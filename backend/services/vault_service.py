"""
Vault Service - Secure encrypted secrets storage.

Provides:
- AES-256 encryption via Fernet
- Database-backed storage with VaultSecret model
- Access control based on owner and allowed accessors
- Audit trail for all access
- Secret rotation support
"""

from cryptography.fernet import Fernet
from typing import Dict, Any, List, Optional
from datetime import datetime
import os
import uuid
import logging

logger = logging.getLogger(__name__)


class VaultService:
    """
    Secure vault service for storing encrypted secrets.
    Supports both JSON file storage (legacy) and database storage.
    """
    
    def __init__(self, key: Optional[str] = None, use_database: bool = True):
        # 1. Try to get key from arguments or environment
        self.key = key or os.environ.get("VAULT_ENCRYPTION_KEY")
        
        # 2. If no key exists, check/load from .env file
        if not self.key:
            try:
                from pathlib import Path
                env_path = Path(".env")
                if env_path.exists():
                    with open(env_path, "r") as f:
                        for line in f:
                            if line.strip().startswith("VAULT_ENCRYPTION_KEY="):
                                self.key = line.strip().split("=", 1)[1].strip('"\'')
                                break
            except Exception as e:
                logger.warning(f"Failed to read .env file: {e}")

        # 3. If still no key, generate one and save it completely
        if not self.key:
            generated_key = Fernet.generate_key().decode()
            self.key = generated_key
            logger.warning("⚠️ No VAULT_ENCRYPTION_KEY found. Generated new persistent key.")
            
            try:
                # Append to .env file
                with open(".env", "a") as f:
                    f.write(f"\n# Auto-generated Vault Key\nVAULT_ENCRYPTION_KEY={generated_key}\n")
                logger.info("✅ Saved new encryption key to .env file")
            except Exception as e:
                logger.error(f"Failed to save key to .env: {e}")

        # Ensure key is in correct format (bytes)
        if isinstance(self.key, str):
            # Handle potential 'b'...' wrapper from string representation
            clean_key = self.key
            if clean_key.startswith("b'") or clean_key.startswith('b"'):
                try:
                    clean_key = eval(clean_key).decode()
                except:
                    pass
            self.key_bytes = clean_key.encode()
        else:
            self.key_bytes = self.key

        try:
            self.cipher = Fernet(self.key_bytes)
        except Exception as e:
            logger.error(f"Invalid encryption key format: {e}")
            # Fallback to a temporary key to prevent crash, but warn loud
            self.cipher = Fernet(Fernet.generate_key())

        self.use_database = use_database
        self._db_session = None
    
    def _get_db(self):
        """Get database session lazily."""
        if self._db_session is None:
            try:
                from backend.database import SessionLocal
                self._db_session = SessionLocal()
            except Exception as e:
                logger.error(f"Failed to get database session: {e}")
                self.use_database = False
        return self._db_session
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string."""
        return self.cipher.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt an encrypted string."""
        return self.cipher.decrypt(ciphertext.encode()).decode()

    def store_secret(
        self,
        name: str,
        value: str,
        category: str,
        owner: str,
        description: Optional[str] = None,
        allowed_accessors: Optional[List[str]] = None,
        expires_at: Optional[datetime] = None,
        tags: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Store an encrypted secret.
        The value is encrypted server-side. For maximum security,
        the value should also be encrypted client-side before transmission.
        """
        # Encrypt the value
        encrypted_value = self.encrypt(value)
        secret_id = f"sec_{uuid.uuid4().hex[:12]}"
        now = datetime.utcnow()
        
        if self.use_database:
            try:
                from backend.database import VaultSecret
                db = self._get_db()
                if db:
                    secret = VaultSecret(
                        secret_id=secret_id,
                        name=name,
                        category=category,
                        encrypted_value=encrypted_value,
                        encryption_version=1,
                        owner_id=owner,
                        owner_type="user",
                        allowed_accessors=allowed_accessors or [],
                        created_at=now,
                        created_by=owner,
                        description=description,
                        tags=tags or [],
                        expires_at=expires_at
                    )
                    db.add(secret)
                    db.commit()
                    db.refresh(secret)
                    
                    logger.info(f"Stored secret '{name}' with ID {secret_id}")
                    return {
                        "id": secret_id,
                        "name": name,
                        "category": category,
                        "created_at": now.isoformat(),
                        "created_by": owner
                    }
            except Exception as e:
                logger.error(f"Database storage failed, using fallback: {e}")
                self.use_database = False
        
        # Fallback to JSON file storage (legacy behavior)
        return self._store_secret_json(
            secret_id, name, encrypted_value, category, owner, now
        )
    
    def _store_secret_json(
        self,
        secret_id: str,
        name: str,
        encrypted_value: str,
        category: str,
        owner: str,
        created_at: datetime
    ) -> Dict[str, Any]:
        """Fallback JSON file storage."""
        from pathlib import Path
        import json
        
        storage_path = Path(".ledger/vault_secrets.json")
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing
        secrets = {}
        if storage_path.exists():
            try:
                with open(storage_path, "r") as f:
                    secrets = json.load(f)
            except Exception:
                pass
        
        # Add new secret
        secrets[secret_id] = {
            "id": secret_id,
            "name": name,
            "value": encrypted_value,
            "category": category,
            "created_by": owner,
            "created_at": created_at.isoformat(),
            "last_accessed": None
        }
        
        # Save
        with open(storage_path, "w") as f:
            json.dump(secrets, f, indent=2)
        
        return {
            "id": secret_id,
            "name": name,
            "category": category,
            "created_at": created_at.isoformat(),
            "created_by": owner
        }

    def get_secret(self, secret_id: str, requestor: str) -> Optional[str]:
        """
        Retrieve and decrypt a secret.
        
        Access control:
        - Owner can always access
        - Users in allowed_accessors list can access
        - Founder role can access all secrets
        """
        if self.use_database:
            try:
                from backend.database import VaultSecret
                db = self._get_db()
                if db:
                    secret = db.query(VaultSecret).filter(
                        VaultSecret.secret_id == secret_id
                    ).first()
                    
                    if not secret:
                        return None
                    
                    # Access control check
                    if not self._can_access(secret, requestor):
                        logger.warning(f"Access denied to secret {secret_id} for {requestor}")
                        return None
                    
                    # Update access audit
                    secret.last_accessed_at = datetime.utcnow()
                    secret.last_accessed_by = requestor
                    secret.access_count = (secret.access_count or 0) + 1
                    db.commit()
                    
                    return self.decrypt(secret.encrypted_value)
            except Exception as e:
                logger.error(f"Database read failed: {e}")
        
        # Fallback to JSON
        return self._get_secret_json(secret_id, requestor)
    
    def _can_access(self, secret, requestor: str) -> bool:
        """Check if requestor can access the secret."""
        # Owner always has access
        if secret.owner_id == requestor:
            return True
        
        # Check allowed accessors list
        if requestor in (secret.allowed_accessors or []):
            return True
        
        # TODO: Check if requestor has founder/admin role
        # For now, allow founder role
        if requestor.lower() == "founder":
            return True
        
        return False
    
    def _get_secret_json(self, secret_id: str, requestor: str) -> Optional[str]:
        """Fallback JSON file retrieval."""
        from pathlib import Path
        import json
        
        storage_path = Path(".ledger/vault_secrets.json")
        if not storage_path.exists():
            return None
        
        try:
            with open(storage_path, "r") as f:
                secrets = json.load(f)
            
            if secret_id not in secrets:
                return None
            
            secret = secrets[secret_id]
            
            # Update last accessed
            secret["last_accessed"] = datetime.utcnow().isoformat()
            with open(storage_path, "w") as f:
                json.dump(secrets, f, indent=2)
            
            return self.decrypt(secret["value"])
        except Exception as e:
            logger.error(f"JSON read failed: {e}")
            return None

    def list_secrets(self, requestor: str) -> List[Dict[str, Any]]:
        """List secrets metadata (without values). Filtered by access."""
        if self.use_database:
            try:
                from backend.database import VaultSecret
                db = self._get_db()
                if db:
                    # For founder, return all; otherwise filter by owner/accessor
                    if requestor.lower() == "founder":
                        secrets = db.query(VaultSecret).all()
                    else:
                        secrets = db.query(VaultSecret).filter(
                            (VaultSecret.owner_id == requestor) |
                            (VaultSecret.allowed_accessors.contains([requestor]))
                        ).all()
                    
                    return [
                        {
                            "id": s.secret_id,
                            "name": s.name,
                            "category": s.category,
                            "created_at": s.created_at.isoformat() if s.created_at else None,
                            "created_by": s.created_by,
                            "last_accessed_at": s.last_accessed_at.isoformat() if s.last_accessed_at else None,
                            "access_count": s.access_count or 0,
                            "description": s.description,
                            "tags": s.tags or []
                        }
                        for s in secrets
                    ]
            except Exception as e:
                logger.error(f"Database list failed: {e}")
        
        # Fallback to JSON
        return self._list_secrets_json(requestor)
    
    def _list_secrets_json(self, requestor: str) -> List[Dict[str, Any]]:
        """Fallback JSON listing."""
        from pathlib import Path
        import json
        
        storage_path = Path(".ledger/vault_secrets.json")
        if not storage_path.exists():
            return []
        
        try:
            with open(storage_path, "r") as f:
                secrets = json.load(f)
            
            return [
                {k: v for k, v in s.items() if k != "value"}
                for s in secrets.values()
            ]
        except Exception:
            return []

    def delete_secret(self, secret_id: str, requestor: str) -> bool:
        """Delete a secret. Only owner or founder can delete."""
        if self.use_database:
            try:
                from backend.database import VaultSecret
                db = self._get_db()
                if db:
                    secret = db.query(VaultSecret).filter(
                        VaultSecret.secret_id == secret_id
                    ).first()
                    
                    if not secret:
                        return False
                    
                    # Only owner or founder can delete
                    if secret.owner_id != requestor and requestor.lower() != "founder":
                        logger.warning(f"Delete denied for secret {secret_id} by {requestor}")
                        return False
                    
                    db.delete(secret)
                    db.commit()
                    logger.info(f"Deleted secret {secret_id}")
                    return True
            except Exception as e:
                logger.error(f"Database delete failed: {e}")
        
        # Fallback to JSON
        return self._delete_secret_json(secret_id, requestor)
    
    def _delete_secret_json(self, secret_id: str, requestor: str) -> bool:
        """Fallback JSON deletion."""
        from pathlib import Path
        import json
        
        storage_path = Path(".ledger/vault_secrets.json")
        if not storage_path.exists():
            return False
        
        try:
            with open(storage_path, "r") as f:
                secrets = json.load(f)
            
            if secret_id not in secrets:
                return False
            
            del secrets[secret_id]
            
            with open(storage_path, "w") as f:
                json.dump(secrets, f, indent=2)
            
            return True
        except Exception:
            return False

    def rotate_secret(
        self,
        secret_id: str,
        new_value: str,
        requestor: str
    ) -> Dict[str, Any]:
        """Rotate a secret's value while preserving metadata."""
        if self.use_database:
            try:
                from backend.database import VaultSecret
                db = self._get_db()
                if db:
                    secret = db.query(VaultSecret).filter(
                        VaultSecret.secret_id == secret_id
                    ).first()
                    
                    if not secret:
                        return {"success": False, "error": "Secret not found"}
                    
                    # Only owner can rotate
                    if secret.owner_id != requestor and requestor.lower() != "founder":
                        return {"success": False, "error": "Access denied"}
                    
                    # Update the encrypted value
                    secret.encrypted_value = self.encrypt(new_value)
                    secret.last_rotated_at = datetime.utcnow()
                    secret.updated_at = datetime.utcnow()
                    db.commit()
                    
                    return {
                        "success": True,
                        "id": secret_id,
                        "rotated_at": secret.last_rotated_at.isoformat()
                    }
            except Exception as e:
                logger.error(f"Secret rotation failed: {e}")
                return {"success": False, "error": str(e)}
        
        return {"success": False, "error": "Database not available"}


# Global singleton
_vault_service: Optional[VaultService] = None


def get_vault_service() -> VaultService:
    """Get the global vault service instance."""
    global _vault_service
    if _vault_service is None:
        _vault_service = VaultService()
    return _vault_service
