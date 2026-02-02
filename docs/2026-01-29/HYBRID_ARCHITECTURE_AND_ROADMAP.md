# Hybrid Architecture & 4-Prompt Roadmap

**Date:** 2026-01-29  
**Scope:** Moltbot-style local control + Manus-style sandbox + Daena as governor. No proprietary code copy; no duplicate apps/folders.

---

## 1. Architecture Summary

| Layer | Role | Status |
|-------|------|--------|
| **Daena Core** | Orchestrator & governor (approves, logs, limits) | In place |
| **Execution Layer** | Tool registry, allowlist, dry-run, audit, UI | **Implemented (Prompt 1)** |
| **Windows Node** | Local “hands” (OS, browser, downloads) | **Not yet (Prompt 2)** |
| **Autonomy Loop** | Plan → Execute → Verify → Next step; 24/7 tasks | Partial (autonomous routes exist) |
| **Sandbox Worker** | Isolated runs for risky work (downloads/builds) | **Not yet (Prompt 4)** |

**Governance rules (keep these):**

- Agents do **not** execute directly; they create **ToolRequests**.
- Daena approves or asks founder depending on risk.
- Execution goes through Execution Layer to the right node (Windows or sandbox).
- Every action is logged and reversible where possible.
- Downloads allowlisted or sandboxed; high-risk actions require approval.

---

## 2. Prompt 1 — Execution Layer (VERIFIED)

### 2.1 Endpoints (all wired in `main.py` via `safe_import_router("execution_layer")`)

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/execution/tools` | List tools with enabled state |
| POST | `/api/v1/execution/run` | Run tool (body: `tool_name`, `args`, `dry_run`, optional `approval_id`) |
| GET | `/api/v1/execution/logs?limit=N` | Recent audit entries |
| GET | `/api/v1/execution/config` | Approval mode, budget (max_steps, max_retries) |
| PATCH | `/api/v1/execution/config` | Update approval mode / budget |
| PATCH | `/api/v1/execution/tools/{name}/enabled?enabled=true\|false` | Enable/disable tool |
| POST | `/api/v1/execution/approve?tool_name=...` | Create short-lived approval for risky tool (TTL 300s) |

**Token:** When `EXECUTION_TOKEN` is set, all relevant endpoints require `X-Execution-Token` header (see `backend/routes/execution_layer.py` → `verify_execution_token`).

### 2.2 Config & allowlist

- **Config file:** `config/execution_layer_config.json`  
  - `tool_enabled`, `approval_mode`, `require_approval_for_risky`, `max_steps_per_run`, `max_retries_per_tool`, `dry_run_default`.
- **Service:** `backend/services/execution_layer_config.py`  
  - Load/save, risk levels, approval create/consume, `set_tool_enabled`, `is_tool_enabled`.

### 2.3 Tool registry

- **File:** `backend/tools/registry.py`  
  - **Tools:** `git_status`, `git_diff`, `filesystem_read`, `filesystem_write`, `apply_patch`, `shell_exec` (allowlist), `web_scrape_bs4`, `browser_automation_selenium`, `desktop_automation_pyautogui`, `consult_ui`.
  - Workspace-only paths; shell allowlist from settings; audit on every run; dry_run supported.

### 2.4 Dashboard

- **File:** `frontend/templates/dashboard.html`  
  - Execution Layer card: `executionFetch('/api/v1/execution/tools')`, `.../logs?limit=5`, `.../config`, `POST .../run`, `PATCH .../tools/{name}/enabled`. Token from `sessionStorage.execution_token`.

### 2.5 Smoke tests

- **Scripts:** `scripts/smoke_execution_layer.py`, `scripts/smoke_execution_layer_v2.py`  
- **Doc:** `docs/EXECUTION_LAYER.md` (includes 1-command smoke test).

**Conclusion:** Prompt 1 is complete. Execution Layer is the single governance gate for tools; next steps add “hands” (Windows Node) and autonomy/sandbox.

---

## 3. Prompt 2 — Daena Windows Node (TODO)

**Goal:** Local “hands” so Daena can control a Windows machine via governed tools only.

**Planned pieces:**

1. **backend/services/windows_node_client.py**  
   - Call node at `http://127.0.0.1:18888` (default), request signing via token header.
2. **scripts/windows_node/**  
   - e.g. `start_windows_node.ps1` + minimal FastAPI/Flask: `POST /node/run_tool`, `GET /node/health`.
3. **Execution Layer tools:**  
   - `windows_node.safe_shell_exec`, `windows_node.file_read_workspace`, `windows_node.file_write_workspace`, `windows_node.browser_task`, `windows_node.download_allowlist`.
4. **Governance:**  
   - All `windows_node.*` tools medium+ risk → require approval when `approval_mode == require_approval`; enforce max_steps/max_retries; audit every call.
5. **Dashboard:**  
   - Pair Node (address + token stored locally, not in git), Test connection, Enable/disable node tools.

**Deliverables when done:** File list, setup instructions, smoke test (no token → fail; with token → ok; approval gate works).

---

## 4. Prompt 3 — Autonomy Loop (PARTIAL)

**Goal:** Persistent task engine and agent loop: Plan → Execute → Observe → Verify → Next step; 24/7, survive restarts.

**Existing:**  
- `backend/routes/autonomous.py`, `backend/services/autonomous_executor.py`, task/approval-related logic in founder and execution layer.

**Implemented (2026-01-29):**

1. **Task model in DB:**  
   - Tasks are now persisted in the `Task` table (`backend/database.py`). `backend/services/execution_task_store.py` uses the DB for create_task, get_task, list_tasks, update_task, add_step_result, run_task, get_next_step_plan. API shape (task_id, goal, status, step_count, max_steps, max_retries, required_approvals, artifacts, created_at, updated_at) is unchanged. Approvals queue and execution requests remain in `config/execution_tasks.json` for now.

**Still to align:**

2. **Agent loop runner:**  
   - Takes ToolRequests → Execution Layer → verify outcomes → stop and ask founder on policy triggers.
3. **Policy engine:**  
   - Risk levels per tool; require approval for financial, legal, external comms, destructive, credential access; budget and timeouts.
4. **Reporting:**  
   - Progress updates, “Approval Needed” inbox, daily summary + incident log.

**Deliverables when done:** Routes for task create/status, dashboard panels (Tasks, Approvals, Runs, Reports), one demo task (edit file → run tests → report).

---

## 5. Prompt 4 — Sandbox Worker (TODO)

**Goal:** Manus-style isolated execution for high-risk ops (downloads, builds, tests).

**Planned:**

- Sandbox in isolated env (e.g. Docker or Cloud Run job).
- Tools: download, unpack, scan, build, test, static analysis; no real secrets by default; outputs = artifacts back to Daena.
- Execution Layer target: `sandbox_worker.*`.
- Governance: Daena can route ToolRequests from Windows node to sandbox by risk; UI toggle “prefer sandbox for unknown downloads/builds”.

**Deliverable:** Minimal sandbox runner + one demo (e.g. download repo zip → scan deps → report).

---

## 6. Recommended order of work

1. **Harden Prompt 1 (optional):**  
   - Re-run `scripts/smoke_execution_layer.py` (and v2) and fix any failures; ensure dashboard token and toggles work.
2. **Implement Prompt 2 (Windows Node):**  
   - Adds local “hands” without changing Daena’s role as governor; all execution still through Execution Layer.
3. **Implement Prompt 3 (Autonomy loop):**  
   - Task model, loop runner, policy engine, reporting so Daena can run multi-step tasks and “ask only when needed”.
4. **Implement Prompt 4 (Sandbox):**  
   - Safe execution for risky work; keep Windows Node for trusted local control.

---

## 7. File reference (Prompt 1)

| Purpose | Path |
|---------|------|
| Execution Layer API | `backend/routes/execution_layer.py` |
| Execution Layer config service | `backend/services/execution_layer_config.py` |
| Execution Layer config file | `config/execution_layer_config.json` |
| Tool registry & execute | `backend/tools/registry.py` |
| Router registration | `backend/main.py` (safe_import_router("execution_layer")) |
| Dashboard Execution Layer card | `frontend/templates/dashboard.html` |
| Docs | `docs/EXECUTION_LAYER.md` |
| Smoke tests | `scripts/smoke_execution_layer.py`, `scripts/smoke_execution_layer_v2.py` |

---

*This document is the single reference for the hybrid architecture and the 4-prompt roadmap. Update it as each prompt is completed.*
