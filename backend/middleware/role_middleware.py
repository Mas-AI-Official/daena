"""
Role-Based Access Control (RBAC) Middleware.

Enforces role matrix: founder > admin > agent > client > guest
"""

from __future__ import annotations

import logging
from typing import Callable, List, Optional
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.services.jwt_service import UserRole, jwt_service

logger = logging.getLogger(__name__)


# Role hierarchy (higher number = more permissions)
ROLE_HIERARCHY = {
    UserRole.FOUNDER: 5,
    UserRole.ADMIN: 4,
    UserRole.AGENT: 3,
    UserRole.CLIENT: 2,
    UserRole.GUEST: 1
}


# Route-to-role mapping (route pattern -> minimum required role)
ROUTE_ROLES = {
    # Founder-only routes
    "/api/v1/system/emergency-stop": UserRole.FOUNDER,
    "/api/v1/system/reboot": UserRole.FOUNDER,
    "/api/v1/system/security-audit": UserRole.FOUNDER,
    
    # Admin+ routes
    "/api/v1/system/": UserRole.ADMIN,
    "/api/v1/admin/": UserRole.ADMIN,
    "/api/v1/users/": UserRole.ADMIN,
    
    # Agent+ routes
    "/api/v1/agents/": UserRole.AGENT,
    "/api/v1/council/": UserRole.AGENT,
    "/api/v1/self-evolve/": UserRole.AGENT,
    
    # Client+ routes (default)
    "/api/v1/": UserRole.CLIENT,
    
    # Public routes (no auth required)
    "/api/v1/health": None,
    "/api/v1/slo/health": None,
    "/api/v1/auth/login": None,
    "/api/v1/auth/refresh": None,
}


def get_required_role(path: str) -> Optional[UserRole]:
    """
    Get minimum required role for a path.
    
    Args:
        path: Request path
    
    Returns:
        Minimum required role, or None if public
    """
    # Check exact matches first
    if path in ROUTE_ROLES:
        return ROUTE_ROLES[path]
    
    # Check prefix matches (longest match wins)
    matching_prefixes = [
        prefix for prefix in ROUTE_ROLES.keys()
        if path.startswith(prefix)
    ]
    
    if matching_prefixes:
        # Sort by length (longest first) to get most specific match
        matching_prefixes.sort(key=len, reverse=True)
        return ROUTE_ROLES[matching_prefixes[0]]
    
    # Default: require client role
    return UserRole.CLIENT


def has_permission(user_role: UserRole, required_role: Optional[UserRole]) -> bool:
    """
    Check if user role has permission for required role.
    
    Args:
        user_role: User's role
        required_role: Required role (None = public)
    
    Returns:
        True if user has permission
    """
    if required_role is None:
        return True  # Public route
    
    user_level = ROLE_HIERARCHY.get(user_role, 0)
    required_level = ROLE_HIERARCHY.get(required_role, 0)
    
    return user_level >= required_level


class RoleMiddleware(BaseHTTPMiddleware):
    """
    Middleware that enforces role-based access control.
    
    Checks JWT token for user role and verifies permission for requested route.
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.public_paths = [
            "/",
            "/docs",
            "/openapi.json",
            "/dashboard",
            "/api/v1/health",
            "/api/v1/slo/health",
            "/api/v1/auth/login",
            "/api/v1/auth/refresh"
        ]
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Process request with role checking."""
        path = request.url.path

        # NO-AUTH MODE: bypass role checks entirely
        try:
            from config.settings import settings as app_settings
            if getattr(app_settings, "disable_auth", False):
                return await call_next(request)
        except Exception:
            pass
        
        # Skip role check for public paths
        if any(path.startswith(public) for public in self.public_paths):
            return await call_next(request)
        
        # Skip role check for OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)
        
        # Get required role for this path
        required_role = get_required_role(path)
        
        # If public route, allow
        if required_role is None:
            return await call_next(request)
        
        # Try to get user role from JWT token
        user_role = None
        authorization = request.headers.get("Authorization")
        
        if authorization and authorization.startswith("Bearer "):
            token = authorization[7:]  # Remove "Bearer " prefix
            payload = jwt_service.verify_token(token, token_type="access")
            
            if payload:
                role_str = payload.get("role")
                try:
                    user_role = UserRole(role_str)
                except ValueError:
                    logger.warning(f"Invalid role in token: {role_str}")
        
        # If no token, try API key (for backward compatibility)
        if not user_role:
            api_key = request.headers.get("X-API-Key")
            if api_key:
                # API key grants client role (backward compatibility)
                user_role = UserRole.CLIENT
            else:
                # No auth - deny access
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
        
        # Check permission
        if not has_permission(user_role, required_role):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {required_role.value}, your role: {user_role.value}"
            )
        
        # Add user role to request state
        request.state.user_role = user_role
        
        return await call_next(request)

