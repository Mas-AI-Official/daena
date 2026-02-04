import jwt
from datetime import datetime, timedelta
import os
from backend.security.credential_vault import CredentialVault

def get_secret_secure(key: str, default=None):
    """Get secret from vault, fallback to env"""
    secret = CredentialVault.get_secret(key)
    if not secret:
        secret = os.getenv(key, default)
    return secret

def generate_jwt_token(user_id: str, role: str) -> str:
    """Generate JWT token for authenticated user"""
    secret = get_secret_secure("JWT_SECRET")
    if not secret:
        raise ValueError("JWT_SECRET not found in vault or environment")
        
    payload = {
        "user_id": user_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, secret, algorithm="HS256")

def verify_jwt_token(token: str) -> dict:
    """Verify JWT token"""
    try:
        secret = get_secret_secure("JWT_SECRET")
        if not secret:
            return None
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def require_founder_approval(token: str) -> bool:
    """Check if token is the founder approval token"""
    founder_token = get_secret_secure("FOUNDER_APPROVAL_TOKEN")
    if not founder_token:
        return False
    return token == founder_token
