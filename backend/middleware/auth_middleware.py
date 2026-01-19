"""
Authentication Middleware for Daena AI VP
Protects dashboard routes and redirects unauthenticated users to login
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import List
import logging

from backend.services.auth_service import auth_service

logger = logging.getLogger(__name__)

# Public paths that don't require authentication
PUBLIC_PATHS: List[str] = [
    "/login",
    "/auth/token",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/docs",
    "/openapi.json",
    "/static",  # Static files (CSS, JS, images)
    "/favicon.ico",
    "/health",  # Root health check
    "/api/v1/health",
    "/api/v1/slo/health",
    "/api/v1/slo/liveness",
    "/api/v1/slo/readiness",
]

# API paths that require authentication but return JSON errors instead of redirects
API_PATHS: List[str] = [
    "/api/v1/",
]


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware that:
    1. Allows public paths without authentication
    2. Checks JWT tokens for protected routes
    3. Redirects web pages to /login if not authenticated
    4. Returns 401 for API endpoints if not authenticated
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # NO-AUTH MODE: bypass all authentication checks
        try:
            from config.settings import settings as app_settings
            if getattr(app_settings, "disable_auth", False):
                # Provide a minimal user object on request.state for any consumers
                request.state.user = {
                    "username": getattr(app_settings, "dev_founder_name", "Masoud"),
                    "role": "founder",
                    "user_id": "local-dev-founder",
                }
                return await call_next(request)
        except Exception:
            # If settings can't be loaded, fall through to normal logic
            pass
        
        # Allow public paths
        if any(path.startswith(public_path) for public_path in PUBLIC_PATHS):
            return await call_next(request)
        
        # Check for authentication token
        token = None
        
        # Try to get token from cookie
        token = request.cookies.get("access_token")
        
        # Try to get token from Authorization header
        if not token:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header.replace("Bearer ", "")
        
        # Verify token
        if token:
            try:
                token_data = auth_service.verify_token(token)
                if token_data:
                    # Add user info to request state
                    request.state.user = token_data
                    return await call_next(request)
            except Exception as e:
                logger.debug(f"Token verification failed: {e}")
        
        # No valid token - handle based on path type
        if any(path.startswith(api_path) for api_path in API_PATHS):
            # API endpoint - return 401 JSON error
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        else:
            # Web page - redirect to login
            return RedirectResponse(url="/login", status_code=302)

