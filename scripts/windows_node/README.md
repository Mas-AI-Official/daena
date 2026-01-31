# Daena Windows Node

Local "hands" server for Moltbot-style control. Binds to **127.0.0.1:18888** only. Do not expose to the internet.

## Setup

1. From project root: `pip install fastapi uvicorn` (if not already).
2. Optional: set `WINDOWS_NODE_TOKEN` so the node requires `X-Windows-Node-Token` header.
3. Optional: set `EXECUTION_WORKSPACE_ROOT` (default: project root).

## Start

- **PowerShell:** `.\scripts\windows_node\start_windows_node.ps1`
- **CMD:** `scripts\windows_node\start_windows_node.bat`
- **Manual:** from `scripts/windows_node` with PYTHONPATH including project root:
  `python -m uvicorn node_server:app --host 127.0.0.1 --port 18888`

## Endpoints

- `GET /node/health` — returns `{ "status": "ok" }`. Use for "Test connection" in dashboard.
- `POST /node/run_tool` — body: `{ "tool_name": "...", "args": { ... } }`. Tools: `safe_shell_exec`, `file_read_workspace`, `file_write_workspace`.

## Daena backend

Set `WINDOWS_NODE_URL=http://127.0.0.1:18888` and optionally `WINDOWS_NODE_TOKEN` so the backend can call the node. Or use **Pair Node** in Control Plane → Execution to save URL and token in the backend (stored in DB). Execution Layer tools `windows_node.*` delegate to this node.

## Smoke test

From project root: `python scripts\smoke_windows_node.py --base http://localhost:8000 --token %EXECUTION_TOKEN%`. Verifies token gating (401 without token) and config/health endpoints with token.
