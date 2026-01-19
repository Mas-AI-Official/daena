"""
CSRF (Cross-Site Request Forgery) Protection Middleware.

Features:
- CSRF token generation
- CSRF token verification
- Web form protection
- API endpoint protection (for state-changing requests)
"""

from __future__ import annotations

import secrets
import logging
from typing import Callable, Set
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)


# State-changing HTTP methods that require CSRF protection
PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Paths that don't require CSRF protection
PUBLIC_PATHS = {
    "/",
    "/docs",
    "/openapi.json",
    "/api/v1/health",
    "/api/v1/slo/health",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    "/api/v1/monitoring/metrics",
    "/api/v1/monitoring/metrics/summary"
}


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection middleware.
    
    Validates CSRF tokens for state-changing requests.
    """
    
    def __init__(self, app: ASGIApp, secret_key: str = None):
        super().__init__(app)
        self.secret_key = secret_key or "daena_csrf_secret_key_change_in_production"
        self.token_length = 32
    
    def generate_token(self) -> str:
        """Generate a CSRF token."""
        return secrets.token_urlsafe(self.token_length)
    
    def get_token_from_request(self, request: Request) -> str:
        """
        Extract CSRF token from request.
        
        Checks:
        1. X-CSRF-Token header
        2. csrf_token form field
        3. csrf_token query parameter
        """
        # Check header first (preferred)
        token = request.headers.get("X-CSRF-Token")
        if token:
            return token
        
        # Check form data
        if hasattr(request, "form"):
            form = request.form()
            if "csrf_token" in form:
                return form["csrf_token"]
        
        # Check query parameters (less secure, but sometimes needed)
        token = request.query_params.get("csrf_token")
        if token:
            return token
        
        return None
    
    def is_protected_path(self, path: str) -> bool:
        """Check if path requires CSRF protection."""
        # Skip public paths
        if path in PUBLIC_PATHS:
            return False
        
        # Skip paths that start with public prefixes
        for public_path in PUBLIC_PATHS:
            if path.startswith(public_path):
                return False
        
        return True
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Process request with CSRF checking."""
        path = request.url.path
        method = request.method
        
        # Only protect state-changing methods
        if method not in PROTECTED_METHODS:
            return await call_next(request)
        
        # Skip public paths
        if not self.is_protected_path(path):
            return await call_next(request)
        
        # Skip OPTIONS (CORS preflight)
        if method == "OPTIONS":
            return await call_next(request)
        
        # Get CSRF token from request
        token = self.get_token_from_request(request)
        
        if not token:
            logger.warning(f"CSRF token missing for {method} {path}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token required"
            )
        
        # In production, validate token against session/cache
        # For now, just check that token exists and has correct format
        if len(token) < self.token_length:
            logger.warning(f"Invalid CSRF token format for {method} {path}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid CSRF token"
            )
        
        # Add token to request state for downstream use
        request.state.csrf_token = token
        
        return await call_next(request)


def generate_csrf_token() -> str:
    """Generate a CSRF token for use in forms."""
    return secrets.token_urlsafe(32)

