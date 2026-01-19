"""
⚠️ CORE FILE — DO NOT DELETE OR REWRITE
Changes allowed ONLY via extension modules.

Tool registry (single source of truth).

Implements the tools requested by policy:
- web_scrape_bs4
- browser_automation_selenium
- desktop_automation_pyautogui

All tools are optional dependencies. Backend must still boot if missing.

CRITICAL: This is the canonical tool registry and execution layer.
Only patch specific functions. Never replace the entire module or remove execute_tool() function.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from backend.tools.audit_log import write_audit_event
from backend.tools.policies import PolicyError, rate_limiter, redact


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    optional_dependency: bool = True


TOOL_DEFS: Dict[str, ToolDef] = {
    "web_scrape_bs4": ToolDef(
        name="web_scrape_bs4",
        description="Fetch a URL and extract text/links/tables (httpx + BeautifulSoup).",
        optional_dependency=False,  # bs4 is in requirements.txt for main env
    ),
    "browser_automation_selenium": ToolDef(
        name="browser_automation_selenium",
        description="Run a safe browser automation sequence using Selenium (optional, gated).",
        optional_dependency=True,
    ),
    "desktop_automation_pyautogui": ToolDef(
        name="desktop_automation_pyautogui",
        description="Run a safe desktop action using pyautogui (optional, gated).",
        optional_dependency=True,
    ),
    "consult_ui": ToolDef(
        name="consult_ui",
        description="Consult Gemini/ChatGPT via browser automation (manual approval, fallback mode).",
        optional_dependency=True,
    ),
}


def list_tools() -> List[Dict[str, Any]]:
    return [{"name": t.name, "description": t.description, "optional_dependency": t.optional_dependency} for t in TOOL_DEFS.values()]


async def execute_tool(
    *,
    tool_name: str,
    args: Dict[str, Any],
    department: Optional[str],
    agent_id: Optional[str],
    reason: Optional[str],
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Canonical tool execution path.
    Returns: { status, result, error, audit_id, trace_id }
    """
    t0 = time.time()
    trace_id = trace_id or uuid.uuid4().hex
    tool_name = (tool_name or "").strip()
    args = args or {}

    rl_key = f"{department or 'unknown'}:{agent_id or 'unknown'}:{tool_name}"
    if not rate_limiter.allow(rl_key):
        audit_id = write_audit_event(
            tool_name=tool_name,
            args=args,
            department=department,
            agent_id=agent_id,
            reason=reason,
            status="rate_limited",
            trace_id=trace_id,
            duration_ms=(time.time() - t0) * 1000.0,
            error="rate_limited",
        )
        return {"status": "error", "result": None, "error": "rate_limited", "audit_id": audit_id, "trace_id": trace_id}

    error = None
    status = "ok"
    result: Any = None
    try:
        if tool_name == "web_scrape_bs4":
            from backend.tools.executors.web_scrape_bs4 import run as run_scrape
            result = await run_scrape(args)
        elif tool_name == "browser_automation_selenium":
            from backend.tools.executors.browser_automation_selenium import run as run_browser
            result = run_browser(args)
        elif tool_name == "desktop_automation_pyautogui":
            from backend.tools.executors.desktop_automation_pyautogui import run as run_desktop
            result = run_desktop(args)
        elif tool_name == "consult_ui":
            from backend.tools.executors.ui_consult_playwright import consult_ui
            result = await consult_ui(
                provider=args.get("provider", ""),
                question=args.get("question", ""),
                timeout_sec=int(args.get("timeout_sec", 60)),
                manual_approval=bool(args.get("manual_approval", True)),
                trace_id=trace_id,
            )
        else:
            raise PolicyError(f"unknown tool: {tool_name}")
    except Exception as e:
        status = "error"
        error = str(e)

    audit_id = write_audit_event(
        tool_name=tool_name,
        args=args,
        department=department,
        agent_id=agent_id,
        reason=reason,
        status=status,
        trace_id=trace_id,
        duration_ms=(time.time() - t0) * 1000.0,
        error=error,
    )

    return {"status": status, "result": redact(result), "error": error, "audit_id": audit_id, "trace_id": trace_id}



