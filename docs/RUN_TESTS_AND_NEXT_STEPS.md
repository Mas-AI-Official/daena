# Running Tests and Next Steps

## Execute smoke tests and get good results

### 1. Start the backend

In **terminal 1** (keep it open):

```bat
cd d:\Ideas\Daena_old_upgrade_20251213
scripts\start_backend_with_env.bat
```

**Preferred:** `scripts\start_backend_with_env.bat` (sets `PYTHONPATH` and `EXECUTION_TOKEN`; supports both venv_daena_main_py310 and venv_daena_audio_py310). Alternatively: `scripts\start_backend.bat` (full launcher with logging, used by **START_DAENA.bat**) or **START_DAENA.bat** for full stack. Backend runs at **http://localhost:8000**.

### 2. Set execution token

The backend must have `EXECUTION_TOKEN` set (e.g. in `.env` or environment). Use the **same value** when running tests. Default for scripts: `manual-verify-token` (set by `start_backend_with_env.bat` and `run_all_tests.ps1` when unset).

```bat
set EXECUTION_TOKEN=manual-verify-token
```

If you use a different token in `.env`, set `EXECUTION_TOKEN` to that value before running smoke/manual steps, or start the backend with the same token so they match.

### 3. Run smoke tests and manual verification steps

**Smoke tests:**

```bat
cd d:\Ideas\Daena_old_upgrade_20251213
set EXECUTION_TOKEN=your-token-here
python scripts\smoke_control_plane.py --base http://localhost:8000 --token %EXECUTION_TOKEN%
```

**Execute all manual steps (smoke + manual verification) in one go:**

**Option A — Backend already running (terminal 1):** In terminal 2 run `scripts\run_manual_steps.bat` (set `EXECUTION_TOKEN` to match backend).

**Option B — One command (starts backend, then runs smoke + manual):**

```powershell
cd d:\Ideas\Daena_old_upgrade_20251213
.\scripts\run_all_tests.ps1 -StartBackend
```

This starts the backend in a PowerShell job on **port 8001** (so it doesn't conflict with anything on 8000), runs smoke and manual verification against it, then stops the job. Exit 0 = all pass.

**Option C — After manual verification: run E2E (next step):**

```powershell
.\scripts\run_all_tests.ps1 -StartBackend -RunE2E
```

Runs smoke → manual → **E2E UI flows** (Playwright). Requires `pip install playwright` and `playwright install chromium` once. Exit 0 = smoke + manual + E2E all pass.

Or run smoke only:

```bat
scripts\run_smoke_and_verify.bat
```

**Good result:** Exit code 0 and output like `--- Result: N passed, 0 failed ---`.

**Windows Node (Pair Node) smoke test (optional):**

```bat
set EXECUTION_TOKEN=your-token-here
python scripts\smoke_windows_node.py --base http://localhost:8000 --token %EXECUTION_TOKEN%
```

Checks: no token → 401 on node/health and node/config; with token → GET config, GET health, POST config. Does not require the Windows node to be running.

**Manual verification (API equivalents of browser steps):**

```bat
set EXECUTION_TOKEN=your-token-here
set DAENA_BASE_URL=http://localhost:8000
python scripts\manual_verification_steps.py
```

Covers: token gating, skills run, execution run, proactive run_once, tasks create/run, runbook page, skills artifacts, lockdown. Exit 0 = all pass.

**If backend not reachable:** Smoke and manual verification check `GET /health` first and exit immediately with:

- `ERROR: Backend not reachable at http://localhost:8000`
- Instructions to start the backend first.

### 4. (Optional) Run E2E UI flows

Requires **Playwright** and backend running:

```bat
pip install playwright
playwright install chromium
set EXECUTION_TOKEN=your-token
python scripts\daena_ui_e2e_flows.py --base-url http://127.0.0.1:8000
```

**Good result:** `E2E flows: N checks passed` with at least 4 checks (Skills, Execution, Proactive, Runbook, etc.).

---

## CI (GitHub Actions)

Workflow **Smoke and Manual Verification** (`.github/workflows/smoke-and-manual-verification.yml`):

- On push/PR to `main` or `develop`, and on `workflow_dispatch`.
- Installs backend deps, starts backend, waits for `GET /health`, runs `smoke_control_plane.py` then `manual_verification_steps.py`, then optionally **E2E UI flows** (Playwright; `continue-on-error: true` so failures do not fail the job).
- Set repo secret `EXECUTION_TOKEN` to match your backend token, or the workflow uses `ci-smoke-token`.

## Verification checklist (release)

See **`docs/VERIFICATION_CHECKLIST.md`** for a step-by-step checklist: backend, smoke, manual verification, one-shot, UI spot checks, CI, E2E.

---

## Next steps and suggestions

### Immediate (to get green results)

1. **Start backend** – Use `scripts\start_backend_with_env.bat` (or `scripts\start_backend.bat` / **START_DAENA.bat**) in one terminal.
2. **Set EXECUTION_TOKEN** – Must match backend config (e.g. in `.env`: `EXECUTION_TOKEN=...`).
3. **Re-run smoke** – `scripts\run_manual_steps.bat` (full) or `scripts\run_smoke_control_plane.bat` (smoke only).

### Codebase / CI

4. **CI job** – In GitHub Actions (or similar), start the backend, wait for health, then run `smoke_control_plane.py` with `EXECUTION_TOKEN` from secrets.
4b. **Batch scripts** – Scripts are consolidated: one canonical backend starter (`start_backend_with_env.bat`), one full test entry (`run_manual_steps.bat`); thin wrappers call these to avoid duplication.
5. **Single “run all” script** – Use `scripts\run_manual_steps.bat` (health + smoke + manual verification; backend must be running). For automated start-backend-then-test: `.\scripts\run_all_tests.ps1 -StartBackend` or `scripts\run_all_tests_and_backend.bat`.

### Product / features (from MINIMAX report)

6. **E2E with token in UI** – In `daena_ui_e2e_flows.py`, add a step that sets the execution token in the Dashboard/App Setup so “Run” steps (e.g. Skills run) succeed without manual token setup.
7. **MCP server wiring** – Connect Integrations “MCP servers” (GitHub, Cloudflare, etc.) to real MCP client calls so tools can be swapped without rewriting agent logic.
8. **Rate limiting in production** – Enable `RATE_LIMIT_ENABLED` and frontend XSS sanitization where recommended in `docs/2026-01-29/`.

### Operations

9. **Health check** – Use `GET /api/v1/health/` (or existing health route) for readiness probes and for the smoke “backend up” check if you prefer it over `/api/v1/skills`.
10. **Runbook** – Share `docs/MINIMAX_IMPLEMENTATION_REPORT.md` and `/ui/runbook` with the team for troubleshooting failed tasks and execution issues.

---

## Control Plane (new version)

- **Single entry**: `/ui/control-plane` – Brain & API, Integrations/App Setup, Skills, Execution, Proactive, Tasks+Runbook+Approvals, Provider onboarding in one page (tabs).
- **Old URLs** (e.g. `/ui/brain-settings`, `/ui/skills`) redirect to `/ui/control-plane#&lt;section&gt;` when opened directly. Use `?embed=1` to load the page without redirect (e.g. for E2E or iframes).
- **System Monitor** removed from sidebar; content embedded in Dashboard (System Health: Backend Status + API Endpoints). `/ui/system-monitor` redirects to `/ui/dashboard`.

---

## Batch scripts reference (scripts\*.bat)

**Canonical (use these):**

| Script | Purpose |
|--------|---------|
| `start_backend_with_env.bat` | Start backend with PYTHONPATH and EXECUTION_TOKEN (preferred for tests). |
| `run_manual_steps.bat` | Health check + smoke + manual verification (backend must be running). |
| `run_smoke_control_plane.bat` | Smoke only (control plane). |
| `run_all_tests_and_backend.bat` | Start backend in new window, then run comprehensive_test_all_phases.py. |
| `verify_all.bat` | Quick checks: Python, imports, DB, routes, health (no smoke). |

**Thin wrappers (no duplication):** `run_smoke_and_verify.bat` → smoke only (calls `run_smoke_control_plane.bat`). `simple_start_backend.bat` and `quick_start_backend.bat` → call `start_backend_with_env.bat`. `start_and_test.bat` and `test_all.bat` → call `run_all_tests_and_backend.bat`.

**Other:** `start_backend.bat` is used by **START_DAENA.bat** with args (logging, preflight). Use it when launching the full stack via START_DAENA.bat.

---

## Quick reference

| Goal              | Command / action |
|-------------------|-------------------|
| Start backend     | `scripts\start_backend_with_env.bat` (from project root) |
| Run smoke + manual verification | `scripts\run_manual_steps.bat` (backend must be running) |
| Smoke + manual (one command) | `.\scripts\run_all_tests.ps1 -StartBackend` (backend on port 8001) |
| **Next step after manual: E2E** | `.\scripts\run_all_tests.ps1 -StartBackend -RunE2E` (smoke → manual → E2E) |
| **Next step after E2E: UI spot checks** | `.\scripts\open_ui_spot_checks.ps1 -Port 8000 -StartBackend` — starts backend if needed, checks health, then opens Dashboard, Control Plane, Skills, Execution, Tasks in browser. Omit `-StartBackend` if backend is already running. |
| Smoke only        | `scripts\run_smoke_control_plane.bat` or `scripts\run_smoke_and_verify.bat` |
| Run E2E (UI) only | `python scripts\daena_ui_e2e_flows.py --base-url http://127.0.0.1:8000` (set EXECUTION_TOKEN) |
| Start backend + comprehensive tests | `scripts\run_all_tests_and_backend.bat` |
| Backend not reachable | Scripts use `GET /health`; exit with instructions. |
