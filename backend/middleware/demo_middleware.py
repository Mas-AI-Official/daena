"""
Demo Mode Middleware
Blocks dangerous endpoints when DEMO_MODE=1 or DEMO_AUTH_ENABLED=true
"""
import os
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import logging

logger = logging.getLogger(__name__)

# Endpoints blocked in demo mode
BLOCKED_ENDPOINTS = [
    # Founder/Admin endpoints
    "/api/v1/founder-panel",
    "/api/v1/system/reset",
    "/api/v1/system/emergency",
    
    # Dangerous operations
    "/api/v1/agents/delete",
    "/api/v1/departments/delete",
    "/api/v1/council/delete",
    
    # File system access
    "/api/v1/filesystem",
    "/api/v1/files/write",
    "/api/v1/files/delete",
    
    # Admin tools
    "/api/v1/admin",
    "/api/v1/config/write",
    "/api/v1/secrets",
    
    # Hidden departments (founder only)
    "/hidden-departments",
    
    # Database direct access
    "/api/v1/db/",
    "/api/v1/sql/",
]

# Endpoints allowed even without auth in demo
DEMO_ALLOWED_ENDPOINTS = [
    "/demo",
    "/api/v1/demo",
    "/api/v1/health",
    "/api/v1/brain/status",
    "/api/v1/brain/models",
    "/api/v1/daena/chat",
    "/api/v1/daena/status",
    "/api/v1/voice/status",
    "/api/v1/tools/search",
    "/api/v1/tools/providers",
    "/static/",
    "/favicon",
]


def is_demo_mode() -> bool:
    """Check if running in demo mode"""
    return (
        os.getenv("DEMO_MODE", "0") in ("1", "true", "True") or
        os.getenv("DEMO_AUTH_ENABLED", "false").lower() == "true"
    )


def is_blocked_in_demo(path: str) -> bool:
    """Check if a path is blocked in demo mode"""
    path_lower = path.lower()
    for blocked in BLOCKED_ENDPOINTS:
        if blocked.lower() in path_lower:
            return True
    return False


def is_allowed_in_demo(path: str) -> bool:
    """Check if a path is allowed in demo without restrictions"""
    path_lower = path.lower()
    for allowed in DEMO_ALLOWED_ENDPOINTS:
        if path_lower.startswith(allowed.lower()):
            return True
    return False


class DemoModeMiddleware(BaseHTTPMiddleware):
    """
    Middleware that restricts access to dangerous endpoints in demo mode.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip if not in demo mode
        if not is_demo_mode():
            return await call_next(request)
        
        path = request.url.path
        
        # Always allow demo-specific endpoints
        if is_allowed_in_demo(path):
            return await call_next(request)
        
        # Block dangerous endpoints
        if is_blocked_in_demo(path):
            logger.warning(f"Demo mode blocked access to: {path}")
            return JSONResponse(
                status_code=403,
                content={
                    "success": False,
                    "error": "This endpoint is restricted in demo mode",
                    "demo_mode": True,
                    "path": path
                }
            )
        
        # Allow all other endpoints
        return await call_next(request)


def register_demo_middleware(app):
    """Register the demo mode middleware with the app"""
    if is_demo_mode():
        app.add_middleware(DemoModeMiddleware)
        logger.info("🔒 Demo mode middleware enabled - dangerous endpoints blocked")
    else:
        logger.info("⚡ Running in full mode - all endpoints accessible")
