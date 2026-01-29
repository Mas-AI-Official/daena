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

import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from backend.tools.audit_log import write_audit_event
from backend.tools.policies import PolicyError, rate_limiter, redact


def _workspace_root() -> str:
    from backend.config.settings import settings
    root = getattr(settings, "execution_workspace_root", None) or _project_root()
    return str(root)


def _project_root() -> str:
    return str(Path(__file__).resolve().parent.parent.parent)


def _resolve_workspace_path(rel_path: str) -> Path:
    """Resolve path under workspace; raise PolicyError if outside."""
    root = Path(_workspace_root()).resolve()
    path = (root / rel_path).resolve()
    if not str(path).startswith(str(root)):
        raise PolicyError("path outside workspace")
    return path


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
    "git_status": ToolDef(
        name="git_status",
        description="Run git status in workspace (read-only, safe).",
        optional_dependency=False,
    ),
    "git_diff": ToolDef(
        name="git_diff",
        description="Run git diff (read-only, safe).",
        optional_dependency=False,
    ),
    "filesystem_read": ToolDef(
        name="filesystem_read",
        description="Read file content (workspace allowlist only).",
        optional_dependency=False,
    ),
    "filesystem_write": ToolDef(
        name="filesystem_write",
        description="Write text to file (workspace allowlist, no binary).",
        optional_dependency=False,
    ),
    "apply_patch": ToolDef(
        name="apply_patch",
        description="Apply unified diff patch (workspace only).",
        optional_dependency=False,
    ),
    "shell_exec": ToolDef(
        name="shell_exec",
        description="Run allowlisted shell command (git, python -m, pip list, etc.).",
        optional_dependency=False,
    ),
}


def _is_tool_enabled(tool_name: str) -> bool:
    try:
        from backend.services.execution_layer_config import is_tool_enabled as check
        return check(tool_name)
    except Exception:
        return True


def list_tools(include_enabled: bool = False) -> List[Dict[str, Any]]:
    out = [{"name": t.name, "description": t.description, "optional_dependency": t.optional_dependency} for t in TOOL_DEFS.values()]
    if include_enabled:
        for item in out:
            item["enabled"] = _is_tool_enabled(item["name"])
    return out


async def execute_tool(
    *,
    tool_name: str,
    args: Dict[str, Any],
    department: Optional[str],
    agent_id: Optional[str],
    reason: Optional[str],
    trace_id: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Canonical tool execution path.
    Returns: { status, result, error, audit_id, trace_id, dry_run }
    """
    t0 = time.time()
    trace_id = trace_id or uuid.uuid4().hex
    tool_name = (tool_name or "").strip()
    args = args or {}

    if tool_name not in TOOL_DEFS:
        audit_id = write_audit_event(
            tool_name=tool_name,
            args=args,
            department=department,
            agent_id=agent_id,
            reason=reason,
            status="error",
            trace_id=trace_id,
            duration_ms=(time.time() - t0) * 1000.0,
            error="unknown tool",
        )
        return {"status": "error", "result": None, "error": f"unknown tool: {tool_name}", "audit_id": audit_id, "trace_id": trace_id, "dry_run": dry_run}

    if not _is_tool_enabled(tool_name):
        audit_id = write_audit_event(
            tool_name=tool_name,
            args=args,
            department=department,
            agent_id=agent_id,
            reason=reason,
            status="disabled",
            trace_id=trace_id,
            duration_ms=(time.time() - t0) * 1000.0,
            error="tool disabled",
        )
        return {"status": "error", "result": None, "error": "tool disabled", "audit_id": audit_id, "trace_id": trace_id, "dry_run": dry_run}

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
        return {"status": "error", "result": None, "error": "rate_limited", "audit_id": audit_id, "trace_id": trace_id, "dry_run": dry_run}

    if dry_run:
        audit_id = write_audit_event(
            tool_name=tool_name,
            args=args,
            department=department,
            agent_id=agent_id,
            reason=reason,
            status="dry_run",
            trace_id=trace_id,
            duration_ms=(time.time() - t0) * 1000.0,
            error=None,
        )
        return {"status": "ok", "result": {"dry_run": True, "tool": tool_name, "args_summary": redact(args)}, "error": None, "audit_id": audit_id, "trace_id": trace_id, "dry_run": True}

    error = None
    status = "ok"
    result: Any = None
    try:
        if tool_name == "git_status":
            cwd = args.get("cwd") or _workspace_root()
            r = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=10, cwd=cwd)
            result = {"stdout": r.stdout, "stderr": r.stderr, "returncode": r.returncode}
        elif tool_name == "git_diff":
            cwd = args.get("cwd") or _workspace_root()
            r = subprocess.run(["git", "diff", "--no-color"], capture_output=True, text=True, timeout=30, cwd=cwd)
            result = {"stdout": r.stdout, "stderr": r.stderr, "returncode": r.returncode}
        elif tool_name == "filesystem_read":
            rel = (args.get("path") or args.get("file") or "").strip()
            if not rel:
                raise PolicyError("path required")
            path = _resolve_workspace_path(rel)
            if not path.is_file():
                raise PolicyError("not a file or not found")
            result = {"path": str(path), "content": path.read_text(encoding="utf-8", errors="replace")}
        elif tool_name == "filesystem_write":
            rel = (args.get("path") or args.get("file") or "").strip()
            content = args.get("content") or args.get("text") or ""
            if not rel:
                raise PolicyError("path required")
            path = _resolve_workspace_path(rel)
            if isinstance(content, bytes):
                raise PolicyError("binary writes denied")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            result = {"path": str(path), "written": len(content)}
        elif tool_name == "apply_patch":
            patch_content = args.get("patch") or args.get("content") or ""
            cwd = args.get("cwd") or _workspace_root()
            if not patch_content.strip():
                raise PolicyError("patch content required")
            r = subprocess.run(
                ["git", "apply", "--check", "-"],
                input=patch_content,
                capture_output=True,
                text=True,
                timeout=15,
                cwd=cwd,
            )
            if r.returncode != 0:
                result = {"ok": False, "error": r.stderr or r.stdout, "returncode": r.returncode}
            else:
                r2 = subprocess.run(
                    ["git", "apply", "-"],
                    input=patch_content,
                    capture_output=True,
                    text=True,
                    timeout=15,
                    cwd=cwd,
                )
                result = {"ok": r2.returncode == 0, "stdout": r2.stdout, "stderr": r2.stderr, "returncode": r2.returncode}
        elif tool_name == "shell_exec":
            from backend.config.settings import settings
            cmd = args.get("command") or args.get("cmd") or ""
            if isinstance(cmd, list):
                cmd = " ".join(str(c) for c in cmd)
            cmd = cmd.strip()
            allowlist = getattr(settings, "shell_allowlist", None) or ["git ", "python -m ", "pip list", "pip show", "pip --version"]
            allowed = any(cmd.startswith(a.strip()) for a in allowlist if a)
            if not allowed:
                raise PolicyError("command not in allowlist")
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=_workspace_root())
            result = {"stdout": r.stdout, "stderr": r.stderr, "returncode": r.returncode}
        elif tool_name == "web_scrape_bs4":
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

    return {"status": status, "result": redact(result), "error": error, "audit_id": audit_id, "trace_id": trace_id, "dry_run": False}



