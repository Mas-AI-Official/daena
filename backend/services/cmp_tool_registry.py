"""
DEPRECATED: CMP Tool Registry

This file is kept for backward compatibility, but tool execution is now
canonical via:
- `backend/tools/registry.py`
- `backend/services/cmp_service.py`
- `/api/v1/tools/execute`
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    input_schema: Dict[str, Any]


TOOLS: List[ToolDef] = [
    # kept only so imports don’t break; prefer backend/tools/registry.py
]


def list_tools() -> List[Dict[str, Any]]:
    from backend.tools.registry import list_tools as canonical_list
    return canonical_list()


async def execute_tool(name: str, args: Dict[str, Any], trace_id: str) -> Dict[str, Any]:
    """
    Execute a tool and return normalized output for the brain:
    { status, data, errors, trace_id }
    """
    name = (name or "").strip()
    args = args or {}

    # Best-effort compatibility mapping
    mapping = {
        "tool.scrape.extract": "web_scrape_bs4",
        "tool.desktop.click": "desktop_automation_pyautogui",
        "tool.desktop.type": "desktop_automation_pyautogui",
        "tool.browser.navigate": "browser_automation_selenium",
        "tool.browser.click": "browser_automation_selenium",
        "tool.browser.type": "browser_automation_selenium",
        "tool.browser.screenshot": "browser_automation_selenium",
    }
    tool_name = mapping.get(name, name)
    from backend.services.cmp_service import run_cmp_tool_action
    out = await run_cmp_tool_action(
        tool_name=tool_name,
        args=args,
        department=None,
        agent_id=None,
        reason="deprecated.cmp_tool_registry",
        trace_id=trace_id,
    )
    return {
        "status": out.get("status"),
        "data": out.get("result"),
        "errors": [out.get("error")] if out.get("error") else None,
        "trace_id": out.get("trace_id", trace_id),
    }


