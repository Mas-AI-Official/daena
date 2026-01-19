"""
Cloud KMS Adapters for Daena

Provides integration with cloud Key Management Services:
- AWS KMS
- Azure Key Vault
- GCP Secret Manager

Supports automatic key rotation and secure key storage.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class CloudKMSAdapter(ABC):
    """Base class for cloud KMS adapters."""
    
    @abstractmethod
    def get_key(self, key_id: str) -> Optional[str]:
        """
        Retrieve encryption key from cloud KMS.
        
        Args:
            key_id: Key identifier
            
        Returns:
            Key material as string, or None if not found
        """
        pass
    
    @abstractmethod
    def create_key(self, key_id: str, key_material: Optional[str] = None) -> str:
        """
        Create a new encryption key in cloud KMS.
        
        Args:
            key_id: Key identifier
            key_material: Optional key material (if None, KMS generates)
            
        Returns:
            Key material as string
        """
        pass
    
    @abstractmethod
    def rotate_key(self, key_id: str) -> str:
        """
        Rotate encryption key in cloud KMS.
        
        Args:
            key_id: Key identifier
            
        Returns:
            New key material as string
        """
        pass
    
    @abstractmethod
    def delete_key(self, key_id: str) -> bool:
        """
        Delete encryption key from cloud KMS.
        
        Args:
            key_id: Key identifier
            
        Returns:
            True if deleted, False otherwise
        """
        pass
    
    @abstractmethod
    def list_keys(self) -> list[str]:
        """
        List all key IDs in cloud KMS.
        
        Returns:
            List of key IDs
        """
        pass


class AWSKMSAdapter(CloudKMSAdapter):
    """AWS KMS adapter."""
    
    def __init__(
        self,
        region: Optional[str] = None,
        key_id: Optional[str] = None,
        profile: Optional[str] = None
    ):
        """
        Initialize AWS KMS adapter.
        
        Args:
            region: AWS region (default: from AWS_REGION env or us-east-1)
            key_id: Default key ID (default: from AWS_KMS_KEY_ID env)
            profile: AWS profile name (optional)
        """
        self.region = region or os.getenv("AWS_REGION", "us-east-1")
        self.key_id = key_id or os.getenv("AWS_KMS_KEY_ID")
        self.profile = profile or os.getenv("AWS_PROFILE")
        
        try:
            import boto3
            session = boto3.Session(profile_name=self.profile) if self.profile else boto3.Session()
            self.kms_client = session.client('kms', region_name=self.region)
            logger.info(f"✅ AWS KMS adapter initialized (region: {self.region})")
        except ImportError:
            logger.warning("⚠️ boto3 not installed. Install: pip install boto3")
            self.kms_client = None
        except Exception as e:
            logger.error(f"❌ Failed to initialize AWS KMS: {e}")
            self.kms_client = None
    
    def get_key(self, key_id: str) -> Optional[str]:
        """Get key from AWS KMS (decrypts data key)."""
        if not self.kms_client:
            return None
        
        try:
            # In AWS KMS, we typically store encrypted data keys
            # This is a simplified version - in production, you'd store encrypted keys
            # and decrypt them using KMS
            response = self.kms_client.describe_key(KeyId=key_id)
            if response['KeyMetadata']['KeyState'] == 'Enabled':
                # For this adapter, we'll use the key ID to reference the key
                # In production, you'd decrypt a stored encrypted data key
                return key_id
            return None
        except Exception as e:
            logger.error(f"Failed to get key from AWS KMS: {e}")
            return None
    
    def create_key(self, key_id: str, key_material: Optional[str] = None) -> str:
        """Create a new key in AWS KMS."""
        if not self.kms_client:
            raise RuntimeError("AWS KMS client not initialized")
        
        try:
            # Create a new CMK (Customer Master Key)
            response = self.kms_client.create_key(
                Description=f"Daena encryption key: {key_id}",
                KeyUsage='ENCRYPT_DECRYPT',
                KeySpec='SYMMETRIC_DEFAULT'
            )
            
            key_arn = response['KeyMetadata']['Arn']
            logger.info(f"Created AWS KMS key: {key_arn}")
            
            # If key_material provided, generate a data key and encrypt it
            if key_material:
                data_key_response = self.kms_client.generate_data_key(
                    KeyId=key_arn,
                    KeySpec='AES_256'
                )
                # Store encrypted data key (in production, store this securely)
                return base64.b64encode(data_key_response['Plaintext']).decode('utf-8')
            
            return key_arn
        except Exception as e:
            logger.error(f"Failed to create key in AWS KMS: {e}")
            raise
    
    def rotate_key(self, key_id: str) -> str:
        """Rotate key in AWS KMS."""
        if not self.kms_client:
            raise RuntimeError("AWS KMS client not initialized")
        
        try:
            # AWS KMS supports automatic key rotation
            # For manual rotation, generate a new data key
            response = self.kms_client.generate_data_key(
                KeyId=key_id,
                KeySpec='AES_256'
            )
            new_key = base64.b64encode(response['Plaintext']).decode('utf-8')
            logger.info(f"Rotated AWS KMS key: {key_id}")
            return new_key
        except Exception as e:
            logger.error(f"Failed to rotate key in AWS KMS: {e}")
            raise
    
    def delete_key(self, key_id: str) -> bool:
        """Schedule key deletion in AWS KMS."""
        if not self.kms_client:
            return False
        
        try:
            self.kms_client.schedule_key_deletion(KeyId=key_id, PendingWindowInDays=7)
            logger.info(f"Scheduled AWS KMS key deletion: {key_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete key in AWS KMS: {e}")
            return False
    
    def list_keys(self) -> list[str]:
        """List all keys in AWS KMS."""
        if not self.kms_client:
            return []
        
        try:
            response = self.kms_client.list_keys()
            return [key['KeyId'] for key in response.get('Keys', [])]
        except Exception as e:
            logger.error(f"Failed to list keys in AWS KMS: {e}")
            return []


class AzureKeyVaultAdapter(CloudKMSAdapter):
    """Azure Key Vault adapter."""
    
    def __init__(
        self,
        vault_url: Optional[str] = None,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ):
        """
        Initialize Azure Key Vault adapter.
        
        Args:
            vault_url: Key Vault URL (default: from AZURE_KEY_VAULT_URL env)
            tenant_id: Azure tenant ID (default: from AZURE_TENANT_ID env)
            client_id: Azure client ID (default: from AZURE_CLIENT_ID env)
            client_secret: Azure client secret (default: from AZURE_CLIENT_SECRET env)
        """
        self.vault_url = vault_url or os.getenv("AZURE_KEY_VAULT_URL")
        self.tenant_id = tenant_id or os.getenv("AZURE_TENANT_ID")
        self.client_id = client_id or os.getenv("AZURE_CLIENT_ID")
        self.client_secret = client_secret or os.getenv("AZURE_CLIENT_SECRET")
        
        try:
            from azure.identity import ClientSecretCredential
            from azure.keyvault.secrets import SecretClient
            
            if self.vault_url and self.tenant_id and self.client_id and self.client_secret:
                credential = ClientSecretCredential(
                    tenant_id=self.tenant_id,
                    client_id=self.client_id,
                    client_secret=self.client_secret
                )
                self.secret_client = SecretClient(vault_url=self.vault_url, credential=credential)
                logger.info(f"✅ Azure Key Vault adapter initialized (vault: {self.vault_url})")
            else:
                # Try default credential (Managed Identity, etc.)
                from azure.identity import DefaultAzureCredential
                credential = DefaultAzureCredential()
                self.secret_client = SecretClient(vault_url=self.vault_url or "", credential=credential)
                logger.info("✅ Azure Key Vault adapter initialized (default credential)")
        except ImportError:
            logger.warning("⚠️ azure-keyvault-secrets not installed. Install: pip install azure-keyvault-secrets azure-identity")
            self.secret_client = None
        except Exception as e:
            logger.error(f"❌ Failed to initialize Azure Key Vault: {e}")
            self.secret_client = None
    
    def get_key(self, key_id: str) -> Optional[str]:
        """Get secret (key) from Azure Key Vault."""
        if not self.secret_client:
            return None
        
        try:
            secret = self.secret_client.get_secret(key_id)
            return secret.value
        except Exception as e:
            logger.error(f"Failed to get secret from Azure Key Vault: {e}")
            return None
    
    def create_key(self, key_id: str, key_material: Optional[str] = None) -> str:
        """Create a new secret (key) in Azure Key Vault."""
        if not self.secret_client:
            raise RuntimeError("Azure Key Vault client not initialized")
        
        try:
            if key_material is None:
                # Generate a random key
                import secrets
                key_material = base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
            
            self.secret_client.set_secret(key_id, key_material)
            logger.info(f"Created Azure Key Vault secret: {key_id}")
            return key_material
        except Exception as e:
            logger.error(f"Failed to create secret in Azure Key Vault: {e}")
            raise
    
    def rotate_key(self, key_id: str) -> str:
        """Rotate secret (key) in Azure Key Vault."""
        if not self.secret_client:
            raise RuntimeError("Azure Key Vault client not initialized")
        
        try:
            # Generate new key
            import secrets
            new_key = base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
            
            # Update secret
            self.secret_client.set_secret(key_id, new_key)
            logger.info(f"Rotated Azure Key Vault secret: {key_id}")
            return new_key
        except Exception as e:
            logger.error(f"Failed to rotate secret in Azure Key Vault: {e}")
            raise
    
    def delete_key(self, key_id: str) -> bool:
        """Delete secret (key) from Azure Key Vault."""
        if not self.secret_client:
            return False
        
        try:
            self.secret_client.begin_delete_secret(key_id)
            logger.info(f"Deleted Azure Key Vault secret: {key_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete secret from Azure Key Vault: {e}")
            return False
    
    def list_keys(self) -> list[str]:
        """List all secrets (keys) in Azure Key Vault."""
        if not self.secret_client:
            return []
        
        try:
            secrets = self.secret_client.list_properties_of_secrets()
            return [secret.name for secret in secrets]
        except Exception as e:
            logger.error(f"Failed to list secrets in Azure Key Vault: {e}")
            return []


class GCPSecretManagerAdapter(CloudKMSAdapter):
    """GCP Secret Manager adapter."""
    
    def __init__(
        self,
        project_id: Optional[str] = None,
        credentials_path: Optional[str] = None
    ):
        """
        Initialize GCP Secret Manager adapter.
        
        Args:
            project_id: GCP project ID (default: from GCP_PROJECT_ID env)
            credentials_path: Path to service account JSON (default: from GOOGLE_APPLICATION_CREDENTIALS env)
        """
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")
        self.credentials_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        
        try:
            from google.cloud import secretmanager
            
            if self.credentials_path:
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = self.credentials_path
            
            self.secret_client = secretmanager.SecretManagerServiceClient()
            logger.info(f"✅ GCP Secret Manager adapter initialized (project: {self.project_id})")
        except ImportError:
            logger.warning("⚠️ google-cloud-secret-manager not installed. Install: pip install google-cloud-secret-manager")
            self.secret_client = None
        except Exception as e:
            logger.error(f"❌ Failed to initialize GCP Secret Manager: {e}")
            self.secret_client = None
    
    def get_key(self, key_id: str) -> Optional[str]:
        """Get secret (key) from GCP Secret Manager."""
        if not self.secret_client or not self.project_id:
            return None
        
        try:
            name = f"projects/{self.project_id}/secrets/{key_id}/versions/latest"
            response = self.secret_client.access_secret_version(request={"name": name})
            return response.payload.data.decode('UTF-8')
        except Exception as e:
            logger.error(f"Failed to get secret from GCP Secret Manager: {e}")
            return None
    
    def create_key(self, key_id: str, key_material: Optional[str] = None) -> str:
        """Create a new secret (key) in GCP Secret Manager."""
        if not self.secret_client or not self.project_id:
            raise RuntimeError("GCP Secret Manager client not initialized")
        
        try:
            if key_material is None:
                # Generate a random key
                import secrets
                key_material = base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
            
            parent = f"projects/{self.project_id}"
            
            # Create secret
            secret = self.secret_client.create_secret(
                request={
                    "parent": parent,
                    "secret_id": key_id,
                    "secret": {"replication": {"automatic": {}}}
                }
            )
            
            # Add secret version
            self.secret_client.add_secret_version(
                request={
                    "parent": secret.name,
                    "payload": {"data": key_material.encode('UTF-8')}
                }
            )
            
            logger.info(f"Created GCP Secret Manager secret: {key_id}")
            return key_material
        except Exception as e:
            logger.error(f"Failed to create secret in GCP Secret Manager: {e}")
            raise
    
    def rotate_key(self, key_id: str) -> str:
        """Rotate secret (key) in GCP Secret Manager."""
        if not self.secret_client or not self.project_id:
            raise RuntimeError("GCP Secret Manager client not initialized")
        
        try:
            # Generate new key
            import secrets
            new_key = base64.b64encode(secrets.token_bytes(32)).decode('utf-8')
            
            # Add new version
            parent = f"projects/{self.project_id}/secrets/{key_id}"
            self.secret_client.add_secret_version(
                request={
                    "parent": parent,
                    "payload": {"data": new_key.encode('UTF-8')}
                }
            )
            
            logger.info(f"Rotated GCP Secret Manager secret: {key_id}")
            return new_key
        except Exception as e:
            logger.error(f"Failed to rotate secret in GCP Secret Manager: {e}")
            raise
    
    def delete_key(self, key_id: str) -> bool:
        """Delete secret (key) from GCP Secret Manager."""
        if not self.secret_client or not self.project_id:
            return False
        
        try:
            name = f"projects/{self.project_id}/secrets/{key_id}"
            self.secret_client.delete_secret(request={"name": name})
            logger.info(f"Deleted GCP Secret Manager secret: {key_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete secret from GCP Secret Manager: {e}")
            return False
    
    def list_keys(self) -> list[str]:
        """List all secrets (keys) in GCP Secret Manager."""
        if not self.secret_client or not self.project_id:
            return []
        
        try:
            parent = f"projects/{self.project_id}"
            secrets = self.secret_client.list_secrets(request={"parent": parent})
            return [secret.name.split('/')[-1] for secret in secrets]
        except Exception as e:
            logger.error(f"Failed to list secrets in GCP Secret Manager: {e}")
            return []


def get_cloud_kms_adapter(provider: Optional[str] = None) -> Optional[CloudKMSAdapter]:
    """
    Get cloud KMS adapter based on provider or environment.
    
    Args:
        provider: Provider name ('aws', 'azure', 'gcp') or None for auto-detect
        
    Returns:
        CloudKMSAdapter instance or None if not configured
    """
    provider = provider or os.getenv("DAENA_CLOUD_KMS_PROVIDER", "").lower()
    
    if provider == "aws" or (not provider and os.getenv("AWS_REGION")):
        return AWSKMSAdapter()
    elif provider == "azure" or (not provider and os.getenv("AZURE_KEY_VAULT_URL")):
        return AzureKeyVaultAdapter()
    elif provider == "gcp" or (not provider and os.getenv("GCP_PROJECT_ID")):
        return GCPSecretManagerAdapter()
    else:
        logger.warning("No cloud KMS provider configured")
        return None

