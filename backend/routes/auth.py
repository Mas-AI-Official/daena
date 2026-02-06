"""
Authentication Routes with JWT Support.

Endpoints:
- POST /api/v1/auth/login - Login and get tokens
- POST /api/v1/auth/refresh - Refresh access token
- POST /api/v1/auth/logout - Logout and revoke tokens
- GET /api/v1/auth/me - Get current user info
"""

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional

from backend.services.jwt_service import jwt_service, UserRole
from backend.services.billing_service import billing_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


def _client_ip(request: Request) -> str:
    """Client IP for containment/JWT revocation tracking."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return getattr(request.client, "host", "") if request.client else ""


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
async def login(body: LoginRequest, request: Request) -> LoginResponse:
    """
    Login and get JWT tokens.
    
    In production, verify password here.
    Client IP is recorded for containment (revoke sessions when IP is blocked).
    """
    # TODO: Verify password against user database
    # For now, accept any user_id
    
    # Determine role (in production, get from database)
    role = UserRole.CLIENT  # Default
    if body.user_id == "founder" or body.user_id.startswith("founder_") or "masoud" in body.user_id.lower():
        role = UserRole.FOUNDER
    elif body.user_id.startswith("admin_"):
        role = UserRole.ADMIN
    elif body.user_id.startswith("agent_"):
        role = UserRole.AGENT
    
    # Generate token pair
    token_pair = jwt_service.generate_token_pair(
        user_id=body.user_id,
        role=role,
        email=body.email,
        tenant_id=body.tenant_id,
        project_id=body.project_id
    )
    ip = _client_ip(request)
    if ip:
        jwt_service.record_tokens_for_ip(
            ip,
            token_pair["access_token"],
            token_pair["refresh_token"],
        )
    
    return LoginResponse(
        access_token=token_pair["access_token"],
        refresh_token=token_pair["refresh_token"],
        token_type=token_pair["token_type"],
        expires_in=token_pair["expires_in"],
        user_id=body.user_id,
        role=role.value
    )


class RefreshRequest(BaseModel):
    refresh_token: Optional[str] = None

@router.post("/refresh")
async def refresh_token(
    request: Request,
    body: Optional[RefreshRequest] = None,
    x_refresh_token: Optional[str] = Header(None, alias="X-Refresh-Token")
) -> LoginResponse:
    """
    Refresh access token using refresh token.
    Supports token rotation: old refresh token is revoked, new pair is issued.
    """
    token = (body.refresh_token if body else None) or x_refresh_token
    
    if not token:
        raise HTTPException(status_code=400, detail="Refresh token missing (use X-Refresh-Token header or body)")
        
    token_pair = jwt_service.refresh_access_token(token)
    
    if not token_pair:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    
    # Record new tokens for this client IP (containment revocation)
    ip = _client_ip(request)
    if ip:
        jwt_service.record_tokens_for_ip(
            ip,
            token_pair["access_token"],
            token_pair["refresh_token"],
        )
    
    # Extract user info from refresh token (before it was revoked)
    payload = jwt_service.verify_token(token, token_type="refresh")
    if not payload:
        # Fallback if verify fails after refresh_access_token (unlikely)
        return LoginResponse(
            access_token=token_pair["access_token"],
            refresh_token=token_pair["refresh_token"],
            token_type=token_pair["token_type"],
            expires_in=token_pair["expires_in"],
            user_id="unknown",
            role="client"
        )
    
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
