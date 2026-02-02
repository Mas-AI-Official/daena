# Execution Layer

Daena’s **Execution Layer** is the local tool runner that runs actions on this machine safely: file read/write (workspace), shell (allowlist), git, browser automation, and app/API connectors. It is local-first and safe by default.

## Features

- **Tool registry** – Single source of truth in `backend/tools/registry.py`; tools can be enabled/disabled via config.
- **Permission model** – Per-tool allowlist via `config/execution_layer_config.json`; risky tools (browser, desktop) are off by default.
- **Audit log** – Every tool call is logged to `logs/tools_audit.jsonl` and optionally to DB (`ToolExecution`).
- **Dry-run mode** – Run a tool without executing it; only logs the intended call.

## API (for UI)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/execution/tools` | List tools with enabled/disabled state |
| POST | `/api/v1/execution/run` | Run a tool (body: `tool_name`, `args`, `dry_run`) |
| GET | `/api/v1/execution/logs?limit=N` | Recent executions (timestamp, tool, args summary, result) |
| GET | `/api/v1/execution/config` | Approval mode, budget (max_steps, max_retries) |
| PATCH | `/api/v1/execution/config` | Update approval mode / budget |
| PATCH | `/api/v1/execution/tools/{name}/enabled?enabled=true\|false` | Enable/disable a tool |

Canonical tool execute (used by agents/Daena): `POST /api/v1/tools/execute` with optional `dry_run: true`.

## Config

File: `config/execution_layer_config.json`

- `tool_enabled`: map of tool name → boolean (default: safe tools on, risky off).
- `approval_mode`: `"auto"` or `"require_approval"` for risky tools.
- `require_approval_for_risky`: if true, high-impact tools need approval.
- `max_steps_per_run`, `max_retries_per_tool`: budget guards.
- `dry_run_default`: default dry_run for run requests.

## UI

Dashboard → **Execution Layer** card:

- Tool toggles (enable/disable per tool).
- Recent runs (last 5 from audit log).
- Approval mode and budget (max steps / max retries).

## Safety

- **Local-first**: Backend binds to host (e.g. localhost); use a local token or auth in production.
- **Default-deny**: Dangerous commands and risky tools are disabled unless explicitly enabled in config.
- **Audit**: All runs (including dry_run) are written to `logs/tools_audit.jsonl`.

## How to enable

1. Ensure backend is running (e.g. `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`).
2. Enable tools in `config/execution_layer_config.json` or via PATCH `/api/v1/execution/tools/{name}/enabled`.
3. Use Dashboard → Execution Layer to toggle tools and view logs.

## Windows Node (Moltbot-style hands)

When you run a local Windows Node (see `scripts/windows_node/README.md`), set `WINDOWS_NODE_URL` (default `http://127.0.0.1:18888`) and optionally `WINDOWS_NODE_TOKEN`. The Execution Layer then exposes:

- `windows_node_safe_shell_exec` — allowlisted shell on the node
- `windows_node_file_read_workspace` — read file in node workspace
- `windows_node_file_write_workspace` — write file in node workspace

All are medium+ risk; approval is required when `approval_mode` is `require_approval`. Dashboard has a “Test connection” button that calls GET `/api/v1/execution/node/health`.

## Sandbox worker

- `sandbox_worker_run` — run allowlisted commands (e.g. pip list, pip show) in an isolated temp dir. Use for downloads/builds without touching the main workspace.

## Autonomy tasks and approvals

- POST `/api/v1/execution/tasks` — create task (goal, max_steps, max_retries).
- GET `/api/v1/execution/tasks` — list tasks.
- GET `/api/v1/execution/tasks/{task_id}` — task status and artifacts.
- GET `/api/v1/execution/approvals` — list pending approvals (“Approval Needed” inbox).
- POST `/api/v1/execution/approvals/{approval_request_id}` — approve or deny (body: `{ "approved": true }`).

Task store: tasks are persisted in the DB (`Task` table); approvals queue and execution requests remain in `config/execution_tasks.json`. See `backend/services/execution_task_store.py`.

## How to add a new tool

1. Add a `ToolDef` in `backend/tools/registry.py` (`TOOL_DEFS`).
2. Add a branch in `execute_tool()` that calls your tool implementation (with rate limit and audit).
3. Optionally add a default `tool_enabled` entry in `config/execution_layer_config.json`.

## Security (local token)

When `EXECUTION_TOKEN` is set in the environment, all `/api/v1/execution/*` endpoints require the `X-Execution-Token` header. If the header is missing or wrong, the server returns 401. When `EXECUTION_TOKEN` is unset, no token is required (local dev). The dashboard sends the token from `sessionStorage.execution_token` when present; on 401 it clears it and shows an error.

## Approval mode

When `approval_mode` is `require_approval` and the tool is risky (risk_level ≥ medium), the run must include a valid `approval_id`. Create one with `POST /api/v1/execution/approve?tool_name=...` (valid for 300 seconds).

## Budget guard

`max_steps_per_run` and `max_retries_per_tool` from config are enforced in playbook execution (see `backend/services/tool_playbooks.py`).

## 1-command smoke tests

**Basic (no token):**  
From project root with backend running:

```bash
python scripts/smoke_execution_layer.py
```

**V2 (token, approval, apply_patch dry_run):**

```bash
python scripts/smoke_execution_layer_v2.py
```

With token required on server:

```bash
set EXECUTION_TOKEN=your_secret
python scripts/smoke_execution_layer_v2.py --token your_secret
```
