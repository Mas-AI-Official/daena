"""
Kill-Switch Middleware for Daena AI VP.
Blocks all requests when kill-switch is active (except kill-switch management endpoints).
"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class KillSwitchMiddleware(BaseHTTPMiddleware):
    """
    Middleware that blocks all requests when kill-switch is active.
    
    Exceptions:
    - Kill-switch management endpoints (/api/v1/security/kill-switch/*)
    - Health check endpoints (/health, /api/v1/health)
    """
    
    # Endpoints that are always allowed (even when kill-switch is active)
    ALLOWED_PATHS = [
        "/api/v1/security/kill-switch/status",
        "/api/v1/security/kill-switch/activate",
        "/api/v1/security/kill-switch/deactivate",
        "/health",
        "/api/v1/health",
        "/docs",
        "/openapi.json",
        "/redoc"
    ]
    
    async def dispatch(self, request: Request, call_next):
        # Check if kill-switch is active
        try:
            from backend.services.threat_detection import threat_detector
            
            # Allow kill-switch management endpoints
            if any(request.url.path.startswith(path) for path in self.ALLOWED_PATHS):
                return await call_next(request)
            
            # Check if kill-switch is active
            if threat_detector.is_kill_switch_active():
                status_info = threat_detector.get_kill_switch_status()
                
                logger.critical(
                    f"Request blocked by kill-switch: {request.method} {request.url.path} "
                    f"(Reason: {status_info.get('reason', 'Unknown')})"
                )
                
                return JSONResponse(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    content={
                        "error": "service_unavailable",
                        "message": "System is currently unavailable due to security kill-switch activation",
                        "reason": status_info.get("reason", "Security emergency"),
                        "activated_at": status_info.get("activated_at"),
                        "activated_by": status_info.get("activated_by"),
                        "contact": "masoud.masoori@mas-ai.co"
                    }
                )
        except ImportError:
            # If threat_detector is not available, allow requests (graceful degradation)
            logger.warning("Kill-switch middleware: threat_detector not available, allowing requests")
        except Exception as e:
            # On any error, log but allow request (fail open for availability)
            logger.error(f"Kill-switch middleware error: {e}, allowing request")
        
        # Continue with request
        return await call_next(request)





