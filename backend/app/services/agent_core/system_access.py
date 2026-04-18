"""SystemAccess -- full machine access layer.

Daena's hands. File system, terminal, network, system info.
All actions go through governance wrapper: AGI mode = immediate,
governed mode = check criticality first.
"""

from __future__ import annotations

import asyncio
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


def _run_sync(cmd: list[str], *, cwd: str | None = None, timeout: float = 300.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)


class CriticalityClassifier:
    """Classify actions as critical or non-critical."""

    CRITICAL_PATTERNS = [
        "delete", "remove", "rm -rf", "format", "drop table",
        "push --force", "reset --hard", "send email", "post to",
        "payment", "transfer", "deploy production",
    ]

    def classify(self, action: str) -> str:
        """Returns 'CRITICAL' or 'NON_CRITICAL'."""
        action_lower = action.lower()
        for pattern in self.CRITICAL_PATTERNS:
            if pattern in action_lower:
                return "CRITICAL"
        return "NON_CRITICAL"


class SystemAccess:
    """Full machine access layer with governance wrapper."""

    def __init__(self, agi_mode: bool = False) -> None:
        self.agi_mode = agi_mode
        self.classifier = CriticalityClassifier()

    # ── File System ──

    async def read_file(self, path: str) -> str:
        """Read a file's contents."""
        return await asyncio.to_thread(Path(path).read_text, encoding="utf-8", errors="replace")

    async def write_file(self, path: str, content: str) -> bool:
        """Write content to a file (creates parent dirs)."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(p.write_text, content, encoding="utf-8")
        return True

    async def list_directory(self, path: str) -> list[dict[str, Any]]:
        """List directory contents."""
        p = Path(path)
        if not p.exists():
            return []
        entries = []
        for item in p.iterdir():
            entries.append({
                "name": item.name,
                "is_dir": item.is_dir(),
                "size": item.stat().st_size if item.is_file() else 0,
            })
        return sorted(entries, key=lambda e: (not e["is_dir"], e["name"]))

    async def search_files(self, pattern: str, root: str = ".") -> list[str]:
        """Search for files matching a glob pattern."""
        matches = []
        for p in Path(root).rglob(pattern):
            matches.append(str(p))
            if len(matches) >= 100:
                break
        return matches

    async def copy_file(self, src: str, dst: str) -> bool:
        """Copy a file."""
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.copy2, src, dst)
        return True

    async def move_file(self, src: str, dst: str) -> bool:
        """Move a file."""
        Path(dst).parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.move, src, dst)
        return True

    # ── Terminal ──

    async def run_command(self, cmd: str, cwd: str | None = None, timeout: int = 300) -> dict[str, Any]:
        """Run a shell command."""
        result = await asyncio.to_thread(
            _run_sync, ["bash", "-c", cmd], cwd=cwd, timeout=float(timeout),
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0,
        }

    async def run_python(self, code: str) -> dict[str, Any]:
        """Run Python code.

        Uses ``sys.executable`` so the subprocess inherits the same
        interpreter (venv or system) that Daena is running on. The
        prior version shelled out to bare ``python`` which resolved
        from PATH and routinely mismatched the running env -- making
        ``_auto_install`` appear broken because packages landed in the
        venv but the subprocess ran against a different Python.
        """
        import sys
        result = await asyncio.to_thread(
            _run_sync, [sys.executable, "-c", code], timeout=60.0,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "success": result.returncode == 0,
        }

    async def install_package(self, package: str, manager: str = "pip") -> bool:
        """Install a package.

        For pip, uses ``sys.executable -m pip`` so installs always
        target the interpreter actually running Daena (matches the
        fix in ``run_python``).
        """
        import sys
        if manager == "pip":
            cmd = [sys.executable, "-m", "pip", "install", package, "--quiet"]
        elif manager == "npm":
            cmd = ["npm", "install", package]
        else:
            return False

        result = await asyncio.to_thread(_run_sync, cmd, timeout=120.0)
        return result.returncode == 0

    # ── Network ──

    async def http_get(self, url: str, headers: dict | None = None) -> dict[str, Any]:
        """HTTP GET request."""
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(url, headers=headers or {})
            return {
                "status_code": resp.status_code,
                "text": resp.text[:5000],
                "headers": dict(resp.headers),
            }

    async def http_post(self, url: str, data: dict | None = None, json_body: dict | None = None) -> dict[str, Any]:
        """HTTP POST request."""
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, data=data, json=json_body)
            return {
                "status_code": resp.status_code,
                "text": resp.text[:5000],
            }

    # ── System Info ──

    async def get_system_info(self) -> dict[str, Any]:
        """Get system information."""
        return {
            "platform": platform.system(),
            "version": platform.version(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "cwd": os.getcwd(),
        }

    async def get_disk_usage(self) -> dict[str, Any]:
        """Get disk usage."""
        usage = shutil.disk_usage(".")
        return {
            "total_gb": round(usage.total / (1024**3), 1),
            "used_gb": round(usage.used / (1024**3), 1),
            "free_gb": round(usage.free / (1024**3), 1),
            "percent_used": round(usage.used / usage.total * 100, 1),
        }

    # ── Governance Wrapper ──

    async def execute_with_governance(self, action: str, func, *args, **kwargs) -> Any:
        """Every system access call goes through this.

        AGI mode: execute immediately, log only.
        Governed mode: check CriticalityClassifier first.
        """
        criticality = self.classifier.classify(action)

        if self.agi_mode or criticality == "NON_CRITICAL":
            result = await func(*args, **kwargs)
            logger.info("system_access.executed", action=action[:100], criticality=criticality)
            return result
        else:
            logger.warning("system_access.blocked", action=action[:100], criticality=criticality)
            return {"status": "pending_approval", "action": action, "criticality": criticality}
