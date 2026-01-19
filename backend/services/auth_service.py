"""
Auth service (NO-AUTH baseline).

Per project policy, authentication/login/session/JWT is disabled for now.
When DISABLE_AUTH=1 (default), `get_current_user()` always returns a Dev Founder.
"""

from typing import Optional
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from backend.config.settings import get_settings
settings = get_settings()

# Security scheme (kept for compatibility; in no-auth mode it is not required)
security = HTTPBearer(auto_error=False)

class TokenData(BaseModel):
    username: Optional[str] = None
    user_id: Optional[str] = None
    role: Optional[str] = None

class User(BaseModel):
    user_id: str
    username: str
    email: str
    role: str
    is_active: bool = True

class AuthService:
    """Auth service placeholder (kept for compatibility)."""

    def verify_token(self, token: str) -> TokenData:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth disabled")

# Global auth service instance
auth_service = AuthService()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get current user - returns Dev Founder when DISABLE_AUTH=True."""
    if getattr(settings, "disable_auth", False):
        from backend.security.dev_user import DevUser
        dev_user = DevUser(name=getattr(settings, "dev_founder_name", "Masoud"))
        return User(
            user_id=dev_user.user_id,
            username=dev_user.username,
            email=dev_user.email,
            role=dev_user.role,
            is_active=dev_user.is_active,
        )
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Auth disabled")

async def get_current_user_optional(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[User]:
    """Get current user - returns Dev Founder when DISABLE_AUTH=True, else None."""
    if getattr(settings, "disable_auth", False):
        return await get_current_user(credentials)
    return None