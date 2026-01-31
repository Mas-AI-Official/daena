"""
Provider messages never call tools directly. They create a ToolRequest that goes through
Execution Layer: provider allowlist, approval_mode, budget, audit.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from backend.providers.base import InboundMessage
from backend.providers.config import (
    is_provider_enabled,
    get_allowed_tools,
    get_standing_instructions,
)
from backend.services.execution_layer_config import (
    get_execution_config,
    get_tool_risk_level,
    consume_approval,
)
from backend.tools.registry import execute_tool
from backend.tools.audit_log import write_audit_event

logger = logging.getLogger(__name__)


@dataclass
class ProviderToolRequest:
    provider_id: str
    tool_name: str
    args: Dict[str, Any]
    channel_id: str
    user_id: str
    reason: str
    approval_id: Optional[str] = None
    trace_id: Optional[str] = None


# Simple keyword -> tool mapping for intent (no LLM required for smoke test)
_INTENT_MAP = [
    (r"health\s*check|status", "health_check"),
    (r"run\s+git\s+status|git\s+status", "git_status"),
    (r"run\s+git\s+diff|git\s+diff", "git_diff"),
    (r"list\s+tools|tools", "list_tools"),
]


def _parse_intent(text: str) -> Optional[tuple[str, Dict[str, Any]]]:
    """Map message text to (tool_name, args). Return None if no match."""
    t = (text or "").strip().lower()
    for pattern, tool_name in _INTENT_MAP:
        if re.search(pattern, t):
            if tool_name == "health_check":
                return ("health_check", {})
            if tool_name == "git_status":
                return ("git_status", {})
            if tool_name == "git_diff":
                return ("git_diff", {})
            if tool_name == "list_tools":
                return ("list_tools", {})
    return None


def create_tool_request_from_message(msg: InboundMessage) -> Optional[ProviderToolRequest]:
    """
    Parse inbound message into a ToolRequest. Returns None if no tool intent.
    Standing instructions are available for future LLM-based parsing.
    """
    if not is_provider_enabled(msg.provider_id):
        return None
    parsed = _parse_intent(msg.text)
    if not parsed:
        return None
    tool_name, args = parsed
    allowed = get_allowed_tools(msg.provider_id)
    if tool_name not in allowed:
        logger.warning("Provider %s requested tool %s not in allowlist %s", msg.provider_id, tool_name, allowed)
        return None
    trace_id = uuid.uuid4().hex[:32]
    reason = f"provider:{msg.provider_id}"
    return ProviderToolRequest(
        provider_id=msg.provider_id,
        tool_name=tool_name,
        args=args,
        channel_id=msg.channel_id,
        user_id=msg.user_id,
        reason=reason,
        trace_id=trace_id,
    )


async def submit_tool_request(
    req: ProviderToolRequest,
    approval_id: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Run ToolRequest through Execution Layer: allowlist, approval for risky, audit.
    Returns { success, result?, error?, audit_id?, requires_approval? }.
    """
    cfg = get_execution_config()
    approval_mode = cfg.get("approval_mode", "auto")
    require_risky = cfg.get("require_approval_for_risky", True)
    risk = get_tool_risk_level(req.tool_name)

    # Special handling for virtual "health_check" / "list_tools"
    if req.tool_name == "health_check":
        from backend.services.daena_tools.api_tester import health_check
        try:
            h = await health_check()
            return {"success": True, "result": h, "audit_id": None}
        except Exception as e:
            return {"success": False, "error": str(e)}
    if req.tool_name == "list_tools":
        from backend.tools.registry import list_tools
        tools = list_tools(include_enabled=True)
        return {"success": True, "result": {"tools": tools}, "audit_id": None}

    # Real tool: check approval for medium+ risk
    if risk >= 1 and require_risky and approval_mode == "require_approval":
        aid = approval_id or req.approval_id
        if not consume_approval(aid, req.tool_name):
            return {
                "success": False,
                "error": "Risky tool requires approval. Call POST /api/v1/execution/approve?tool_name=... first.",
                "requires_approval": True,
            }

    # Execute via canonical path (checks tool_enabled, rate limit, audit)
    out = await execute_tool(
        tool_name=req.tool_name,
        args=req.args,
        department=f"provider:{req.provider_id}",
        agent_id=req.user_id,
        reason=req.reason,
        trace_id=req.trace_id,
        dry_run=dry_run,
    )
    if out.get("status") == "ok":
        return {"success": True, "result": out.get("result"), "audit_id": out.get("audit_id")}
    return {
        "success": False,
        "error": out.get("error", "tool failed"),
        "audit_id": out.get("audit_id"),
    }
