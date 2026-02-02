"""
Daena Windows Node client.
Calls local node at configurable URL (default http://127.0.0.1:18888).
Requires X-Windows-Node-Token header when token is set.
URL and token can be stored in SystemConfig (key windows_node_config) so UI can pair without editing .env.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_NODE_URL = "http://127.0.0.1:18888"
TIMEOUT = 30.0
_CONFIG_KEY = "windows_node_config"


def _get_node_config() -> Dict[str, Any]:
    """Read Windows Node URL and token from DB (SystemConfig)."""
    try:
        from backend.database import SessionLocal, SystemConfig
        db = SessionLocal()
        try:
            row = db.query(SystemConfig).filter(SystemConfig.config_key == _CONFIG_KEY).first()
            if row and row.config_value:
                data = json.loads(row.config_value) if isinstance(row.config_value, str) else row.config_value
                if isinstance(data, dict):
                    return data
        finally:
            db.close()
    except Exception as e:
        logger.warning("windows_node_config read failed: %s", e)
    return {}


def save_node_config(url: Optional[str] = None, token: Optional[str] = None) -> None:
    """Persist Windows Node URL and/or token to SystemConfig (for Pair Node UI). Omitted args (None) leave existing value unchanged."""
    from datetime import datetime
    from backend.database import SessionLocal, SystemConfig
    data = dict(_get_node_config())
    if url is not None:
        data["url"] = (url or "").strip()
    if token is not None:
        data["token"] = (token or "").strip()
    import json
    json_val = json.dumps(data)
    db = SessionLocal()
    try:
        row = db.query(SystemConfig).filter(SystemConfig.config_key == _CONFIG_KEY).first()
        if row:
            row.config_value = json_val
            row.updated_at = datetime.utcnow()
        else:
            row = SystemConfig(
                config_key=_CONFIG_KEY,
                config_value=json_val,
                config_type="json",
                description="Windows Node URL and token (Pair Node)",
            )
            db.add(row)
        db.commit()
    finally:
        db.close()


def get_node_url() -> str:
    cfg = _get_node_config()
    url = (cfg.get("url") or "").strip()
    if url:
        return url
    from backend.config.settings import settings
    return getattr(settings, "windows_node_url", None) or DEFAULT_NODE_URL


def get_node_token() -> Optional[str]:
    cfg = _get_node_config()
    token = (cfg.get("token") or "").strip()
    if token:
        return token
    import os
    return os.environ.get("WINDOWS_NODE_TOKEN") or None


async def node_health() -> Dict[str, Any]:
    """GET /node/health - check if Windows node is reachable."""
    url = get_node_url().rstrip("/") + "/node/health"
    token = get_node_token()
    headers = {}
    if token:
        headers["X-Windows-Node-Token"] = token
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(url, headers=headers or None)
            r.raise_for_status()
            return r.json() if r.content else {"status": "ok"}
    except Exception as e:
        logger.warning("Windows node health check failed: %s", e)
        return {"status": "error", "error": str(e)}


async def node_run_tool(tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """POST /node/run_tool - run a tool on the Windows node."""
    url = get_node_url().rstrip("/") + "/node/run_tool"
    token = get_node_token()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Windows-Node-Token"] = token
    body = {"tool_name": tool_name, "args": args}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.post(url, json=body, headers=headers)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as e:
        return {"status": "error", "error": f"HTTP {e.response.status_code}: {e.response.text[:500]}"}
    except Exception as e:
        return {"status": "error", "error": str(e)}
