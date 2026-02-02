# MiniMax Agent Takeaways – Daena Implementation Report

## Summary

Daena was upgraded with MiniMax-style agent runtime, E2E/browser tools, MCP-first integrations, and UX improvements (task timeline, artifacts viewer, Runbook, proactive E2E/health rules). No WhatsApp/Telegram/social connectors were added. All changes reuse existing endpoints and pages.

---

## 1. File-by-File Implementation

### A) Agent Runtime (plan → execute → verify, persist, artifacts)

| File | Change |
|------|--------|
| `backend/services/execution_task_store.py` | Added `get_next_step_plan(task_id)` returning `{ tool_name, args }` for next step (step 0: repo_git_status, step 1: run_tests or repo_scan, step 2: optional browser_e2e_runner). Added `add_step_result(task_id, step_index, tool_name, result, artifact_files)` to append step result and artifact paths; marks task completed when no more plan. Updated `run_task(task_id)` to set status running, call `get_next_step_plan`, return task + `planned_tool` for the route to execute. |
| `backend/routes/execution_layer.py` | Updated `POST /tasks/{task_id}/run`: after `run_task` gets `planned_tool`, calls `execute_tool(planned_tool)`, then `add_step_result` with result and artifact paths (report_path, report_md_path, screenshot path). Returns task + step_result. |

### B) New Tools (safe, defensive only)

| File | Change |
|------|--------|
| `backend/tools/executors/browser_e2e_runner.py` | **New.** Playwright E2E runner: allowlisted URLs only (localhost/127.0.0.1), steps (navigate, screenshot, click, fill), produces JSON + markdown report. |
| `backend/tools/executors/screenshot_capture.py` | **New.** Playwright screenshot of allowlisted URL only. |
| `backend/tools/executors/repo_scan.py` | **New.** Read-only: dependencies (requirements.txt, package.json) + basic secret-pattern scan (local only, no exfiltration). |
| `backend/tools/registry.py` | Registered `browser_e2e_runner`, `screenshot_capture`, `repo_scan` in TOOL_DEFS; added execute_tool branches (async for E2E/screenshot, sync for repo_scan). |
| `backend/services/execution_layer_config.py` | Added risk levels and default enabled for `browser_e2e_runner`, `screenshot_capture`, `repo_scan`. |

### C) MCP-First Integrations

| File | Change |
|------|--------|
| `backend/services/integration_registry.py` | In `get_default_integrations()`, added MCP-first entries: **GitHub**, **Cloudflare**, **GCP**, **Azure/OpenAI**, **Local models (Ollama)** with `mcp_server`, `enabled_by_default: false` (except local_models). Existing integrations kept; no duplicate UIs. |

### D) UX Upgrades

| File | Change |
|------|--------|
| `frontend/templates/tasks.html` | Task detail: **Step timeline** (per-step tool_name, result_status, ts), **Artifacts** list (artifact_files from steps). Added **Runbook** panel: “Suggested next actions when a task fails” (check logs, re-run step, ensure token/lockdown). |
| `frontend/templates/skills.html` | **Artifacts in UI**: After run, "View last artifact" link; **Recent artifacts** section with `GET /api/v1/skills/artifacts` list + View buttons. |
| `backend/routes/skills.py` | **GET /api/v1/skills/artifacts** (with token): list recent artifact filenames (newest first, limit default 20). |
| `frontend/templates/execution.html` | **Live Audit**: "Live (auto-refresh 5s)" checkbox; when on, polls execution logs every 5s. |
| `frontend/templates/runbook.html` | **New.** Runbook page: "When a task fails", "When execution is blocked", **Quick links** (Execution, Tasks, Incident Room, Approvals, Founder Panel, App Setup). |
| `backend/routes/ui.py` | **GET /ui/runbook** → runbook.html; sidebar Runbook link after Tasks. |
| `backend/routes/proactive.py` | Added default rules: **E2E regression check nightly** (cron `0 2 * * *`, event_trigger `e2e_regression`), **Notify on failing health checks** (event_trigger `health_fail`). |

### E) Governance (unchanged; reinforced)

- Token gating: `GET /api/v1/execution/tools` and run/approve endpoints require `X-Execution-Token` (401 if not set).
- Daena-only execution: sandboxed agents use `POST /api/v1/execution/request`; approval runs tool via Daena.
- Lockdown: `_check_lockdown()` in run and approve blocks execution when active.
- Audit: every tool run logged in `logs/tools_audit.jsonl`.

---

## 2. Smoke Tests

Location: `scripts/smoke_control_plane.py`.

Added/updated:

- **13** Create task (`POST /api/v1/execution/tasks`) with goal + max_steps.
- **14** Run one step (`POST /api/v1/execution/tasks/{id}/run`), verify task has artifacts or status completed/pending.
- **15** `GET /api/v1/execution/logs` – verify audit log returns entries.
- **16** `repo_scan` tool via `POST /api/v1/execution/run` (read-only).
- **17** `GET /api/v1/skills/artifacts` (with token) – list artifact filenames.
- **18** `GET /ui/runbook` – Runbook page returns 200 and contains "Runbook".

Existing:

- **1** Token gating: `GET /api/v1/execution/tools` without token → 401 when EXECUTION_TOKEN set.
- **8–12** Execution Broker: submit request (repo_git_status) → approve → execution_result → audit log; shell_exec request → 403.

Run:

```bash
cd d:\Ideas\Daena_old_upgrade_20251213
set EXECUTION_TOKEN=your-token
python scripts/smoke_control_plane.py
```

---

## 3. Manual Verification Steps (Browser)

1. **Token gating**  
   Open Execution page without setting Execution Token in Dashboard → tools/list should show 401 or “Set Execution Token”. Set token in Dashboard → refresh → tools and logs load.

2. **Skills → Repo Health Check → artifact**  
   Open Skills, run “Repo Health Check” (with Execution Token). Verify success and that any artifact or log appears (Execution logs or task artifact).

3. **Execution → git_status → log**  
   Use Execution page “Run” (or API) to run `repo_git_status` / `git_status`. Open Execution logs → last entry is repo_git_status.

4. **Proactive → run_once → event**  
   Open Proactive, create or use a rule, click “Run once”. Open Events → new event appears.

5. **Tasks → create → run step → timeline + artifacts**  
   Create task with goal “Smoke agent runtime”. Click “Run step” once or twice. Open task “View” → Step timeline shows repo_git_status (and optionally run_tests/repo_scan); Artifacts list shows any report_path/screenshot path if produced.

6. **Runbook**  
   Open Runbook from sidebar (/ui/runbook). Verify "When a task fails", "When execution is blocked", and Quick links.

7. **Skills artifacts**  
   Open Skills, run a skill (e.g. Repo Health Check). Verify "View last artifact" after run; Recent artifacts section lists artifacts with View buttons.

   Runbook panel also on Tasks page.

8. **E2E runner (allowlisted URL)**  
   With backend and Playwright installed, run `browser_e2e_runner` with `base_url: http://127.0.0.1:8000` (e.g. via Execution run or task step). Verify report or screenshot is produced; non-allowlisted URL should be rejected.

9. **Lockdown**  
   Incident Room → Lockdown. Then Execution run or task run → should return 423 Locked.

---

## 4. Hard Rules Respected

- No hack-back, no customer surveillance, no accessing non-public data.
- E2E and screenshot tools: allowlisted URLs only (localhost/127.0.0.1).
- repo_scan: read-only, local workspace, no exfiltration.
- No new parallel UIs; reused Execution, Tasks, Proactive, Integrations.

---

## 5. Completed (Follow-up)

- **Skills artifact UI**: Run returns `artifact_path`; "View last artifact" + Recent artifacts section with `GET /api/v1/skills/artifacts` and View buttons.
- **Execution Live Audit**: Checkbox "Live (auto-refresh 5s)" on Execution page; polls logs every 5s when enabled.
- **Runbook page**: `/ui/runbook` with suggested actions and quick links; sidebar link; smoke test 18 and E2E step 7.

## 6. Completed (CI)

- **Smoke + manual verification in CI**: `.github/workflows/smoke-and-manual-verification.yml` – start backend, wait for `/health`, run smoke then manual verification, then optional E2E UI flows (Playwright; `continue-on-error: true`). Set `EXECUTION_TOKEN` in repo secrets or uses `ci-smoke-token`.

## 7. Completed (E2E Skills run)

- **E2E: run skill from UI**: When `--token` is set, step 1b clicks the first "Run" button on the Skills page and verifies the run result area shows content (success/artifact/result/error).

## 8. Completed (Docs)

- **MCP wiring next steps**: `docs/MCP_WIRING_NEXT_STEPS.md` – what wiring would add (MCP client layer, tool routing, secrets, health), suggested order, and references.
- **Verification checklist**: `docs/VERIFICATION_CHECKLIST.md` – release checklist: backend, smoke, manual verification, one-shot, UI spot checks, CI, E2E.

## 9. Optional Next Steps

- **E2E flows for Daena UI**: Login/token set → Skills run Repo Health Check → Execution run git_status → Proactive run_once → verify artifacts/events (automated Playwright script against allowlisted base_url).
- **Artifact storage**: Task artifacts in `data/task_artifacts`; Skills artifacts in `data/skill_artifacts` with list + view in UI (done).
- **MCP server wiring**: Connect Integrations “MCP servers” (GitHub, Cloudflare, etc.) to actual MCP client calls so tools can be swapped without rewriting agent logic.
