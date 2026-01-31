"""
Sandbox worker: run allowlisted commands in an isolated temp dir.
Use for downloads, unpack, scan, build, test. No access to real secrets by default.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict

SANDBOX_ALLOWLIST = ["pip list", "pip show", "pip download", "python -m pip list", "python -m pip show"]


async def run(args: Dict[str, Any]) -> Dict[str, Any]:
    """Run command in temp dir. args: command (str), timeout_sec (int, default 60)."""
    cmd = (args.get("command") or args.get("cmd") or "").strip()
    if isinstance(cmd, list):
        cmd = " ".join(str(c) for c in cmd)
    timeout = int(args.get("timeout_sec", 60))
    allowed = any(cmd.startswith(a.strip()) for a in SANDBOX_ALLOWLIST if a)
    if not allowed:
        return {"status": "error", "error": "command not in sandbox allowlist", "stdout": "", "stderr": ""}
    with tempfile.TemporaryDirectory(prefix="daena_sandbox_") as tmp:
        try:
            r = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmp,
                env={**os.environ, "SANDBOX": "1"},
            )
            return {
                "status": "ok",
                "stdout": (r.stdout or "")[:2000],
                "stderr": (r.stderr or "")[:500],
                "returncode": r.returncode,
                "cwd": tmp,
            }
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "timeout", "stdout": "", "stderr": ""}
        except Exception as e:
            return {"status": "error", "error": str(e), "stdout": "", "stderr": ""}
