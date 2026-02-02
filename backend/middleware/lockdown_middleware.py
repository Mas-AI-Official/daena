"""
Lockdown Middleware – when SECURITY_LOCKDOWN_MODE or runtime lockdown is active,
reject non-whitelisted requests with 503 so operators can contain the system
and still use Incident Room / unlock.
"""

import logging
from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# Paths allowed during lockdown (so users can see UI, check status, and unlock)
LOCKDOWN_ALLOWED_PATHS = [
    "/health",
    "/api/v1/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/favicon.ico",
    "/",
    "/static",
    "/ui",
    "/incident-room",
    "/api/v1/qa/ui",
    "/api/v1/founder-panel/system/emergency/status",
    "/api/v1/founder-panel/system/emergency/unlock",
    "/api/v1/_decoy/hits",
    "/api/v1/security/containment",
    "/cmp-canvas",
    "/control-center",
]


def _is_allowed(path: str) -> bool:
    for allowed in LOCKDOWN_ALLOWED_PATHS:
        if allowed == "/":
            if path == "/":
                return True
        elif path == allowed or path.startswith(allowed + "/"):
            return True
    return False


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


async def lockdown_middleware(request: Request, call_next):
    # Block requests from containment blocklist (403)
    try:
        from backend.services.security_containment import is_blocked
        ip = _client_ip(request)
        if ip and is_blocked(ip):
            logger.warning("[LOCKDOWN] Blocked request from blocked IP: %s %s", request.method, request.url.path)
            return JSONResponse(
                status_code=403,
                content={"detail": "Access denied (IP blocked by security containment).", "blocked": True},
            )
    except Exception:
        pass

    try:
        from backend.config.security_state import is_lockdown_active
        if not is_lockdown_active():
            return await call_next(request)
    except Exception:
        return await call_next(request)

    path = request.url.path
    if _is_allowed(path):
        return await call_next(request)

    logger.warning("[LOCKDOWN] Blocked %s %s", request.method, path)
    return JSONResponse(
        status_code=503,
        content={
            "detail": "System in lockdown. Only status, unlock, and Incident Room are available.",
            "lockdown": True,
            "retry_after": "Clear lockdown via Incident Room or POST /api/v1/founder-panel/system/emergency/unlock",
        },
        headers={"Retry-After": "60"},
    )
