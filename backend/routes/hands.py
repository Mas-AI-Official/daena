"""
DaenaBot Hands status: configured, reachable (Control UI), url (redacted), message.
GET /api/v1/hands/status — for UI "DaenaBot Hands: Connected/Disconnected" and Test button.
Token is never logged or returned.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/hands", tags=["hands"])

# Module-level cache for last_check (optional; can be updated by a background task)
_last_check_ts: str | None = None
_last_reachable: bool = False


def _hands_url() -> str | None:
    """URL from DAENABOT_HANDS_URL or OPENCLAW_GATEWAY_URL. Never return token."""
    try:
        from backend.config.settings import env_first
        return env_first("DAENABOT_HANDS_URL", "OPENCLAW_GATEWAY_URL", default=None) or None
    except Exception:
        import os
        u = os.environ.get("DAENABOT_HANDS_URL") or os.environ.get("OPENCLAW_GATEWAY_URL")
        return (u or "").strip() or None


def _hands_token() -> Optional[str]:
    """Token from DAENABOT_HANDS_TOKEN or OPENCLAW_GATEWAY_TOKEN. Used only to check configured; never logged."""
    try:
        from backend.config.settings import env_first
        return env_first("DAENABOT_HANDS_TOKEN", "OPENCLAW_GATEWAY_TOKEN", default=None)
    except Exception:
        import os
        t = os.environ.get("DAENABOT_HANDS_TOKEN") or os.environ.get("OPENCLAW_GATEWAY_TOKEN")
        return (t or "").strip() or None


def _control_ui_base_url(ws_url: str | None) -> str | None:
    """Derive Control UI HTTP base from WS URL (e.g. ws://127.0.0.1:18789/ws -> http://127.0.0.1:18789/)."""
    if not ws_url or not ws_url.strip():
        return None
    u = ws_url.strip().lower()
    if u.startswith("ws://"):
        u = "http://" + u[5:]
    elif u.startswith("wss://"):
        u = "https://" + u[6:]
    else:
        return None
    # Remove path (e.g. /ws)
    if "/" in u.split("//", 1)[-1]:
        u = u.rsplit("/", 1)[0] + "/"
    else:
        u = u.rstrip("/") + "/"
    return u


def _check_reachable(base_url: Optional[str]) -> bool:
    """Return True if Control UI at base_url responds (e.g. http://127.0.0.1:18789/)."""
    if not base_url:
        return False
    try:
        import urllib.request
        req = urllib.request.Request(base_url, method="GET")
        req.add_header("User-Agent", "Daena-Hands-Status/1")
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status in (200, 302, 401)
    except Exception:
        return False


@router.get("/status")
async def hands_status() -> Dict[str, Any]:
    """
    Hands awareness: configured (URL+token set), reachable (Control UI HTTP),
    url (redacted: host:port only), last_check (iso8601), message.
    Token is never included or logged.
    """
    global _last_check_ts, _last_reachable
    url = _hands_url()
    token = _hands_token()
    configured = bool(url and url.strip() and token and str(token).strip())
    # Redact URL for response: show only scheme+host+port (no path, no token)
    display_url = "(not set)"
    if url:
        u = url.strip().lower()
        if "://" in u:
            rest = u.split("://", 1)[-1]
            host_part = rest.split("/")[0]
            display_url = u.split("://")[0] + "://" + host_part + "/"
        else:
            display_url = url[:50] + "..." if len(url) > 50 else url
    base = _control_ui_base_url(url)
    reachable = _check_reachable(base) if base else False
    _last_check_ts = datetime.now(timezone.utc).isoformat()
    _last_reachable = reachable
    if configured and reachable:
        message = "DaenaBot Hands: Connected"
    elif configured and not reachable:
        message = "DaenaBot Hands: Configured but Control UI unreachable"
    else:
        message = "DaenaBot Hands: Not configured (set DAENABOT_HANDS_URL and DAENABOT_HANDS_TOKEN)"
    return {
        "configured": configured,
        "reachable": reachable,
        "url": display_url,
        "last_check": _last_check_ts,
        "message": message,
    }
@router.post("/execute")
async def execute_hands_action(payload: Dict[str, Any]):
    """Execute a Hands action via the gateway, subject to governance."""
    action_name = payload.get("action")
    args = payload.get("args", {})
    
    if not action_name:
        return {"success": False, "error": "Missing action name"}
        
    # Use ToolBroker for risk assessment and approval gating
    from backend.services.tool_broker import async_broker_request
    
    # Map high-level action to ToolBroker action
    broker_action = {
        "action_type": action_name,
        "parameters": args,
        "source": "hands"
    }
    
    status, result = await async_broker_request(broker_action, requested_by="founder")
    
    if status == "queued_for_approval":
        return {
            "success": False,
            "status": "pending_approval",
            "request_id": result.get("request_id"),
            "message": result.get("message")
        }
    
    if status == "blocked":
        return {"success": False, "error": result.get("error")}
        
    return result

@router.post("/allowlist")
async def update_hands_allowlist(config: Dict[str, Any]):
    """Update Hands allowlist configuration (stored in SystemConfig)."""
    from backend.database import SessionLocal, SystemConfig
    db = SessionLocal()
    try:
        # Save to DB
        existing = db.query(SystemConfig).filter(SystemConfig.key == "hands_allowlist").first()
        if existing:
            existing.value_json = config
        else:
            new_conf = SystemConfig(key="hands_allowlist", value_json=config)
            db.add(new_conf)
        db.commit()
        return {"success": True, "message": "Allowlist updated"}
    finally:
        db.close()
