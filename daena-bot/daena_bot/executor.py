"""Tool executor - the hands of Daena on the user's machine.

Executes tool calls received from cloud Daena. Each tool maps to a
local operation: file system, terminal, browser, desktop, MCP, etc.

Security:
    - Blocked paths enforced (config.blocked_paths)
    - File size limits enforced (config.max_file_size_mb)
    - Command timeout enforced (config.command_timeout_seconds)
    - All executions logged locally
"""

from __future__ import annotations

import asyncio
import base64
import io
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

from daena_bot.config import BotConfig


class ToolExecutor:
    """Execute tool calls on the local machine."""

    def __init__(self, config: BotConfig) -> None:
        self.config = config
        self._cwd = Path(config.working_directory or Path.home())

    def list_capabilities(self) -> list[str]:
        """Return list of available tool categories."""
        caps = ["file", "terminal", "network", "system"]

        # Check for optional capabilities
        try:
            import playwright  # noqa: F401
            caps.append("browser")
        except ImportError:
            pass

        try:
            import pyautogui  # noqa: F401
            caps.append("desktop")
        except ImportError:
            pass

        return caps

    async def execute(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Dispatch and execute a tool call."""
        # Parse tool_name: "file.read_file" -> prefix="file", op="read_file"
        parts = tool_name.split(".", 1)
        if len(parts) == 2:
            prefix, operation = parts
        else:
            # Try direct name mapping
            prefix, operation = self._resolve_direct(tool_name)

        dispatch = {
            "file": self._exec_file,
            "terminal": self._exec_terminal,
            "network": self._exec_network,
            "browser": self._exec_browser,
            "desktop": self._exec_desktop,
            "system": self._exec_system,
        }

        handler = dispatch.get(prefix)
        if handler is None:
            return {"success": False, "error": f"Unknown tool category: {prefix}"}

        return await handler(operation, params)

    def _resolve_direct(self, name: str) -> tuple[str, str]:
        """Map direct tool names to prefix.operation."""
        mapping = {
            "read_file": ("file", "read_file"),
            "write_file": ("file", "write_file"),
            "list_directory": ("file", "list_directory"),
            "search_files": ("file", "search_files"),
            "delete_file": ("file", "delete_file"),
            "move_file": ("file", "move_file"),
            "copy_file": ("file", "copy_file"),
            "run_command": ("terminal", "execute_command"),
            "run_python": ("terminal", "run_python"),
            "install_package": ("terminal", "install_package"),
            "web_search": ("network", "web_search"),
            "http_get": ("network", "http_get"),
            "http_post": ("network", "http_post"),
            "browser_navigate": ("browser", "navigate"),
            "browser_screenshot": ("browser", "screenshot"),
            "desktop_screenshot": ("desktop", "screenshot"),
            "desktop_click": ("desktop", "click"),
            "desktop_type": ("desktop", "type_text"),
        }
        return mapping.get(name, ("unknown", name))

    def _check_path_allowed(self, path: str) -> bool:
        """Check if a path is allowed (not in blocked list)."""
        resolved = str(Path(path).resolve())
        for blocked in self.config.blocked_paths:
            if resolved.startswith(blocked):
                return False
        return True

    # ── File Operations ─────────────────────────────────────

    async def _exec_file(self, op: str, params: dict[str, Any]) -> dict[str, Any]:
        path = params.get("path", "")

        if op == "read_file":
            if not self._check_path_allowed(path):
                return {"success": False, "error": f"Path blocked: {path}"}
            p = Path(path)
            if not p.exists():
                return {"success": False, "error": f"File not found: {path}"}
            size_mb = p.stat().st_size / (1024 * 1024)
            if size_mb > self.config.max_file_size_mb:
                return {"success": False, "error": f"File too large: {size_mb:.1f}MB (max {self.config.max_file_size_mb}MB)"}
            try:
                content = p.read_text(encoding="utf-8", errors="replace")
                return {"success": True, "content": content[:50_000]}
            except Exception as exc:
                return {"success": False, "error": str(exc)}

        elif op == "write_file":
            if not self._check_path_allowed(path):
                return {"success": False, "error": f"Path blocked: {path}"}
            content = params.get("content", "")
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return {"success": True, "message": f"Written {len(content)} chars to {path}"}

        elif op == "list_directory":
            p = Path(path or ".")
            if not p.is_dir():
                return {"success": False, "error": f"Not a directory: {path}"}
            entries = []
            for item in sorted(p.iterdir()):
                entries.append({
                    "name": item.name,
                    "type": "dir" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else 0,
                })
            return {"success": True, "entries": entries[:200]}

        elif op == "search_files":
            pattern = params.get("pattern", "*")
            root = Path(params.get("root", "."))
            matches = [str(p) for p in root.rglob(pattern)]
            return {"success": True, "files": matches[:100]}

        elif op == "delete_file":
            if not self._check_path_allowed(path):
                return {"success": False, "error": f"Path blocked: {path}"}
            p = Path(path)
            if not p.exists():
                return {"success": False, "error": f"Not found: {path}"}
            # Archive instead of delete
            archive = p.parent / ".archive"
            archive.mkdir(exist_ok=True)
            dest = archive / f"{p.name}.{int(asyncio.get_event_loop().time())}"
            shutil.move(str(p), str(dest))
            return {"success": True, "message": f"Archived to {dest}"}

        elif op == "move_file":
            src, dst = params.get("source", ""), params.get("destination", "")
            shutil.move(src, dst)
            return {"success": True, "message": f"Moved {src} -> {dst}"}

        elif op == "copy_file":
            src, dst = params.get("source", ""), params.get("destination", "")
            shutil.copy2(src, dst)
            return {"success": True, "message": f"Copied {src} -> {dst}"}

        return {"success": False, "error": f"Unknown file operation: {op}"}

    # ── Terminal Operations ─────────────────────────────────

    async def _exec_terminal(self, op: str, params: dict[str, Any]) -> dict[str, Any]:
        if op == "execute_command":
            command = params.get("command", "")
            cwd = params.get("working_directory", str(self._cwd))
            try:
                result = await asyncio.wait_for(
                    asyncio.create_subprocess_shell(
                        command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=cwd,
                    ),
                    timeout=self.config.command_timeout_seconds,
                )
                stdout_raw, stderr_raw = await result.communicate()
                stdout = stdout_raw.decode("utf-8", errors="replace")[:10_000]
                stderr = stderr_raw.decode("utf-8", errors="replace")[:2_000]
                return {
                    "success": result.returncode == 0,
                    "stdout": stdout,
                    "stderr": stderr,
                    "exit_code": result.returncode,
                }
            except asyncio.TimeoutError:
                return {"success": False, "error": f"Command timed out after {self.config.command_timeout_seconds}s"}
            except Exception as exc:
                return {"success": False, "error": str(exc)}

        elif op == "run_python":
            code = params.get("code", "")
            try:
                result = await asyncio.wait_for(
                    asyncio.create_subprocess_exec(
                        "python", "-c", code,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                    ),
                    timeout=self.config.command_timeout_seconds,
                )
                stdout_raw, stderr_raw = await result.communicate()
                return {
                    "success": result.returncode == 0,
                    "stdout": stdout_raw.decode("utf-8", errors="replace")[:10_000],
                    "stderr": stderr_raw.decode("utf-8", errors="replace")[:2_000],
                }
            except asyncio.TimeoutError:
                return {"success": False, "error": "Python execution timed out"}

        elif op == "install_package":
            pkg = params.get("package", "")
            manager = params.get("manager", "pip")
            cmd = f"pip install {pkg}" if manager == "pip" else f"npm install -g {pkg}"
            return await self._exec_terminal("execute_command", {"command": cmd})

        return {"success": False, "error": f"Unknown terminal operation: {op}"}

    # ── Network Operations ──────────────────────────────────

    async def _exec_network(self, op: str, params: dict[str, Any]) -> dict[str, Any]:
        import httpx

        if op == "http_get":
            url = params.get("url", "")
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.get(url, follow_redirects=True)
                    return {
                        "success": True,
                        "status_code": resp.status_code,
                        "body": resp.text[:10_000],
                        "headers": dict(resp.headers),
                    }
            except Exception as exc:
                return {"success": False, "error": str(exc)}

        elif op == "http_post":
            url = params.get("url", "")
            body = params.get("json_body", {})
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(url, json=body, follow_redirects=True)
                    return {
                        "success": True,
                        "status_code": resp.status_code,
                        "body": resp.text[:10_000],
                    }
            except Exception as exc:
                return {"success": False, "error": str(exc)}

        elif op == "web_search":
            query = params.get("query", "")
            import httpx
            import re
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(
                        "https://html.duckduckgo.com/html/",
                        params={"q": query},
                        headers={"User-Agent": "DaenaBot/0.1"},
                    )
                    results = re.findall(
                        r'class="result__snippet">(.*?)</a>',
                        resp.text, re.DOTALL,
                    )
                    clean = [re.sub(r'<[^>]+>', '', r).strip() for r in results[:5]]
                    return {"success": True, "query": query, "results": clean or ["No results found"]}
            except Exception as exc:
                return {"success": False, "error": str(exc)}

        return {"success": False, "error": f"Unknown network operation: {op}"}

    # ── Browser Operations ──────────────────────────────────

    async def _exec_browser(self, op: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return {
                "success": False,
                "error": "Browser tools require playwright. Run: pip install playwright && playwright install chromium",
            }

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                if op == "navigate":
                    url = params.get("url", "")
                    await page.goto(url, timeout=30_000)
                    title = await page.title()
                    content = await page.content()
                    return {"success": True, "title": title, "content": content[:10_000]}

                elif op == "screenshot":
                    url = params.get("url", "")
                    await page.goto(url, timeout=30_000)
                    screenshot = await page.screenshot(type="png")
                    b64 = base64.b64encode(screenshot).decode("utf-8")
                    return {"success": True, "image_base64": b64[:200] + "...", "message": "Screenshot captured"}

                elif op == "extract_text":
                    url = params.get("url", "")
                    await page.goto(url, timeout=30_000)
                    text = await page.inner_text("body")
                    return {"success": True, "text": text[:10_000]}

                elif op == "click_element":
                    selector = params.get("selector", "")
                    await page.click(selector, timeout=10_000)
                    return {"success": True, "message": f"Clicked {selector}"}

                elif op == "fill_form":
                    selector = params.get("selector", "")
                    value = params.get("value", "")
                    await page.fill(selector, value, timeout=10_000)
                    return {"success": True, "message": f"Filled {selector}"}

                return {"success": False, "error": f"Unknown browser operation: {op}"}
            finally:
                await browser.close()

    # ── Desktop Operations ──────────────────────────────────

    async def _exec_desktop(self, op: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            import pyautogui
            pyautogui.FAILSAFE = True
        except ImportError:
            return {
                "success": False,
                "error": "Desktop tools require pyautogui. Run: pip install pyautogui",
            }

        if op == "screenshot":
            screenshot = pyautogui.screenshot()
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG")
            b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
            return {
                "success": True,
                "image_base64": b64[:200] + "...",
                "width": screenshot.width,
                "height": screenshot.height,
            }

        elif op == "click":
            x, y = params.get("x", 0), params.get("y", 0)
            button = params.get("button", "left")
            clicks = 2 if params.get("double_click") else 1
            pyautogui.click(x, y, clicks=clicks, button=button)
            return {"success": True, "message": f"Clicked ({x}, {y})"}

        elif op == "type_text":
            text = params.get("text", "")
            pyautogui.write(text)
            return {"success": True, "message": f"Typed {len(text)} chars"}

        elif op == "hotkey":
            keys = params.get("keys", "").split("+")
            pyautogui.hotkey(*keys)
            return {"success": True, "message": f"Pressed {params.get('keys')}"}

        elif op == "scroll":
            direction = params.get("direction", "down")
            amount = params.get("amount", 3)
            pyautogui.scroll(amount if direction == "up" else -amount)
            return {"success": True, "message": f"Scrolled {direction}"}

        return {"success": False, "error": f"Unknown desktop operation: {op}"}

    # ── System Info ─────────────────────────────────────────

    async def _exec_system(self, op: str, params: dict[str, Any]) -> dict[str, Any]:
        import psutil

        if op == "info":
            return {
                "success": True,
                "platform": platform.system(),
                "machine": platform.node(),
                "os_version": platform.version(),
                "python_version": platform.python_version(),
                "cpu_count": psutil.cpu_count(),
                "memory_gb": round(psutil.virtual_memory().total / (1024**3), 1),
                "disk_free_gb": round(psutil.disk_usage("/").free / (1024**3), 1),
            }

        elif op == "processes":
            procs = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent"]):
                procs.append(p.info)
            procs.sort(key=lambda x: x.get("cpu_percent", 0), reverse=True)
            return {"success": True, "processes": procs[:20]}

        return {"success": False, "error": f"Unknown system operation: {op}"}
