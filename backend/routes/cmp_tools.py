"""
CMP tool registry + executor endpoints.

These endpoints are used by the brain/operator UI to discover and execute tools
in a normalized way.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel

from backend.tools.registry import list_tools
from backend.services.cmp_service import run_cmp_tool_action


router = APIRouter(prefix="/api/v1/cmp", tags=["cmp-tools"])


def _trace_id_from_request(request: Optional[Request]) -> str:
    if request is not None and hasattr(request.state, "trace_id") and request.state.trace_id:
        return str(request.state.trace_id)
    return uuid.uuid4().hex


class ToolExecRequest(BaseModel):
    name: str
    args: Dict[str, Any] = {}


@router.get("/tools")
async def get_tools():
    return {"success": True, "tools": list_tools()}


@router.post("/tools/execute")
async def post_execute_tool(req: ToolExecRequest, request: Request):
    trace_id = _trace_id_from_request(request)
    out = await run_cmp_tool_action(
        tool_name=req.name,
        args=req.args,
        department=None,
        agent_id=None,
        reason="cmp_tools.execute",
        trace_id=trace_id,
    )
    return {"success": out["status"] == "ok", **out}


