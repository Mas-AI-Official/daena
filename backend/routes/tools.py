"""
Canonical tool execution endpoint for Daena + agents.

POST /api/v1/tools/execute
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.services.cmp_service import run_cmp_tool_action
from backend.tools.registry import list_tools


router = APIRouter(prefix="/api/v1/tools", tags=["tools"])


def _trace_id(request: Optional[Request]) -> str:
    if request is not None and hasattr(request.state, "trace_id") and request.state.trace_id:
        return str(request.state.trace_id)
    return uuid.uuid4().hex


class ToolExecuteRequest(BaseModel):
    tool_name: str
    args: Dict[str, Any] = {}
    department: Optional[str] = None
    agent_id: Optional[str] = None
    reason: Optional[str] = None


@router.get("/status")
async def tools_status():
    """
    Returns tool registry plus basic availability hints (dependency installed checks are done at runtime per tool).
    """
    return {"success": True, "tools": list_tools()}


@router.post("/execute")
async def tools_execute(req: ToolExecuteRequest, request: Request):
    trace_id = _trace_id(request)
    out = await run_cmp_tool_action(
        tool_name=req.tool_name,
        args=req.args,
        department=req.department,
        agent_id=req.agent_id,
        reason=req.reason,
        trace_id=trace_id,
    )
    return {"success": out["status"] == "ok", **out}


class ConsultUIRequest(BaseModel):
    provider: str  # "chatgpt" | "gemini"
    question: str
    timeout_sec: int = 60
    manual_approval: bool = True


@router.post("/consult_ui")
async def consult_ui_endpoint(req: ConsultUIRequest, request: Request):
    """
    Consult external LLM UI via browser automation (manual approval mode).
    
    This is a fallback mode when APIs are unavailable or too costly.
    Requires ENABLE_UI_CONSULT=1 and manual approval by default.
    """
    import os
    
    # Check feature flag
    if os.getenv("ENABLE_UI_CONSULT", "0") != "1":
        return {
            "success": False,
            "status": "error",
            "error": "UI Consult Mode disabled. Set ENABLE_UI_CONSULT=1 to enable.",
        }
    
    trace_id = _trace_id(request)
    
    # Execute via canonical tool runner
    out = await run_cmp_tool_action(
        tool_name="consult_ui",
        args={
            "provider": req.provider,
            "question": req.question,
            "timeout_sec": req.timeout_sec,
            "manual_approval": req.manual_approval,
        },
        department=None,
        agent_id=None,
        reason="daena.ui_consult",
        trace_id=trace_id,
    )
    
    return {"success": out["status"] == "ok", **out}



