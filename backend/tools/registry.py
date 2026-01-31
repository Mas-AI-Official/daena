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
    "windows_node_safe_shell_exec": ToolDef(
        name="windows_node_safe_shell_exec",
        description="Run allowlisted shell command on Windows Node (local hands).",
        optional_dependency=True,
    ),
    "windows_node_file_read_workspace": ToolDef(
        name="windows_node_file_read_workspace",
        description="Read file from workspace via Windows Node.",
        optional_dependency=True,
    ),
    "windows_node_file_write_workspace": ToolDef(
        name="windows_node_file_write_workspace",
        description="Write text to file in workspace via Windows Node.",
        optional_dependency=True,
    ),
    "sandbox_worker_run": ToolDef(
        name="sandbox_worker_run",
        description="Run allowlisted command in isolated temp dir (download, scan, build).",
        optional_dependency=True,
    ),
    # Tier 0 (read-only, always safe)
    "system_info": ToolDef(
        name="system_info",
        description="Read-only: CPU, memory, disk (Tier 0).",
        optional_dependency=False,
    ),
    "process_list": ToolDef(
        name="process_list",
        description="Read-only: list processes (Tier 0).",
        optional_dependency=False,
    ),
    "service_list": ToolDef(
        name="service_list",
        description="Read-only: list services (Tier 0, Windows/Unix).",
        optional_dependency=False,
    ),
    "net_connections": ToolDef(
        name="net_connections",
        description="Read-only: network connections (Tier 0).",
        optional_dependency=False,
    ),
    "windows_eventlog_read": ToolDef(
        name="windows_eventlog_read",
        description="Read Windows Event Log (Application/System/Security, last N minutes). Tier 0.",
        optional_dependency=True,
    ),
    "defender_status_read": ToolDef(
        name="defender_status_read",
        description="Read Windows Defender status. Tier 0.",
        optional_dependency=True,
    ),
    "repo_git_status": ToolDef(
        name="repo_git_status",
        description="Alias: git status in workspace (Tier 0).",
        optional_dependency=False,
    ),
    "repo_git_diff": ToolDef(
        name="repo_git_diff",
        description="Alias: git diff in workspace (Tier 0).",
        optional_dependency=False,
    ),
    "run_tests": ToolDef(
        name="run_tests",
        description="Run tests (Tier 1): pytest, npm test, pnpm test allowlist; workspace only.",
        optional_dependency=False,
    ),
    "browser_e2e_runner": ToolDef(
        name="browser_e2e_runner",
        description="E2E user flow simulation (Playwright, allowlisted URLs only). Produces report.",
        optional_dependency=True,
    ),
    "screenshot_capture": ToolDef(
        name="screenshot_capture",
        description="Capture screenshot of allowlisted URL (local/UI validation).",
        optional_dependency=True,
    ),
    "repo_scan": ToolDef(
        name="repo_scan",
        description="Read-only: dependency list + basic secrets scan (local, no exfiltration).",
        optional_dependency=False,
    ),
    "workspace_index": ToolDef(
        name="workspace_index",
        description="Build/update index of file paths, sizes, last_modified for allowed workspace (excludes venv, node_modules, .git, models, large binaries).",
        optional_dependency=False,
    ),
    "workspace_search": ToolDef(
        name="workspace_search",
        description="Search workspace index by keyword; returns top matching file paths with short snippets (first N lines via filesystem_read).",
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


# --- Tier 0 helpers (read-only, platform-aware) ---

def _tool_system_info(args: Dict[str, Any]) -> Dict[str, Any]:
    """CPU, memory, disk (Tier 0). Prefer psutil; fallback to subprocess on Windows."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/") if hasattr(psutil, "disk_usage") else None
        return {
            "cpu_percent": cpu,
            "memory_total_mb": round(mem.total / (1024 * 1024), 1),
            "memory_available_mb": round(mem.available / (1024 * 1024), 1),
            "memory_percent": mem.percent,
            "disk_total_gb": round(disk.total / (1024**3), 2) if disk else None,
            "disk_free_gb": round(disk.free / (1024**3), 2) if disk else None,
        }
    except Exception:
        pass
    import sys
    if sys.platform == "win32":
        r = subprocess.run(["wmic", "cpu", "get", "loadpercentage"], capture_output=True, text=True, timeout=5)
        return {"raw_wmic_cpu": (r.stdout or "").strip(), "stderr": r.stderr, "returncode": r.returncode}
    return {"message": "system_info not implemented on this platform"}


def _tool_process_list(args: Dict[str, Any]) -> Dict[str, Any]:
    """List processes (Tier 0)."""
    limit = int(args.get("limit", 20))
    try:
        import psutil
        procs = []
        for p in list(psutil.process_iter(["pid", "name", "status"]))[:limit]:
            try:
                procs.append({"pid": p.info.get("pid"), "name": p.info.get("name"), "status": p.info.get("status")})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return {"processes": procs, "count": len(procs)}
    except Exception:
        pass
    if __import__("sys").platform == "win32":
        r = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=10)
        return {"stdout": (r.stdout or "")[:2000], "returncode": r.returncode}
    return {"message": "process_list not implemented"}


def _tool_service_list(args: Dict[str, Any]) -> Dict[str, Any]:
    """List services (Tier 0). Windows: sc query; Unix: systemctl or stub."""
    import sys
    if sys.platform == "win32":
        r = subprocess.run(["sc", "query", "type=", "state=", "all"], capture_output=True, text=True, timeout=15)
        return {"stdout": (r.stdout or "")[:3000], "stderr": (r.stderr or "")[:500], "returncode": r.returncode}
    return {"message": "service_list not implemented on this platform"}


def _tool_net_connections(args: Dict[str, Any]) -> Dict[str, Any]:
    """Network connections (Tier 0, read-only)."""
    try:
        import psutil
        conns = []
        for c in list(psutil.net_connections(kind="inet"))[:50]:
            conns.append({"family": str(c.family), "status": c.status, "laddr": str(c.laddr), "raddr": str(c.raddr) if c.raddr else None})
        return {"connections": conns, "count": len(conns)}
    except Exception:
        pass
    import sys
    if sys.platform == "win32":
        r = subprocess.run(["netstat", "-an"], capture_output=True, text=True, timeout=10)
        return {"stdout": (r.stdout or "")[:2000], "returncode": r.returncode}
    return {"message": "net_connections not implemented"}


def _tool_windows_eventlog_read(args: Dict[str, Any]) -> Dict[str, Any]:
    """Windows Event Log (Application/System/Security, last N minutes). Tier 0."""
    import sys
    if sys.platform != "win32":
        return {"message": "Windows only"}
    log_name = args.get("log", "Application")
    minutes = int(args.get("minutes", 5))
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Get-WinEvent -LogName {log_name} -MaxEvents 20 -ErrorAction SilentlyContinue | Select-Object TimeCreated, Id, Message | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=15,
        )
        return {"stdout": (r.stdout or "")[:3000], "stderr": (r.stderr or "")[:500], "returncode": r.returncode}
    except Exception as e:
        return {"error": str(e), "message": "eventlog read failed"}


def _tool_defender_status_read(args: Dict[str, Any]) -> Dict[str, Any]:
    """Windows Defender status. Tier 0."""
    import sys
    if sys.platform != "win32":
        return {"message": "Windows only"}
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-MpComputerStatus | Select-Object AntivirusEnabled, RealTimeProtectionEnabled | ConvertTo-Json"],
            capture_output=True, text=True, timeout=10,
        )
        return {"stdout": (r.stdout or "").strip(), "returncode": r.returncode}
    except Exception as e:
        return {"error": str(e), "message": "defender status failed"}


# Exclude dirs when building workspace index (same as repo_scan style)
_WORKSPACE_INDEX_SKIP_DIRS = frozenset({
    "venv", ".venv", "env", ".git", "node_modules", "__pycache__",
    "models", ".cursor", ".idea", ".vscode", "dist", "build", ".tox",
})


def _is_likely_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as f:
            chunk = f.read(8192)
        return b"\x00" in chunk
    except Exception:
        return True


def _tool_workspace_index(args: Dict[str, Any]) -> Dict[str, Any]:
    """Build index of workspace: paths, sizes, last_modified. Excludes skip dirs and large binaries."""
    root = Path(_workspace_root()).resolve()
    max_file_size = int(args.get("max_file_size", 500_000))
    max_entries = int(args.get("max_entries", 2000))
    index_entries: List[Dict[str, Any]] = []
    try:
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            try:
                rel = str(p.relative_to(root)).replace("\\", "/")
            except ValueError:
                continue
            if any(part in _WORKSPACE_INDEX_SKIP_DIRS for part in p.parts):
                continue
            if p.suffix.lower() in (".pyc", ".pyo", ".so", ".dll", ".exe", ".bin", ".zip", ".tar", ".gz"):
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            if st.st_size > max_file_size:
                continue
            if st.st_size > 0 and _is_likely_binary(p):
                continue
            index_entries.append({
                "path": rel,
                "size": st.st_size,
                "last_modified": st.st_mtime,
            })
            if len(index_entries) >= max_entries:
                break
    except Exception as e:
        return {"error": str(e), "entries": []}
    # Optionally write REPO_DIGEST.md (key folders, entrypoints)
    digest_path = root / "docs" / "REPO_DIGEST.md"
    try:
        digest_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Repo Digest (auto-generated by workspace_index)",
            "",
            "## Key folders",
        ]
        seen_dirs: set = set()
        for e in index_entries[:500]:
            parts = e["path"].split("/")
            for i in range(1, len(parts)):
                d = "/".join(parts[:i])
                if d not in seen_dirs:
                    seen_dirs.add(d)
            if len(seen_dirs) > 50:
                break
        for d in sorted(seen_dirs)[:40]:
            lines.append(f"- {d}/")
        lines.extend(["", "## Sample entrypoints"])
        for e in index_entries:
            if e["path"].endswith("main.py") or e["path"].endswith("__main__.py") or e["path"] in ("backend/main.py", "app.py"):
                lines.append(f"- {e['path']}")
            if len([x for x in lines if x.startswith("- ") and "entrypoints" in "".join(lines)]) > 15:
                break
        lines.append("")
        digest_path.write_text("\n".join(lines), encoding="utf-8")
    except Exception:
        pass
    return {
        "workspace_path": str(root),
        "count": len(index_entries),
        "entries": index_entries[:500],
        "digest_written": digest_path.exists() if digest_path else False,
    }


def _tool_workspace_search(args: Dict[str, Any]) -> Dict[str, Any]:
    """Search workspace by keyword; returns top paths with short snippets (first N lines)."""
    query = (args.get("query") or args.get("q") or "").strip().lower()
    if not query:
        return {"error": "query required", "matches": []}
    root = Path(_workspace_root()).resolve()
    max_matches = int(args.get("max_matches", 15))
    snippet_lines = int(args.get("snippet_lines", 5))
    matches: List[Dict[str, Any]] = []
    try:
        for p in root.rglob("*"):
            if not p.is_file() or len(matches) >= max_matches:
                break
            if any(part in _WORKSPACE_INDEX_SKIP_DIRS for part in p.parts):
                continue
            try:
                rel = str(p.relative_to(root)).replace("\\", "/")
            except ValueError:
                continue
            if query in rel.lower():
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                    first = "\n".join(content.splitlines()[:snippet_lines])
                    matches.append({"path": rel, "snippet": first[:400]})
                except Exception:
                    matches.append({"path": rel, "snippet": ""})
                continue
            if p.suffix.lower() not in (".py", ".md", ".txt", ".html", ".js", ".ts", ".json", ".yaml", ".yml"):
                continue
            try:
                if p.stat().st_size > 100_000:
                    continue
                content = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if query not in content.lower():
                continue
            first = "\n".join(content.splitlines()[:snippet_lines])
            matches.append({"path": rel, "snippet": first[:400]})
    except Exception as e:
        return {"error": str(e), "matches": []}
    return {"query": query, "count": len(matches), "matches": matches}


def _tool_run_tests(args: Dict[str, Any]) -> Dict[str, Any]:
    """Run tests (Tier 1): pytest, npm test, pnpm test allowlist only; workspace only."""
    runner = (args.get("runner") or args.get("command") or "pytest").strip().lower()
    cwd = args.get("cwd") or _workspace_root()
    root = Path(_workspace_root()).resolve()
    if not str(Path(cwd).resolve()).startswith(str(root)):
        raise PolicyError("cwd outside workspace")
    timeout_sec = int(args.get("timeout", 120))
    if runner in ("pytest", "python -m pytest", "python -m pytest -v"):
        r = subprocess.run(
            ["python", "-m", "pytest", "-v", "--tb=short"],
            capture_output=True, text=True, timeout=timeout_sec, cwd=cwd,
        )
        return {"stdout": r.stdout, "stderr": r.stderr, "returncode": r.returncode}
    if runner in ("npm test", "npm run test"):
        r = subprocess.run(["npm", "run", "test"], capture_output=True, text=True, timeout=timeout_sec, cwd=cwd)
        return {"stdout": r.stdout, "stderr": r.stderr, "returncode": r.returncode}
    if runner in ("pnpm test", "pnpm run test"):
        r = subprocess.run(["pnpm", "run", "test"], capture_output=True, text=True, timeout=timeout_sec, cwd=cwd)
        return {"stdout": r.stdout, "stderr": r.stderr, "returncode": r.returncode}
    raise PolicyError("runner not in allowlist: pytest, npm test, pnpm test")


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
        if tool_name in ("git_status", "repo_git_status"):
            cwd = args.get("cwd") or _workspace_root()
            r = subprocess.run(["git", "status", "--short"], capture_output=True, text=True, timeout=10, cwd=cwd)
            result = {"stdout": r.stdout, "stderr": r.stderr, "returncode": r.returncode}
        elif tool_name in ("git_diff", "repo_git_diff"):
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
        elif tool_name in ("windows_node_safe_shell_exec", "windows_node_file_read_workspace", "windows_node_file_write_workspace"):
            from backend.services.windows_node_client import node_run_tool
            node_tool = "safe_shell_exec" if tool_name == "windows_node_safe_shell_exec" else "file_read_workspace" if tool_name == "windows_node_file_read_workspace" else "file_write_workspace"
            out = await node_run_tool(node_tool, args)
            if out.get("status") == "error":
                raise PolicyError(out.get("error", "node error"))
            result = out
        elif tool_name == "sandbox_worker_run":
            from backend.tools.executors.sandbox_worker import run as run_sandbox
            result = await run_sandbox(args)
        elif tool_name == "system_info":
            result = _tool_system_info(args)
        elif tool_name == "process_list":
            result = _tool_process_list(args)
        elif tool_name == "service_list":
            result = _tool_service_list(args)
        elif tool_name == "net_connections":
            result = _tool_net_connections(args)
        elif tool_name == "windows_eventlog_read":
            result = _tool_windows_eventlog_read(args)
        elif tool_name == "defender_status_read":
            result = _tool_defender_status_read(args)
        elif tool_name == "run_tests":
            result = _tool_run_tests(args)
        elif tool_name == "browser_e2e_runner":
            from backend.tools.executors.browser_e2e_runner import run_browser_e2e
            result = await run_browser_e2e(
                base_url=args.get("base_url") or args.get("url") or "http://127.0.0.1:8000",
                steps=args.get("steps"),
                timeout_ms=int(args.get("timeout_ms", 30000)),
                headless=bool(args.get("headless", True)),
                allowlist=args.get("allowlist"),
                report_path=args.get("report_path"),
            )
        elif tool_name == "screenshot_capture":
            from backend.tools.executors.screenshot_capture import capture_screenshot
            result = await capture_screenshot(
                url=args.get("url") or args.get("base_url") or "http://127.0.0.1:8000",
                path=args.get("path"),
                timeout_ms=int(args.get("timeout_ms", 15000)),
                headless=bool(args.get("headless", True)),
                allowlist=args.get("allowlist"),
            )
        elif tool_name == "repo_scan":
            from backend.tools.executors.repo_scan import run_repo_scan
            result = run_repo_scan(
                cwd=args.get("cwd"),
                scan_deps=bool(args.get("scan_deps", True)),
                scan_secrets=bool(args.get("scan_secrets", True)),
                max_file_size=int(args.get("max_file_size", 100000)),
            )
        elif tool_name == "workspace_index":
            result = _tool_workspace_index(args)
        elif tool_name == "workspace_search":
            result = _tool_workspace_search(args)
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



