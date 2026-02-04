import keyring
from cryptography.fernet import Fernet
import os

class CredentialVault:
    """
    Secure credential storage using Windows Credential Manager (keyring library)
    Never stores passwords in plain text
    """
    
    SERVICE_NAME = "Daena-AI"
    
    @staticmethod
    def store_secret(key: str, value: str):
        """Store a secret securely"""
        keyring.set_password(CredentialVault.SERVICE_NAME, key, value)
    
    @staticmethod
    def get_secret(key: str) -> str:
        """Retrieve a secret"""
        return keyring.get_password(CredentialVault.SERVICE_NAME, key)
    
    @staticmethod
    def delete_secret(key: str):
        """Delete a secret"""
        keyring.delete_password(CredentialVault.SERVICE_NAME, key)
    
    @staticmethod
    def encrypt_data(data: str, key: bytes) -> bytes:
        """Encrypt sensitive data at rest"""
        f = Fernet(key)
        return f.encrypt(data.encode())
    
    @staticmethod
    def decrypt_data(encrypted_data: bytes, key: bytes) -> str:
        """Decrypt sensitive data"""
        f = Fernet(key)
        return f.decrypt(encrypted_data).decode()
    
    @classmethod
    def migrate_env_secrets_to_vault(cls):
        """
        Migrate secrets from .env to credential vault
        Call this once during setup
        """
        secrets_to_migrate = [
            "JWT_SECRET",
            "FOUNDER_APPROVAL_TOKEN",
            "DAENABOT_HANDS_TOKEN",
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GOOGLE_API_KEY"
        ]
        
        for secret_name in secrets_to_migrate:
            value = os.getenv(secret_name)
            if value:
                cls.store_secret(secret_name, value)
                print(f"✓ Migrated {secret_name} to vault")

# Usage in backend:
# Instead of: os.getenv("JWT_SECRET")
# Use: CredentialVault.get_secret("JWT_SECRET")
