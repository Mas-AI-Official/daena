"""
Authentication Routes with JWT Support.

Endpoints:
- POST /api/v1/auth/login - Login and get tokens
- POST /api/v1/auth/refresh - Refresh access token
- POST /api/v1/auth/logout - Logout and revoke tokens
- GET /api/v1/auth/me - Get current user info
"""

from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional

from backend.services.jwt_service import jwt_service, UserRole
from backend.services.billing_service import billing_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    """Login request model."""
    user_id: str
    email: Optional[str] = None
    password: Optional[str] = None  # In production, verify password
    tenant_id: Optional[str] = None
    project_id: Optional[str] = None


class LoginResponse(BaseModel):
    """Login response model."""
    access_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int
    user_id: str
    role: str


async def get_current_user(
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> dict:
    """
    Get current user from JWT token.
    
    Returns:
        User payload from JWT token
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    token = authorization.credentials
    payload = jwt_service.verify_token(token, token_type="access")
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    return payload


@router.post("/login")
async def login(request: LoginRequest) -> LoginResponse:
    """
    Login and get JWT tokens.
    
    In production, verify password here.
    """
    # TODO: Verify password against user database
    # For now, accept any user_id
    
    # Determine role (in production, get from database)
    role = UserRole.CLIENT  # Default
    if request.user_id == "founder" or request.user_id.startswith("founder_"):
        role = UserRole.FOUNDER
    elif request.user_id.startswith("admin_"):
        role = UserRole.ADMIN
    elif request.user_id.startswith("agent_"):
        role = UserRole.AGENT
    
    # Generate token pair
    token_pair = jwt_service.generate_token_pair(
        user_id=request.user_id,
        role=role,
        email=request.email,
        tenant_id=request.tenant_id,
        project_id=request.project_id
    )
    
    return LoginResponse(
        access_token=token_pair["access_token"],
        refresh_token=token_pair["refresh_token"],
        token_type=token_pair["token_type"],
        expires_in=token_pair["expires_in"],
        user_id=request.user_id,
        role=role.value
    )


@router.post("/refresh")
async def refresh_token(
    refresh_token: str = Header(..., alias="X-Refresh-Token")
) -> LoginResponse:
    """
    Refresh access token using refresh token.
    
    Implements token rotation: old refresh token is revoked, new pair is issued.
    """
    token_pair = jwt_service.refresh_access_token(refresh_token)
    
    if not token_pair:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    
    # Extract user info from refresh token (before it was revoked)
    # In production, store user info separately
    payload = jwt_service.verify_token(refresh_token, token_type="refresh")
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    
    return LoginResponse(
        access_token=token_pair["access_token"],
        refresh_token=token_pair["refresh_token"],
        token_type=token_pair["token_type"],
        expires_in=token_pair["expires_in"],
        user_id=payload.get("sub", "unknown"),
        role=payload.get("role", "client")
    )


@router.post("/logout")
async def logout(
    current_user: dict = Depends(get_current_user),
    authorization: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """
    Logout and revoke tokens.
    """
    if authorization:
        token = authorization.credentials
        jwt_service.revoke_token(token)
    
    user_id = current_user.get("sub")
    if user_id:
        jwt_service.revoke_user_tokens(user_id)
    
    return {"success": True, "message": "Logged out successfully"}


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)) -> dict:
    """
    Get current user information.
    """
    user_id = current_user.get("sub")
    plan = billing_service.get_user_plan(user_id) if user_id else None
    
    return {
        "user_id": user_id,
        "role": current_user.get("role"),
        "email": current_user.get("email"),
        "tenant_id": current_user.get("tenant_id"),
        "project_id": current_user.get("project_id"),
        "plan": plan.value if plan else None
    }
