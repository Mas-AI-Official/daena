"""
Daena Windows Node - minimal local server for Moltbot-style "hands".
Bind 127.0.0.1:18888 only. Require X-Windows-Node-Token when WINDOWS_NODE_TOKEN is set.
Run: python -m uvicorn node_server:app --host 127.0.0.1 --port 18888
     (from scripts/windows_node with PYTHONPATH including project root)
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

# Try FastAPI; fallback for minimal server
try:
    from fastapi import FastAPI, Header, HTTPException
    from fastapi.middleware.cors import CORSMiddleware
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

WORKSPACE_ROOT = os.environ.get("EXECUTION_WORKSPACE_ROOT") or os.environ.get("DAENA_PROJECT_ROOT") or str(Path(__file__).resolve().parent.parent.parent)
SHELL_ALLOWLIST = ["git ", "python -m ", "pip list", "pip show", "pip --version"]


def _require_token(x_token: Optional[str] = None) -> None:
    token = os.environ.get("WINDOWS_NODE_TOKEN")
    if not token:
        return
    if x_token != token:
        raise HTTPException(status_code=401, detail="Missing or invalid X-Windows-Node-Token")


def _resolve_workspace_path(rel_path: str) -> Path:
    root = Path(WORKSPACE_ROOT).resolve()
    path = (root / rel_path.lstrip("/")).resolve()
    if not str(path).startswith(str(root)):
        raise HTTPException(status_code=403, detail="path outside workspace")
    return path


if HAS_FASTAPI:
    app = FastAPI(title="Daena Windows Node", version="1.0.0")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

    @app.get("/node/health")
    def node_health(x_windows_node_token: Optional[str] = Header(None, alias="X-Windows-Node-Token")):
        _require_token(x_windows_node_token)
        return {"status": "ok", "workspace_root": WORKSPACE_ROOT}

    @app.post("/node/run_tool")
    def node_run_tool(
        body: Dict[str, Any],
        x_windows_node_token: Optional[str] = Header(None, alias="X-Windows-Node-Token"),
    ):
        _require_token(x_windows_node_token)
        tool_name = (body.get("tool_name") or "").strip()
        args = body.get("args") or {}
        if tool_name == "safe_shell_exec":
            cmd = args.get("command") or args.get("cmd") or ""
            if isinstance(cmd, list):
                cmd = " ".join(str(c) for c in cmd)
            cmd = cmd.strip()
            allowed = any(cmd.startswith(a.strip()) for a in SHELL_ALLOWLIST if a)
            if not allowed:
                raise HTTPException(status_code=403, detail="command not in allowlist")
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=WORKSPACE_ROOT)
            return {"status": "ok", "stdout": r.stdout, "stderr": r.stderr, "returncode": r.returncode}
        if tool_name == "file_read_workspace":
            rel = (args.get("path") or args.get("file") or "").strip()
            if not rel:
                raise HTTPException(status_code=400, detail="path required")
            path = _resolve_workspace_path(rel)
            if not path.is_file():
                raise HTTPException(status_code=404, detail="not a file or not found")
            return {"status": "ok", "path": str(path), "content": path.read_text(encoding="utf-8", errors="replace")}
        if tool_name == "file_write_workspace":
            rel = (args.get("path") or args.get("file") or "").strip()
            content = args.get("content") or args.get("text") or ""
            if not rel:
                raise HTTPException(status_code=400, detail="path required")
            path = _resolve_workspace_path(rel)
            if isinstance(content, bytes):
                raise HTTPException(status_code=400, detail="binary writes denied")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return {"status": "ok", "path": str(path), "written": len(content)}
        raise HTTPException(status_code=400, detail=f"unknown tool: {tool_name}")
else:
    app = None  # type: ignore
