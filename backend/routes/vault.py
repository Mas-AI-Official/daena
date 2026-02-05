from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from backend.services.vault_service import get_vault_service
from backend.routes.auth import get_current_user

router = APIRouter(prefix="/api/v1/vault", tags=["Vault"])

from cryptography.fernet import Fernet
import os
import datetime

class VaultEncryption:
    def __init__(self):
        self.key = os.environ.get("VAULT_ENCRYPTION_KEY")
        if not self.key:
             # Fallback for dev - in production this should be fatal
             self.key = Fernet.generate_key().decode()
             print(f"WARNING: VAULT_ENCRYPTION_KEY not set, using ephemeral key: {self.key}")
        
        # Ensure key is bytes
        if isinstance(self.key, str):
            self.key = self.key.encode()
            
        self.cipher = Fernet(self.key)
    
    def encrypt(self, plaintext: str) -> str:
        return self.cipher.encrypt(plaintext.encode()).decode()
    
    def decrypt(self, ciphertext: str) -> str:
        return self.cipher.decrypt(ciphertext.encode()).decode()

class SecretCreate(BaseModel):
    name: str
    encrypted_value: str  # Changed from value to encrypted_value per audit
    category: str = "general"

@router.post("/secrets")
async def store_secret(
    secret: SecretCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Store a secret in the vault with server-side double encryption.
    Only FOUNDER role can store secrets.
    """
    if current_user.get("role") != "founder":
        raise HTTPException(status_code=403, detail="Only Founder can store secrets")
        
    # Double-encrypt server-side
    vault_crypto = VaultEncryption()
    try:
        double_encrypted = vault_crypto.encrypt(secret.encrypted_value)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Encryption failed: {str(e)}")
        
    vault = get_vault_service()
    
    # Store the doubly encrypted value
    return vault.store_secret(
        name=secret.name,
        value=double_encrypted,
        category=secret.category,
        owner=current_user.get("sub", "unknown")
    )

@router.get("/secrets")
async def list_secrets(current_user: dict = Depends(get_current_user)):
    """List available secrets (metadata only)."""
    if current_user.get("role") != "founder":
        raise HTTPException(status_code=403, detail="Permission denied")
        
    vault = get_vault_service()
    return vault.list_secrets(current_user.get("sub"))

@router.get("/secrets/{secret_id}")
async def get_secret(
    secret_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Retrieve a decrypted secret.
    Strictly audited.
    """
    if current_user.get("role") != "founder":
        raise HTTPException(status_code=403, detail="Permission denied")
        
    vault = get_vault_service()
    value = vault.get_secret(secret_id, current_user.get("sub"))
    
    if value is None:
        raise HTTPException(status_code=404, detail="Secret not found")
        
    # Decrypt server-side layer
    vault_crypto = VaultEncryption()
    try:
        # Try to decrypt (it might be legacy plain text)
        decrypted_value = vault_crypto.decrypt(value)
        return {"id": secret_id, "value": decrypted_value}
    except Exception:
        # Fallback for unencrypted/legacy secrets
        return {"id": secret_id, "value": value}

@router.delete("/secrets/{secret_id}")
async def delete_secret(
    secret_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Delete a secret."""
    if current_user.get("role") != "founder":
        raise HTTPException(status_code=403, detail="Permission denied")
        
    vault = get_vault_service()
    success = vault.delete_secret(secret_id, current_user.get("sub"))
    
    if not success:
        raise HTTPException(status_code=404, detail="Secret not found")
        
    return {"success": True}
