from cryptography.fernet import Fernet
from typing import Dict, Any, List, Optional
from datetime import datetime
import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class VaultService:
    def __init__(self, key: Optional[str] = None):
        # In production, this key should come from a secure environment variable or KMS
        self.key = key or os.environ.get("VAULT_ENCRYPTION_KEY")
        if not self.key:
            # Generate a key if none exists (for dev/demo purposes)
            self.key = Fernet.generate_key().decode()
            logger.warning("⚠️ No VAULT_ENCRYPTION_KEY found. Generated temporary key.")
            
        self.cipher = Fernet(self.key)
        self.storage_path = Path(".ledger/vault_secrets.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.secrets = self._load()

    def _load(self) -> Dict[str, Any]:
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load vault secrets: {e}")
        return {}

    def _save(self):
        try:
            with open(self.storage_path, "w") as f:
                json.dump(self.secrets, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save vault secrets: {e}")

    def encrypt(self, plaintext: str) -> str:
        return self.cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self.cipher.decrypt(ciphertext.encode()).decode()

    def store_secret(self, name: str, value: str, category: str, owner: str) -> Dict[str, Any]:
        """Store verify-encrypted secret"""
        encrypted_value = self.encrypt(value)
        secret_id = f"sec_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{os.urandom(4).hex()}"
        
        secret_entry = {
            "id": secret_id,
            "name": name,
            "value": encrypted_value,
            "category": category,
            "created_by": owner,
            "created_at": datetime.utcnow().isoformat(),
            "last_accessed": None
        }
        
        self.secrets[secret_id] = secret_entry
        self._save()
        
        # Return harmless metadata
        return {k: v for k, v in secret_entry.items() if k != "value"}

    def get_secret(self, secret_id: str, requestor: str) -> Optional[str]:
        """Retrieve and decrypt a secret"""
        if secret_id not in self.secrets:
            return None
            
        # TODO: Add specific access control logic here based on requestor
        
        secret = self.secrets[secret_id]
        secret["last_accessed"] = datetime.utcnow().isoformat()
        self._save()
        
        return self.decrypt(secret["value"])

    def list_secrets(self, requestor: str) -> List[Dict[str, Any]]:
        """List secrets (metadata only)"""
        # TODO: Filter based on requestor permissions
        return [{k: v for k, v in s.items() if k != "value"} for s in self.secrets.values()]

    def delete_secret(self, secret_id: str, requestor: str) -> bool:
        if secret_id in self.secrets:
            # TODO: Verify requestor is owner or admin
            del self.secrets[secret_id]
            self._save()
            return True
        return False

# Global singleton
_vault_service = None

def get_vault_service():
    global _vault_service
    if _vault_service is None:
        _vault_service = VaultService()
    return _vault_service
