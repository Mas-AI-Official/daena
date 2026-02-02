# Execution Layer — Repo Audit Report

## Step 1: Audit results (before and after)

### Execution runner / service

| Item | Status | Location |
|------|--------|----------|
| Tool runner | **Exists** | `backend/services/cmp_service.py` → `run_cmp_tool_action()`; `backend/tools/registry.py` → `execute_tool()` |
| Invocation | **Exists** | `POST /api/v1/tools/execute`, `POST /api/v1/execution/run` (new) |

### Tool registry

| Item | Status | Location |
|------|--------|----------|
| Registry | **Exists** | `backend/tools/registry.py` — `TOOL_DEFS`, `list_tools()` |
| Tools | **Exists** | `web_scrape_bs4`, `browser_automation_selenium`, `desktop_automation_pyautogui`, `consult_ui`, `git_status` (added) |

### Permission / approval model

| Item | Status | Location |
|------|--------|----------|
| Allowlist | **Added** | `config/execution_layer_config.json` — `tool_enabled` per tool |
| Approval mode | **Exists + extended** | `backend/services/unified_tool_executor.py` (HIGH_IMPACT_ACTIONS); config `approval_mode`, `require_approval_for_risky` |
| Enabled check in runner | **Added** | `backend/tools/registry.py` — `_is_tool_enabled()` before execute |

### Logging / audit trail

| Item | Status | Location |
|------|--------|----------|
| Audit log (JSONL) | **Exists** | `backend/tools/audit_log.py` → `logs/tools_audit.jsonl` |
| DB audit (optional) | **Exists** | `backend/database.py` — `ToolExecution`; `backend/routes/daena.py` — `log_tool_execution()` |
| Execution Layer logs API | **Added** | `GET /api/v1/execution/logs` reads JSONL |

### UI surface

| Item | Status | Location |
|------|--------|----------|
| Tools panel (basic) | **Existed** | `frontend/templates/dashboard.html` — Quick Actions / Tools reference in docs |
| **Execution Layer panel** | **Added** | `frontend/templates/dashboard.html` — Execution Layer card: tool toggles, recent runs, approval mode, budget |

---

## Step 2: What was implemented

1. **MODELS_ROOT (brain root)**  
   - `backend/config/settings.py`: `models_root` (env `MODELS_ROOT`), `ollama_models_path` derived from it when unset.  
   - `backend/services/local_llm_ollama.py`: Uses `settings.models_root` for fallback path.

2. **Execution Layer API**  
   - `backend/routes/execution_layer.py`:  
     - `GET /api/v1/execution/tools` — list tools with `enabled`  
     - `POST /api/v1/execution/run` — run tool (optional `dry_run`)  
     - `GET /api/v1/execution/logs` — recent audit entries  
     - `GET/PATCH /api/v1/execution/config` — approval mode, budget  
     - `PATCH /api/v1/execution/tools/{name}/enabled` — toggle tool  

3. **Tool registry**  
   - `backend/tools/registry.py`:  
     - `list_tools(include_enabled=True)`, `execute_tool(..., dry_run=False)`, enabled check, `git_status` tool.  
   - `backend/services/cmp_service.py`: `dry_run` passed through to `execute_tool`.

4. **Config**  
   - `config/execution_layer_config.json`: tool_enabled, approval_mode, max_steps_per_run, max_retries_per_tool, dry_run_default.  
   - `backend/services/execution_layer_config.py`: load/save, `is_tool_enabled`, `set_tool_enabled`, `update_execution_config`.

5. **Dashboard UI**  
   - Execution Layer card: tool toggles, recent runs, approval mode, budget; JS calls `/api/v1/execution/*`.

6. **Docs and smoke test**  
   - `docs/EXECUTION_LAYER.md`: usage, API, config, safety, add tool, 1-command test.  
   - `scripts/smoke_execution_layer.py`: GET tools, POST run (git_status, dry_run then real), GET logs and print latest entry.

---

## Step 3: Run instructions

### Enable the Execution Layer

- Backend is already wired: start app as usual (e.g. `uvicorn backend.main:app --host 0.0.0.0 --port 8000`).  
- Optionally set `MODELS_ROOT` to your shared brain path (e.g. `D:\Ideas\MODELS_ROOT`).  
- Tool toggles: edit `config/execution_layer_config.json` or use Dashboard → Execution Layer or `PATCH /api/v1/execution/tools/{name}/enabled`.

### Add a new tool

1. Add `ToolDef` in `backend/tools/registry.py` (`TOOL_DEFS`).  
2. Add branch in `execute_tool()` that runs the tool and respects rate limit + audit.  
3. Add default in `config/execution_layer_config.json` under `tool_enabled` if needed.

### How the UI calls the backend

- Dashboard loads: `GET /api/v1/execution/tools`, `GET /api/v1/execution/logs?limit=5`, `GET /api/v1/execution/config`.  
- Toggle: `PATCH /api/v1/execution/tools/{name}/enabled?enabled=true|false`.

### Keep it safe on a developer machine

- Run backend on localhost; use auth/token in production.  
- Risky tools (browser, desktop) are off by default in `execution_layer_config.json`.  
- Use `dry_run=true` to test without executing.  
- Audit log: `logs/tools_audit.jsonl`.

---

## 1-command proof-it-works test

With backend **already running**:

```bash
python scripts/smoke_execution_layer.py
```

This will:

1. Call `GET /api/v1/execution/tools`  
2. Call `POST /api/v1/execution/run` with `tool_name=git_status`, `dry_run=true`  
3. Call `POST /api/v1/execution/run` with `tool_name=git_status`, `dry_run=false`  
4. Call `GET /api/v1/execution/logs?limit=1` and print the latest audit log entry  

Optional: start backend and run the test in one go:

```bash
python scripts/smoke_execution_layer.py --start
```

---

## Changed / new files list

| File | Change |
|------|--------|
| `backend/config/settings.py` | `models_root`, `ollama_models_path` from root, validator |
| `backend/services/local_llm_ollama.py` | Use `settings.models_root` for fallback path |
| `backend/tools/registry.py` | `list_tools(include_enabled)`, `execute_tool(dry_run)`, enabled check, `git_status` |
| `backend/services/cmp_service.py` | `dry_run` parameter |
| `backend/routes/tools.py` | `ToolExecuteRequest.dry_run`, pass to `run_cmp_tool_action` |
| `backend/routes/execution_layer.py` | **New** — Execution Layer API |
| `backend/services/execution_layer_config.py` | **New** — config load/save, enabled toggles |
| `config/execution_layer_config.json` | **New** — default config |
| `backend/main.py` | Include `execution_layer` router |
| `frontend/templates/dashboard.html` | Execution Layer card + CSS + JS |
| `docs/EXECUTION_LAYER.md` | **New** — Execution Layer doc |
| `docs/EXECUTION_LAYER_AUDIT.md` | **New** — This audit |
| `scripts/smoke_execution_layer.py` | **New** — 1-command smoke test |
