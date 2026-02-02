"""
Live capability registry for Daena: tools, Hands, local LLM, governance.
Used by GET /api/v1/system/capabilities and awareness UI.
No deletion of exports without updating callers (see docs/FRONTEND_BACKEND_WIRING_AUDIT.md).
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Tool catalog Daena can call (browser, shell, filesystem, web, etc.)
TOOL_CATALOG = [
    {"id": "browser.navigate", "name": "Browser navigate", "risk": "low", "requires_approval": False},
    {"id": "browser.screenshot", "name": "Browser screenshot", "risk": "low", "requires_approval": False},
    {"id": "filesystem.list", "name": "List directory", "risk": "low", "requires_approval": False},
    {"id": "filesystem.read", "name": "Read file", "risk": "low", "requires_approval": False},
    {"id": "workspace_index", "name": "Workspace index", "risk": "low", "requires_approval": False},
    {"id": "workspace_search", "name": "Workspace search", "risk": "low", "requires_approval": False},
    {"id": "filesystem.download", "name": "Download file", "risk": "medium", "requires_approval": True},
    {"id": "filesystem.write", "name": "Write file", "risk": "high", "requires_approval": True},
    {"id": "terminal.run", "name": "Run terminal command", "risk": "high", "requires_approval": True},
    {"id": "shell_exec", "name": "Shell execution", "risk": "high", "requires_approval": True},
]


def _hands_url_host() -> str:
    """Return host from DAENABOT_HANDS_URL or OPENCLAW_GATEWAY_URL."""
    try:
        from backend.integrations.openclaw_gateway_client import _default_url
        url = _default_url()
    except Exception:
        url = os.environ.get("DAENABOT_HANDS_URL") or os.environ.get("OPENCLAW_GATEWAY_URL") or "ws://127.0.0.1:18789/ws"
    try:
        parsed = urlparse(url)
        return (parsed.hostname or "").strip().lower()
    except Exception:
        return ""


def _remote_hands_warning() -> bool:
    """True if Hands URL is not localhost and ENABLE_REMOTE_HANDS is not set."""
    host = _hands_url_host()
    if not host or host in ("127.0.0.1", "localhost", "::1"):
        return False
    return (os.environ.get("ENABLE_REMOTE_HANDS", "").strip().lower() not in ("true", "1", "yes"))


async def _check_hands_gateway(timeout_sec: float = 2.0) -> Dict[str, Any]:
    """Quick WebSocket connect test to Hands gateway. Returns available, connected, authenticated, token_present (never token value)."""
    out = {"available": False, "connected": False, "authenticated": False, "token_present": False, "url_host": _hands_url_host()}
    try:
        from backend.integrations.openclaw_gateway_client import get_openclaw_client, _default_token
        token = _default_token()
        out["token_present"] = bool(token and str(token).strip())
        client = get_openclaw_client()
        # Use short timeout for awareness check
        client.timeout_sec = timeout_sec
        connected = await asyncio.wait_for(client.connect(), timeout=timeout_sec)
        out["connected"] = connected
        out["authenticated"] = getattr(client, "is_authenticated", False) or (connected and not out["token_present"])
        out["available"] = out["connected"]
        try:
            await client.disconnect()
        except Exception:
            pass
    except asyncio.TimeoutError:
        out["error"] = "timeout"
    except Exception as e:
        out["error"] = str(e)
    return out


async def _check_local_llm() -> Dict[str, Any]:
    """Detect local LLM provider (Ollama / LM Studio) and health."""
    out = {"provider": None, "healthy": False, "model": None}
    try:
        from backend.services.local_llm_ollama import check_ollama_available, get_ollama_base_url
        ok = await check_ollama_available()
        if ok:
            out["provider"] = "ollama"
            out["healthy"] = True
            try:
                base = await get_ollama_base_url()
                out["base_url"] = base.rstrip("/") if base else None
            except Exception:
                pass
            # Optionally list one model
            try:
                import httpx
                base = await get_ollama_base_url()
                async with httpx.AsyncClient(timeout=3) as client:
                    r = await client.get(f"{base.rstrip('/')}/api/tags")
                    if r.status_code == 200:
                        data = r.json()
                        models = data.get("models") or []
                        if models:
                            out["model"] = models[0].get("name") if isinstance(models[0], dict) else str(models[0])
            except Exception:
                pass
        return out
    except ImportError:
        out["error"] = "ollama module not available"
        return out
    except Exception as e:
        out["error"] = str(e)
        return out


def _governance_profile() -> Dict[str, Any]:
    """Current governance: autopilot, auto-approve threshold, pending count."""
    try:
        from backend.services.governance_loop import get_governance_loop
        loop = get_governance_loop()
        stats = loop.get_stats()
        return {
            "autopilot_enabled": getattr(loop, "autopilot", True),
            "auto_approve_threshold": "low" if getattr(loop, "autopilot", True) else "none",
            "pending_count": len(loop.get_pending()),
            **stats,
        }
    except Exception as e:
        return {"autopilot_enabled": True, "auto_approve_threshold": "low", "pending_count": 0, "error": str(e)}


def _version_build() -> Dict[str, Any]:
    """Optional version/build info (git sha, build time)."""
    out = {"version": "2.0.0"}
    try:
        import subprocess
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        )
        if r.returncode == 0 and r.stdout:
            out["git_sha"] = r.stdout.strip()
    except Exception:
        pass
    return out


async def build_capabilities() -> Dict[str, Any]:
    """
    Build live capabilities JSON: available, enabled, requires_approval, health.
    Used by GET /api/v1/system/capabilities and awareness UI.
    """
    hands = await _check_hands_gateway(2.0)
    local_llm = await _check_local_llm()
    governance = _governance_profile()
    version = _version_build()

    remote_warning = _remote_hands_warning()
    if remote_warning:
        hands["remote_hands_warning"] = True
        hands["message"] = "Hands URL is not localhost. Set ENABLE_REMOTE_HANDS=true to acknowledge."

    return {
        "success": True,
        "available": {
            "hands_gateway": hands.get("available", False),
            "local_llm": local_llm.get("healthy", False),
            "tool_catalog": True,
        },
        "enabled": {
            "hands_gateway": hands.get("connected", False),
            "local_llm": local_llm.get("healthy", False),
            "tools": True,
        },
        "requires_approval": [t["id"] for t in TOOL_CATALOG if t.get("requires_approval")],
        "health": {
            "hands": hands,
            "local_llm": local_llm,
            "governance": governance,
        },
        "tool_catalog": TOOL_CATALOG,
        "governance": governance,
        "version": version,
        "remote_hands_warning": remote_warning,
    }
