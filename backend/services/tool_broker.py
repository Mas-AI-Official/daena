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
    """Return risk level for action. Checks SkillRegistry first, then hardcoded list."""
    action_type = (action.get("action_type") or action.get("tool_name") or action.get("type") or "").strip().lower()
    
    # Check Skill Registry
    try:
        from backend.services.skill_registry import get_skill_registry
        reg = get_skill_registry()
        skill = reg.get_skill_by_name(action_type)
        if skill:
            return skill.get("risk_level", MEDIUM)
    except Exception:
        pass
        
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


async def _execute_fallback(action: Dict[str, Any], requested_by: str) -> Dict[str, Any]:
    """Fallback execution if OpenClaw is not available."""
    action_type = action.get("action_type", "")
    params = action.get("parameters", {})
    
    logger.info(f"Attempting fallback execution for {action_type}")

    # 1. Native Unified Tools (browser, etc)
    if action_type.startswith("browser."):
        from backend.services.unified_tool_executor import unified_executor
        tool_action = action_type.split(".")[-1]
        try:
            # Browser actions usually safe enough to run if they were approved/low risk
            res = await unified_executor.execute("browser", tool_action, params, requested_by, skip_approval=True)
            return {"success": True, "result": res.get("result"), "fallback": True}
        except Exception as e:
            logger.error(f"Fallback browser exec failed: {e}")
            return {"success": False, "error": f"Fallback failed: {e}"}

    # 2. Simple Filesystem (Read-only list for testing)
    if action_type == "filesystem.list":
        path = params.get("path", ".")
        try:
            import os
            files = []
            if os.path.exists(path) and os.path.isdir(path):
                items = os.listdir(path)
                for f in items[:50]: # limit
                    files.append({"name": f, "is_dir": os.path.isdir(os.path.join(path, f))})
                if len(items) > 50:
                    files.append({"name": "... (truncated)", "is_dir": False})
            return {"success": True, "result": files}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    # 3. Shell (echo only for test)
    if action_type == "shell.run":
        cmd = params.get("command", "")
        if cmd.startswith("echo "):
             return {"success": True, "result": cmd[5:]}

    return {"success": False, "error": "Not connected to OpenClaw Gate and no local fallback available."}

async def async_broker_request(action: Dict[str, Any], requested_by: str = "unknown") -> Tuple[str, Optional[Dict[str, Any]]]:
    """
    Process a request: check risk, check allowlist, check automation.
    Returns (status, result_json).
    Status: 'executed', 'queued_for_approval', 'blocked', 'error'
    """
    from backend.services.tool_request_store import create_request
    from backend.routes.audit import log_audit_entry as log_execution_audit

    # 1. Check Emergency Stop
    if _check_emergency_stop():
         try:
             log_execution_audit(requested_by, "tool_request", "submit", False, "Emergency Stop ACTIVE", {})
         except Exception: pass
         return ("blocked", {"message": "Emergency Stop is ACTIVE. All tools blocked."})

    # 2. Check Hands Allowlist
    allowed, reason = _check_hands_allowlist(action)
    if not allowed:
         try:
             log_execution_audit(requested_by, "tool_request", "submit", False, f"Allowlist Block: {reason}", {})
         except Exception: pass
         return ("blocked", {"message": f"Action blocked by Hands Allowlist: {reason}"})

    # 3. Determine Risk
    risk = get_risk_level(action)
    
    # 3.1 Security Check: Critical Risk Block
    if os.getenv("GOVERNANCE_BLOCK_CRITICAL_RISK", "true").lower() == "true":
        if risk == CRITICAL:
             return ("blocked", {"message": "CRITICAL risk tasks are blocked by governance policy"})

    # 3.2 Security Check: Execution Token
    if os.getenv("EXECUTION_TOKEN_REQUIRED", "false").lower() == "true":
        token = action.get("execution_token") 
        # Note: If action comes from frontend, token might be in headers/metadata, 
        # but here we assume it's passed in action dict or we need another way.
        # For now, let's assume it's in action['execution_token']
        
        if not token:
             # If auth is disabled, maybe we skip? No, EXECUTION_TOKEN_REQUIRED is explicit.
             return ("blocked", {"message": "Execution token required"})
             
        # For HIGH risk, require founder approval token
        if risk in [HIGH, CRITICAL]: # CRITICAL usually blocked above, but if allowed...
             from backend.security.auth import require_founder_approval
             if not require_founder_approval(token):
                  return ("blocked", {"message": "Founder approval token required for HIGH risk task"})

    
    # 4. Check Automation Policy
    mode = _automation_mode()
    requires_approval = True
    
    if mode == "on":
        requires_approval = False
    elif mode == "low_only" and risk == LOW:
        requires_approval = False
    elif mode == "off":
        requires_approval = True
        
    if risk == HIGH and mode != "on":
        requires_approval = True

    # 5. Execute or Queue
    if requires_approval:
        req_id = create_request(requested_by=requested_by, risk_level=risk, action_json=action)
        try:
             log_execution_audit(requested_by, "tool_request", "submit", True, "queued_for_approval", {"request_id": req_id, "risk": risk})
        except Exception: pass
        
        try:
            from backend.config.branding import get_daena_bot_display_name
            name = get_daena_bot_display_name()
        except Exception:
            name = "DaenaBot"
        return ("queued_for_approval", {"request_id": req_id, "risk_level": risk, "message": f"Requires approval in {name} Tools panel."})

    # Automated Execution (Low Risk or Auto Mode)
    from backend.integrations.openclaw_gateway_client import get_openclaw_client
    client = get_openclaw_client()
    
    # Try OpenClaw
    executed = False
    result = None
    
    if client.is_connected:
        result = await client.execute_tool(action)
        executed = True
    elif await client.connect():
        result = await client.execute_tool(action)
        executed = True
    
    # Fallback
    if not executed or (result and not result.get("success") and "connected" in str(result.get("error", "")).lower()):
         fallback = await _execute_fallback(action, requested_by)
         if fallback.get("success") or fallback.get("fallback"):
             result = fallback
             executed = True

    if executed:
        try:
             log_execution_audit(requested_by, "tool_request", "execute", bool(result.get("success")), "automated_execution", {"risk": risk})
        except Exception: pass
        return ("executed", result)
    
    return ("error", {"message": result.get("error", "Execution failed") if result else "Not connected to OpenClaw Gate and no fallback."})


async def execute_approved_request(req_id: str) -> Dict[str, Any]:
    """After approval, run the request via OpenClaw/Fallback and update store."""
    from backend.services.tool_request_store import get_request, update_status
    from backend.routes.audit import log_audit_entry as log_execution_audit

    req = get_request(req_id)
    if not req or req.get("status") != "pending":
        return {"success": False, "error": "Request not found or not pending"}
        
    action = req.get("action_json") or {}
    requested_by = req.get("requested_by") or "daena"
    
    from backend.integrations.openclaw_gateway_client import get_openclaw_client
    client = get_openclaw_client()
    
    result = None
    
    try:
        # Try OpenClaw
        if client.is_connected or await client.connect():
            result = await client.execute_tool(action)
        
        # Fallback if failed connection
        if not result or (not result.get("success") and "connected" in str(result.get("error", "")).lower()):
            result = await _execute_fallback(action, requested_by)

        if not result:
            result = {"success": False, "error": "Execution failed (no result)"}

        status = "executed" if result.get("success") else "failed"
        update_status(req_id, status, result)
        
        try:
            log_execution_audit("founder", "tool_request", "execute", bool(result.get("success")), "approved_execution", {"request_id": req_id})
        except Exception: pass
            
        return result

    except Exception as e:
        update_status(req_id, "failed", {"success": False, "error": str(e)})
        try:
            log_execution_audit("founder", "tool_request", "execute", False, str(e), {"request_id": req_id})
        except Exception: pass
        return {"success": False, "error": str(e)}


def _check_hands_allowlist(action: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Check action against hands_allowlist in SystemConfig."""
    action_type = action.get("action_type", "").lower()
    params = action.get("parameters", {})
    
    from backend.database import SessionLocal, SystemConfig
    db = SessionLocal()
    try:
        config_rec = db.query(SystemConfig).filter(SystemConfig.key == "hands_allowlist").first()
        if not config_rec or not config_rec.value_json:
            return True, None # Default allow if not configured? 
                             # Or strict: return False, "Allowlist not configured"
                             
        config = config_rec.value_json
        
        # Filesystem checks
        if "filesystem" in action_type:
            path = params.get("path", "")
            if not path: return True, None
            
            mode = "write" if "write" in action_type else "read"
            allowed_paths = config.get("files", {}).get(mode, [])
            
            # Simple prefix check for now (can be improved with glob)
            any_match = False
            for p in allowed_paths:
                if p.endswith("**"):
                    if path.startswith(p[:-2]): any_match = True
                elif path == p: any_match = True
                
            if not any_match:
                return False, f"Path {path} not in {mode} allowlist"
                
        # Shell checks
        if "shell" in action_type or "terminal" in action_type:
            cmd = params.get("command", "")
            allowed_cmds = config.get("shell", {}).get("allowed_commands", [])
            if not any(c in cmd for c in allowed_cmds):
                return False, f"Command not in shell allowlist"
                
        return True, None
    finally:
        db.close()
