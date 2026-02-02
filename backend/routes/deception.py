"""
Deception Layer (Daena Personal Shield – "empty nests").

Decoy routes that look real but only log and alert. No sensitive data.
When an attacker touches these endpoints, we record request metadata and
emit security.deception_hit for monitoring/containment.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import APIRouter, Request, Depends

router = APIRouter(prefix="/api/v1/_decoy", tags=["deception"])
logger = logging.getLogger(__name__)

# In-memory hit log (for dashboard; in production use DB or SIEM)
_deception_hits: list = []


def _log_hit(request: Request, path: str, method: str, label: str) -> None:
    """Log decoy access and emit event for Guardian/monitoring."""
    client_host = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for") or client_host
    ua = request.headers.get("user-agent") or ""
    hit = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "path": path,
        "method": method,
        "label": label,
        "client_host": client_host,
        "x_forwarded_for": forwarded,
        "user_agent": ua[:200],
    }
    _deception_hits.append(hit)
    if len(_deception_hits) > 500:
        _deception_hits.pop(0)
    logger.warning("[DECOY HIT] %s %s %s from %s", method, path, label, forwarded)
    try:
        from backend.routes.events import emit
        emit("security.deception_hit", hit)
    except Exception:
        pass
    try:
        from backend.services.security_containment import on_deception_hit
        on_deception_hit(hit)
    except Exception:
        pass


@router.get("/admin")
async def decoy_admin(request: Request) -> Dict[str, Any]:
    """Decoy admin panel – looks like login; only logs."""
    _log_hit(request, "/api/v1/_decoy/admin", "GET", "decoy_admin")
    return {"message": "Unauthorized", "login_url": "/login"}


@router.post("/admin/login")
async def decoy_admin_login(request: Request) -> Dict[str, Any]:
    """Decoy admin login – logs credential stuffing attempts."""
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    _log_hit(request, "/api/v1/_decoy/admin/login", "POST", "decoy_admin_login")
    return {"success": False, "error": "Invalid credentials"}


@router.get("/api/keys")
async def decoy_api_keys(request: Request) -> Dict[str, Any]:
    """Decoy API keys endpoint – honeytoken style."""
    _log_hit(request, "/api/v1/_decoy/api/keys", "GET", "decoy_api_keys")
    return {"keys": []}


@router.get("/env")
async def decoy_env(request: Request) -> Dict[str, Any]:
    """Decoy env/config – canary; no real env."""
    _log_hit(request, "/api/v1/_decoy/env", "GET", "decoy_env")
    return {"APP_ENV": "production", "DEBUG": "false"}


@router.get("/hits")
async def get_deception_hits(limit: int = 100) -> Dict[str, Any]:
    """Return recent decoy hits (for Incident Room / Guardian). Auth in production."""
    recent = list(reversed(_deception_hits[-limit:]))
    return {"hits": recent, "total": len(_deception_hits)}
