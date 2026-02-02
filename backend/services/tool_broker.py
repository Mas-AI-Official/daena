"""
Tool broker: allowlist + risk scoring. MEDIUM+ requires approval before sending to OpenClaw.
Emergency stop (env) blocks all tool execution.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

# Risk levels
LOW = "low"
MEDIUM = "medium"
HIGH = "high"
CRITICAL = "critical"

# Allowlist: action type -> risk. LOW: auto-allow (if automation allows). MEDIUM+: queue for approval.
# Moltbot-style + Daena-unique: desktop, crypto, defi.
ACTION_RISK: Dict[str, str] = {
    "browser.navigate": LOW,
    "browser.screenshot": LOW,
    "screenshot": LOW,
    "desktop.click": MEDIUM,
    "desktop.type": MEDIUM,
    "filesystem.list": LOW,
    "filesystem.read": LOW,
    "filesystem.download": MEDIUM,
    "filesystem.write": HIGH,
    "workspace_index": LOW,
    "workspace_search": LOW,
    "workspace.write": MEDIUM,
    "terminal.run": HIGH,
    "shell_exec": HIGH,
    "crypto.dashboard": LOW,
    "defi.scan": LOW,
    "defi.health": LOW,
    "system.modify": CRITICAL,
}


def _emergency_stop() -> bool:
    try:
        from backend.config.settings import settings
        return getattr(settings, "daena_emergency_stop", False)
    except Exception:
        import os
        return (os.environ.get("DAENA_EMERGENCY_STOP", "").lower() in ("true", "1", "yes"))


def _automation_mode() -> str:
    try:
        from backend.config.settings import settings
        return (getattr(settings, "daena_tool_automation", "low_only") or "low_only").lower()
    except Exception:
        import os
        return (os.environ.get("DAENA_TOOL_AUTOMATION", "low_only") or "low_only").lower()


def get_risk_level(action: Dict[str, Any]) -> str:
    """Return risk level for action (action_type or tool_name)."""
    action_type = (action.get("action_type") or action.get("tool_name") or action.get("type") or "").strip().lower()
    return ACTION_RISK.get(action_type, MEDIUM)


def requires_approval(risk_level: str) -> bool:
    return risk_level in (MEDIUM, HIGH, CRITICAL)


def broker_request(
    action: Dict[str, Any],
    requested_by: str = "daena",
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Input: requested tool action.
    Output: ("approved_and_executed", result) or ("queued_for_approval", { request_id, message }).
    Enforces allowlist + risk. Emergency stop blocks all.
    """
    if _emergency_stop():
        try:
            from backend.routes.audit import log_audit_entry
            log_audit_entry(requested_by, "tool_request", "submit", False, "Emergency stop active", {})
        except Exception:
            pass
        return ("blocked", {"error": "Emergency stop active. Set DAENA_EMERGENCY_STOP=false to allow execution."})

    risk = get_risk_level(action)
    mode = _automation_mode()

    if mode == "off":
        try:
            from backend.routes.audit import log_audit_entry
            log_audit_entry(requested_by, "tool_request", "submit", False, "Tool automation off", {})
        except Exception:
            pass
        return ("blocked", {"error": "Tool automation is off. Set DAENA_TOOL_AUTOMATION=low_only or on."})

    if requires_approval(risk):
        from backend.services.tool_request_store import create_request
        req_id = create_request(requested_by=requested_by, risk_level=risk, action_json=action)
        try:
            from backend.routes.audit import log_audit_entry
            log_audit_entry(
                actor=requested_by,
                resource="tool_request",
                action="submit",
                allowed=True,
                reason="queued_for_approval",
                context={"request_id": req_id, "risk_level": risk},
            )
        except Exception:
            pass
        return ("queued_for_approval", {"request_id": req_id, "risk_level": risk, "message": "Requires founder approval in DaenaBot Tools panel."})

    if risk == LOW and mode in ("low_only", "on"):
        # Sync path: cannot await; caller should use async_broker_request from async code
        return ("queued_for_approval", {"request_id": None, "message": "Use async_broker_request from async context for low-risk execution."})

    return ("queued_for_approval", {"request_id": None, "risk_level": risk, "message": "Requires approval."})


async def async_broker_request(
    action: Dict[str, Any],
    requested_by: str = "daena",
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Async version: safe to call from async routes (chat, stream).
    Returns ("approved_and_executed", result), ("queued_for_approval", {request_id?, message}), or ("blocked", {error}).
    """
    if _emergency_stop():
        return ("blocked", {"error": "Emergency stop active. Set DAENA_EMERGENCY_STOP=false to allow execution."})

    risk = get_risk_level(action)
    mode = _automation_mode()

    if mode == "off":
        return ("blocked", {"error": "Tool automation is off. Set DAENA_TOOL_AUTOMATION=low_only or on."})

    if requires_approval(risk):
        from backend.services.tool_request_store import create_request
        req_id = create_request(requested_by=requested_by, risk_level=risk, action_json=action)
        try:
            from backend.routes.audit import log_audit_entry
            log_audit_entry(
                actor=requested_by,
                resource="tool_request",
                action="submit",
                allowed=True,
                reason="queued_for_approval",
                context={"request_id": req_id, "risk_level": risk},
            )
        except Exception:
            pass
        try:
            from backend.config.branding import get_daena_bot_display_name
            name = get_daena_bot_display_name()
        except Exception:
            name = "DaenaBot"
        return ("queued_for_approval", {"request_id": req_id, "risk_level": risk, "message": f"Requires founder approval in {name} Tools panel."})

    if risk == LOW and mode in ("low_only", "on"):
        try:
            from backend.integrations.openclaw_gateway_client import get_openclaw_client
            client = get_openclaw_client()
            if not client.is_connected:
                ok = await client.connect()
                if not ok:
                    return ("queued_for_approval", {"request_id": None, "message": "DaenaBot Hands gateway not available. Check Control Pannel → DaenaBot Tools."})
            result = await client.execute_tool(action)
            try:
                from backend.routes.audit import log_audit_entry
                log_audit_entry(
                    actor=requested_by,
                    resource="tool_request",
                    action="execute",
                    allowed=bool(result.get("success")),
                    reason="low_risk_auto",
                    context={"risk_level": risk},
                )
            except Exception:
                pass
            if result.get("success"):
                return ("approved_and_executed", result)
            return ("approved_and_executed", {"success": False, "error": result.get("error", "Unknown error")})
        except Exception as e:
            logger.warning("Tool broker execute failed: %s", e)
            return ("queued_for_approval", {"request_id": None, "message": f"Execution failed: {e}. Approve from DaenaBot Tools panel."})

    return ("queued_for_approval", {"request_id": None, "risk_level": risk, "message": "Requires approval."})


async def execute_approved_request(req_id: str) -> Dict[str, Any]:
    """After approval, run the request via OpenClaw and update store."""
    from backend.services.tool_request_store import get_request, update_status
    req = get_request(req_id)
    if not req or req.get("status") != "pending":
        return {"success": False, "error": "Request not found or not pending"}
    action = req.get("action_json") or {}
    try:
        from backend.integrations.openclaw_gateway_client import get_openclaw_client
        client = get_openclaw_client()
        if not client.is_connected:
            await client.connect()
        result = await client.execute_tool(action)
        update_status(req_id, "approved" if result.get("success") else "failed", result)
        try:
            from backend.routes.audit import log_audit_entry
            requested_by = (req.get("requested_by") or "daena")
            log_audit_entry(
                actor="founder",
                resource="tool_request",
                action="execute",
                allowed=bool(result.get("success")),
                reason="approved_request",
                context={"request_id": req_id, "requested_by": requested_by},
            )
        except Exception:
            pass
        return result
    except Exception as e:
        update_status(req_id, "failed", {"success": False, "error": str(e)})
        try:
            from backend.routes.audit import log_audit_entry
            log_audit_entry("founder", "tool_request", "execute", False, str(e), {"request_id": req_id})
        except Exception:
            pass
        return {"success": False, "error": str(e)}
