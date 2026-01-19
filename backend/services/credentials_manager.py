"""
Credentials Manager
Secure storage and retrieval of integration credentials
"""
from cryptography.fernet import Fernet
from pathlib import Path
import json
from typing import Dict, Any, Optional
import os

class CredentialsManager:
    """Manages encrypted credentials for integrations"""
    
    _instance = None
    
    def __init__(self):
        self.key_file = Path(__file__).parent.parent.parent / "local_brain" / ".key"
        self.creds_file = Path(__file__).parent.parent.parent / "local_brain" / "credentials.enc"
        self.cipher = self._load_or_create_key()
        self.credentials: Dict[str, Dict[str, Any]] = self._load_credentials()
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = CredentialsManager()
        return cls._instance
    
    def _load_or_create_key(self) -> Fernet:
        """Load encryption key or create if doesn't exist"""
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        
        if self.key_file.exists():
            with open(self.key_file, 'rb') as f:
                key = f.read()
        else:
            key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(key)
            # Make file read-only for security
            os.chmod(self.key_file, 0o600)
        
        return Fernet(key)
    
    def _load_credentials(self) -> Dict[str, Dict[str, Any]]:
        """Load encrypted credentials"""
        if not self.creds_file.exists():
            return {}
        
        try:
            with open(self.creds_file, 'rb') as f:
                encrypted = f.read()
            
            decrypted = self.cipher.decrypt(encrypted)
            return json.loads(decrypted.decode())
        except Exception as e:
            print(f"Error loading credentials: {e}")
            return {}
    
    def _save_credentials(self):
        """Save credentials encrypted"""
        try:
            self.creds_file.parent.mkdir(parents=True, exist_ok=True)
            
            plaintext = json.dumps(self.credentials).encode()
            encrypted = self.cipher.encrypt(plaintext)
            
            with open(self.creds_file, 'wb') as f:
                f.write(encrypted)
            
            # Make file read-only for security
            os.chmod(self.creds_file, 0o600)
        except Exception as e:
            print(f"Error saving credentials: {e}")
    
    def store(self, integration_id: str, credentials: Dict[str, Any], user_id: str = "default"):
        """
        Store credentials for an integration
        Args:
            integration_id: ID of the integration
            credentials: Credentials dict (API keys, tokens, etc.)
            user_id: User ID (for multi-user support)
        """
        key = f"{user_id}:{integration_id}"
        self.credentials[key] = credentials
        self._save_credentials()
    
    def retrieve(self, integration_id: str, user_id: str = "default") -> Optional[Dict[str, Any]]:
        """
        Retrieve credentials for an integration
        Args:
            integration_id: ID of the integration
            user_id: User ID
        Returns: Credentials dict or None
        """
        key = f"{user_id}:{integration_id}"
        return self.credentials.get(key)
    
    def delete(self, integration_id: str, user_id: str = "default"):
        """
        Delete credentials for an integration
        Args:
            integration_id: ID of the integration
            user_id: User ID
        """
        key = f"{user_id}:{integration_id}"
        if key in self.credentials:
            del self.credentials[key]
            self._save_credentials()
    
    def list_configured(self, user_id: str = "default") -> list[str]:
        """
        List all integrations with stored credentials for a user
        Args:
            user_id: User ID
        Returns: List of integration IDs
        """
        prefix = f"{user_id}:"
        return [
            key.split(":", 1)[1] 
            for key in self.credentials.keys() 
            if key.startswith(prefix)
        ]
    
    def mask_credentials(self, credentials: Dict[str, Any]) -> Dict[str, Any]:
        """
        Mask sensitive credentials for display
        Args:
            credentials: Credentials dict
        Returns: Masked credentials dict
        """
        masked = {}
        for key, value in credentials.items():
            if isinstance(value, str) and len(value) > 8:
                # Show first 4 and last 4 characters
                masked[key] = f"{value[:4]}...{value[-4:]}"
            else:
                masked[key] = "***"
        return masked

def get_credentials_manager():
    """Get global credentials manager instance"""
    return CredentialsManager.get_instance()
