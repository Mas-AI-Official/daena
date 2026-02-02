# Hybrid Architecture — Implementation Report (2026-01-29)

This report lists file-by-file changes for Prompts 1–4 (Execution Layer verification, Windows Node, Autonomy tasks/approvals, Sandbox worker).

---

## Prompt 1 — Execution Layer (verified, no code changes)

- **backend/routes/execution_layer.py** — Already has GET /tools, POST /run, GET /logs, GET|PATCH /config, PATCH /tools/{name}/enabled, POST /approve; token via `verify_execution_token`.
- **backend/services/execution_layer_config.py** — Config load/save, risk levels, approval create/consume.
- **config/execution_layer_config.json** — Tool toggles, approval_mode, budget.
- **backend/tools/registry.py** — Tool defs and execute_tool (git_status, git_diff, filesystem_read/write, apply_patch, shell_exec, web_scrape_bs4, etc.).
- **frontend/templates/dashboard.html** — Execution Layer card calls execution/tools, run, logs, config, toggle.
- **scripts/smoke_execution_layer.py** — Updated to send `X-Execution-Token` when `EXECUTION_TOKEN` env is set.

---

## Prompt 2 — Daena Windows Node

**New files:**

- **backend/services/windows_node_client.py** — `get_node_url()`, `get_node_token()`, `node_health()`, `node_run_tool(tool_name, args)`; calls `http://127.0.0.1:18888` by default with optional `X-Windows-Node-Token`.
- **scripts/windows_node/node_server.py** — Minimal FastAPI: GET /node/health, POST /node/run_tool; tools: safe_shell_exec, file_read_workspace, file_write_workspace; bind 127.0.0.1:18888; token from env WINDOWS_NODE_TOKEN.
- **scripts/windows_node/start_windows_node.ps1** — Start node server (PowerShell).
- **scripts/windows_node/start_windows_node.bat** — Start node server (CMD).
- **scripts/windows_node/README.md** — Setup and usage.

**Modified:**

- **backend/config/settings.py** — Added `windows_node_url` (validation_alias `WINDOWS_NODE_URL`).
- **backend/services/execution_layer_config.py** — Added TOOL_RISK_LEVELS and tool_enabled for `windows_node_safe_shell_exec`, `windows_node_file_read_workspace`, `windows_node_file_write_workspace`.
- **backend/tools/registry.py** — Added TOOL_DEFS for windows_node_* and execute_tool branches that call `windows_node_client.node_run_tool`.
- **backend/routes/execution_layer.py** — Added GET /api/v1/execution/node/health (test Windows Node connection).
- **frontend/templates/dashboard.html** — Added “Windows Node (Moltbot-style hands)” section with “Test connection” button and `testWindowsNode()` calling /api/v1/execution/node/health.

---

## Prompt 3 — Autonomy tasks and approvals

**New files:**

- **backend/services/execution_task_store.py** — In-memory store (+ optional JSON at config/execution_tasks.json): create_task, get_task, list_tasks, update_task, add_approval_request, list_approvals_pending, approve.

**Modified:**

- **backend/routes/execution_layer.py** — Added: POST /tasks (TaskCreate), GET /tasks, GET /tasks/{task_id}, GET /approvals, POST /approvals/{approval_request_id} (ApprovalDecision).

---

## Prompt 4 — Sandbox worker

**New files:**

- **backend/tools/executors/sandbox_worker.py** — `run(args)`: run allowlisted command (pip list, pip show, pip download, etc.) in temp dir; returns stdout/stderr/returncode.

**Modified:**

- **backend/services/execution_layer_config.py** — Added risk level and tool_enabled for `sandbox_worker_run`.
- **backend/tools/registry.py** — Added TOOL_DEF for sandbox_worker_run and execute_tool branch calling sandbox_worker.run.

---

## Smoke tests

- **scripts/smoke_execution_layer.py** — Sends X-Execution-Token when EXECUTION_TOKEN is set.
- **scripts/smoke_execution_layer_v2.py** — Already validates token auth, POST /approve, apply_patch dry_run, git_status.

**Windows Node smoke (manual):**

1. Start node: `scripts\windows_node\start_windows_node.bat` (or .ps1).
2. Set WINDOWS_NODE_TOKEN and WINDOWS_NODE_URL on backend if desired.
3. In dashboard, Execution Layer → “Test connection” → should show “Node OK” if node is running.

---

## Summary

| Component            | Status   | Paths |
|----------------------|----------|--------|
| Execution Layer      | Verified | execution_layer.py, execution_layer_config.py, registry.py, dashboard |
| Windows Node client | Done     | windows_node_client.py |
| Windows Node server | Done     | scripts/windows_node/* |
| Windows Node tools   | Done     | registry.py, execution_layer_config.py |
| Node health API      | Done     | GET /api/v1/execution/node/health |
| Dashboard Pair Node  | Done     | dashboard.html “Test connection” |
| Task store           | Done     | execution_task_store.py |
| Task/approval API    | Done     | POST/GET /tasks, GET /approvals, POST /approvals/{id} |
| Sandbox worker       | Done     | executors/sandbox_worker.py, registry.py, execution_layer_config.py |
