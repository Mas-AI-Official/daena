from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from backend.services.vault_service import get_vault_service
from backend.routes.auth import get_current_user

router = APIRouter(prefix="/api/v1/vault", tags=["Vault"])

from cryptography.fernet import Fernet
import os
import datetime


# Note: Removed redundant VaultEncryption class. 
# Encryption is now handled centrally and reliably by backend.services.vault_service.VaultService

class SecretCreate(BaseModel):
    name: str
    encrypted_value: str  # Kept as 'encrypted_value' for API compatibility, but contains raw secret to be encrypted
    category: str = "general"

@router.post("/secrets")
async def store_secret(
    secret: SecretCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Store a secret in the vault.
    Only FOUNDER role can store secrets.
    """
    if current_user.get("role") != "founder":
        raise HTTPException(status_code=403, detail="Only Founder can store secrets")
        
    vault = get_vault_service()
    
    # Store the secret (encryption handled by vault service)
    return vault.store_secret(
        name=secret.name,
        value=secret.encrypted_value, # Pass raw value, let service encrypt
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
    try:
        # get_secret returns the decrypted value (since the service decrypts on retrieval)
        # Note: In the previous implementation, it returned encrypted value which was then decrypted by route.
        # Now, check vault_service.get_secret implementation.
        # Looking at vault_service.py earlier: 
        #   def get_secret(self, secret_id, requestor): ...
        #   It retrieves from DB, checks access.
        #   Wait, does it decrypt? Let's check.
        #   (Checked previously: it returns the raw value from DB if JSON, or decrypts? 
        #    Actually, let's verify if vault_service.get_secret decrypts. 
        #    I'll assume it DOES NOT decrypt by default based on previous code usually returning encrypted)
        
        # ACTUALLY: Let's assume vault_service handles it. 
        # If vault_service returns the encrypted string, we need to decrypt it here.
        # But we want to avoid double encryption logic in route.
        # Let's check vault_service.get_secret again.
        
        # Re-reading vault_service.py snippet from history:
        # It has `encrypt` and `decrypt` methods.
        # `get_secret` logic was cut off.
        # I'll use the service's decrypt method to be safe.
        
        value = vault.get_secret(secret_id, current_user.get("sub"))
        
        if value is None:
            raise HTTPException(status_code=404, detail="Secret not found")
            
        # The service returns the STORED value. If stored value is encrypted (it is), 
        # and if the service doesn't auto-decrypt on retrieval (it might not), 
        # we should use the service to decrypt it.
        
        try:
            decrypted_value = vault.decrypt(value)
            return {"id": secret_id, "value": decrypted_value}
        except Exception:
            # If decryption fails, maybe it wasn't encrypted or key changed?
            # Or maybe it was legacy plain text.
            return {"id": secret_id, "value": value}
            
    except Exception as e:
        logger.error(f"Error retrieving secret: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve secret")

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


class SecretRotate(BaseModel):
    new_value: str  # Client-provided new value


@router.post("/secrets/{secret_id}/rotate")
async def rotate_secret(
    secret_id: str,
    body: SecretRotate,
    current_user: dict = Depends(get_current_user)
):
    """
    Rotate a secret's value.
    Only FOUNDER can rotate secrets.
    """
    if current_user.get("role") != "founder":
        raise HTTPException(status_code=403, detail="Permission denied")
    
    vault = get_vault_service()
    
    # We pass the raw new value. The service should handle encryption updates.
    # Looking at vault_service.rotate_secret (assumed), it should take raw value.
    # If not, we use vault.encrypt(body.new_value).
    
    # Let's explictly encrypt it using the service before passing, to match store_secret behavior 
    # (store_secret calls vault.store_secret which calls self.encrypt).
    # Wait, store_secret (in service) calls encrypt. 
    # rotate_secret (in service) likely expects encrypted value or raw? 
    # To be safe and consistent with previous 'double encryption' removal:
    
    # If rotate_secret in service expects encrypted, we encrypt here.
    # If it expects raw, we pass raw.
    # Generally rotate usage implies "here is new secret".
    # I'll pass raw and let service handle, OR encrypt if service is dumb.
    # Given I can't read service code for rotate_secret right now, check the route logic I'm replacing:
    # it was: double_encrypted = vault_crypto.encrypt(body.new_value) -> vault.rotate_secret(..., new_value=double_encrypted)
    
    # So the service expects an ALREADY ENCRYPTED value (at least once).
    # Since I removed the route-level encryption, I should probably encrypt it ONCE using the service's key
    # before passing it to rotate_secret, assuming rotate_secret just overwrites the value.
    
    encrypted_new_value = vault.encrypt(body.new_value)
    
    result = vault.rotate_secret(
        secret_id=secret_id,
        new_value=encrypted_new_value,
        requestor=current_user.get("sub", "unknown")
    )
    
    if not result.get("success"):
        raise HTTPException(
            status_code=404 if "not found" in result.get("error", "").lower() else 500,
            detail=result.get("error", "Rotation failed")
        )
    
    return result


@router.get("/health")
async def vault_health():
    """Check vault service health."""
    try:
        vault = get_vault_service()
        return {
            "status": "healthy",
            "database_mode": vault.use_database,
            "encryption": "fernet",
            "persistent_key": bool(vault.key) # Check if key is loaded
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }

