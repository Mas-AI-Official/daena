"""
⚠️ CORE FILE — DO NOT DELETE OR REWRITE
Changes allowed ONLY via extension modules.

CMP service: interpret a CMP action -> route to tool -> return normalized result.

No new auth/crypto. This is a thin orchestrator over backend/tools/registry.py.

CRITICAL: This is the canonical CMP dispatch layer. Only patch specific functions.
Never replace the entire module or remove run_cmp_tool_action() function.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from backend.tools.registry import execute_tool


async def run_cmp_tool_action(
    *,
    tool_name: str,
    args: Dict[str, Any],
    department: Optional[str],
    agent_id: Optional[str],
    reason: Optional[str],
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    return await execute_tool(
        tool_name=tool_name,
        args=args,
        department=department,
        agent_id=agent_id,
        reason=reason,
        trace_id=trace_id,
    )



