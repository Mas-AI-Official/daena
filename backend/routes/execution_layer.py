"""
Execution Layer API: tool list with enabled toggles, run (with dry_run), logs, config.
Local-first, safe by default. When EXECUTION_TOKEN is set, require X-Execution-Token header.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from backend.config.settings import settings
from backend.tools.registry import list_tools, execute_tool

router = APIRouter(prefix="/api/v1/execution", tags=["execution-layer"])

# Audit log path (same as backend/tools/audit_log.py)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_AUDIT_PATH = _PROJECT_ROOT / "logs" / "tools_audit.jsonl"


async def verify_execution_token(x_execution_token: Optional[str] = Header(None, alias="X-Execution-Token")):
    """Require X-Execution-Token when EXECUTION_TOKEN env is set. Default: deny if token set and missing."""
    if not settings.execution_token:
        return
    if x_execution_token != settings.execution_token:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Execution-Token")
    return x_execution_token


class RunRequest(BaseModel):
    tool_name: str
    args: Dict[str, Any] = {}
    dry_run: bool = False
    department: Optional[str] = None
    agent_id: Optional[str] = None
    reason: Optional[str] = None
    approval_id: Optional[str] = None


class ConfigUpdate(BaseModel):
    approval_mode: Optional[str] = None
    require_approval_for_risky: Optional[bool] = None
    max_steps_per_run: Optional[int] = None
    max_retries_per_tool: Optional[int] = None
    dry_run_default: Optional[bool] = None


@router.get("/tools", dependencies=[Depends(verify_execution_token)])
async def execution_list_tools() -> Dict[str, Any]:
    """List all tools with enabled/disabled state for the Execution Layer UI."""
    tools = list_tools(include_enabled=True)
    return {"success": True, "tools": tools}


@router.post("/approve", dependencies=[Depends(verify_execution_token)])
async def execution_approve(tool_name: str) -> Dict[str, Any]:
    """Create a short-lived approval for a risky tool. Returns approval_id (TTL 300s)."""
    from backend.services.execution_layer_config import create_approval, get_tool_risk_level
    risk = get_tool_risk_level(tool_name)
    if risk < 1:
        return {"success": True, "approval_id": None, "message": "Tool is low-risk, no approval needed"}
    approval_id = create_approval(tool_name)
    return {"success": True, "approval_id": approval_id, "tool_name": tool_name, "ttl_seconds": 300}


@router.post("/run", response_model=Dict[str, Any], dependencies=[Depends(verify_execution_token)])
async def execution_run(req: RunRequest) -> Dict[str, Any]:
    """Run a tool. Use dry_run=True to log without executing. Risky tools require approval_id when approval_mode is require_approval."""
    from backend.services.execution_layer_config import (
        get_execution_config,
        get_tool_risk_level,
        consume_approval,
    )
    cfg = get_execution_config()
    approval_mode = cfg.get("approval_mode", "auto")
    require_risky = cfg.get("require_approval_for_risky", True)
    risk = get_tool_risk_level(req.tool_name)
    if risk >= 1 and require_risky and approval_mode == "require_approval":
        if not consume_approval(req.approval_id, req.tool_name):
            raise HTTPException(
                status_code=403,
                detail="Risky tool requires approval. Call POST /api/v1/execution/approve?tool_name=... first and pass approval_id",
            )
    out = await execute_tool(
        tool_name=req.tool_name,
        args=req.args,
        department=req.department,
        agent_id=req.agent_id,
        reason=req.reason,
        trace_id=None,
        dry_run=req.dry_run,
    )
    return {"success": out.get("status") == "ok", **out}


@router.get("/logs")
async def execution_logs(limit: int = 50) -> Dict[str, Any]:
    """Return recent tool execution audit entries (timestamp, tool, args summary, result)."""
    entries: List[Dict[str, Any]] = []
    if not _AUDIT_PATH.exists():
        return {"success": True, "logs": [], "count": 0}
    try:
        lines = _AUDIT_PATH.read_text(encoding="utf-8").strip().split("\n")
        for line in reversed(lines[-limit:] if len(lines) > limit else lines):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read audit log: {e}")
    return {"success": True, "logs": entries, "count": len(entries)}


@router.get("/config", dependencies=[Depends(verify_execution_token)])
async def execution_get_config() -> Dict[str, Any]:
    """Get Execution Layer config: approval mode, budget guards, tool toggles."""
    from backend.services.execution_layer_config import get_execution_config
    return {"success": True, "config": get_execution_config()}


@router.patch("/config")
async def execution_update_config(updates: ConfigUpdate) -> Dict[str, Any]:
    """Update approval mode, budget guards (max_steps, max_retries)."""
    from backend.services.execution_layer_config import update_execution_config
    u = updates.model_dump(exclude_none=True)
    if not u:
        from backend.services.execution_layer_config import get_execution_config
        return {"success": True, "config": get_execution_config()}
    config = update_execution_config(u)
    return {"success": True, "config": config}


@router.patch("/tools/{tool_name}/enabled", dependencies=[Depends(verify_execution_token)])
async def execution_toggle_tool(tool_name: str, enabled: bool) -> Dict[str, Any]:
    """Enable or disable a tool."""
    from backend.services.execution_layer_config import set_tool_enabled
    set_tool_enabled(tool_name, enabled)
    return {"success": True, "tool_name": tool_name, "enabled": enabled}
