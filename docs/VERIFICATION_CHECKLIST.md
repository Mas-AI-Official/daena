# Verification Checklist (Release / Manual Steps)

Use this before release or when verifying the control plane.

## 1. Backend up

- [ ] Start backend: `scripts\start_backend_with_env.bat` (or `START_DAENA.bat`) in terminal 1.
- [ ] `GET http://localhost:8000/health` returns 200.

## 2. Smoke tests

- [ ] Set `EXECUTION_TOKEN` to match backend (or use `manual-verify-token` if backend uses it).
- [ ] Run: `python scripts\smoke_control_plane.py --base http://localhost:8000 --token <token>`
- [ ] Result: `--- Result: N passed, 0 failed ---`
- **If you get 401 with token**: Backend and test must use the same token. Easiest: run `scripts\run_all_tests.ps1 -StartBackend` — it starts the backend in a job on **port 8001** with the same token and runs smoke + manual verification. Or start backend manually on 8000 with `set EXECUTION_TOKEN=manual-verify-token` and run smoke with `--token manual-verify-token`.

## 3. Manual verification steps (API)

- [ ] Run: `python scripts\manual_verification_steps.py` (with `DAENA_BASE_URL` and `EXECUTION_TOKEN` set).
- [ ] Result: `--- Result: N passed, 0 failed ---`

### Next step after manual verification passes

Run **E2E UI flows** (optional) so smoke + manual + E2E all pass in one go:

```powershell
.\scripts\run_all_tests.ps1 -StartBackend -RunE2E
```

This starts the backend on port 8001, runs smoke, then manual verification, then E2E (Playwright). Requires `pip install playwright` and `playwright install chromium` once. Exit 0 = all pass.

Alternatively, run E2E only (backend must be up): `python scripts\daena_ui_e2e_flows.py --base-url http://127.0.0.1:8000 --token <token>` (or use port 8001 if you started with `run_all_tests.ps1 -StartBackend`).

### Next step after E2E passes

1. **UI spot checks (§5)** — Open the UI in a browser and verify token gating, Skills run, Execution, Runbook (Tasks tab), Lockdown. From project root:
   ```powershell
   .\scripts\open_ui_spot_checks.ps1 -Port 8000 -StartBackend
   ```
   This checks that the backend is reachable (or starts it with `-StartBackend`), then opens Dashboard, Control Plane, Skills, Execution, and Tasks+Runbook. If the backend is already running on 8000, omit `-StartBackend`. Use `-Port 8001` if you usually start with `run_all_tests.ps1 -StartBackend`.
2. **CI (§6)** — Push to `main`/`develop` and confirm the "Smoke and Manual Verification" workflow passes. Set repo secret `EXECUTION_TOKEN` (e.g. `ci-smoke-token`) if needed.

## 4. One-shot (optional)

- [ ] Run: `scripts\run_manual_steps.bat` (backend must be running). Exit 0.

## 5. UI spot checks (browser)

- [ ] **Token gating**: Execution page without token → "Set Execution Token"; set token in Dashboard → tools/logs load.
- [ ] **Skills**: Run "Repo Health Check" → success; "View last artifact" or Recent artifacts visible.
- [ ] **Execution**: Run a tool (e.g. repo_git_status) → entry in logs; "Live (auto-refresh 5s)" works.
- [ ] **Runbook**: Open `/ui/runbook` → "When a task fails", "When execution is blocked", Quick links work.
- [ ] **Tasks**: Create task, Run step → timeline and artifacts appear.
- [ ] **Lockdown**: Incident Room → Lockdown; then Execution run → 423.

## 6. CI (if applicable)

- [ ] Push to `main`/`develop` (or run workflow_dispatch) → workflow "Smoke and Manual Verification" passes.
- [ ] Repo secret `EXECUTION_TOKEN` set, or workflow uses `ci-smoke-token`.
- [ ] Optional: E2E UI flows step runs (Playwright); it uses `continue-on-error: true` so the job still passes if E2E fails.

## 7. E2E (optional, Playwright)

- [ ] `pip install playwright && playwright install chromium`
- [ ] Run: `python scripts\daena_ui_e2e_flows.py --base-url http://127.0.0.1:8000 --token <token>`
- [ ] At least 4 checks pass (Skills, Execution, Proactive, Runbook, Skills Run when token set). E2E uses `?embed=1` for direct page load.

## 8. Execution layer safety (Daena Shield)

- [ ] **Workspace allowlist**: Tool runs (filesystem_read/write, shell_exec, repo_scan, etc.) are confined via `EXECUTION_WORKSPACE_ROOT` and `_resolve_workspace_path()` in `backend/tools/registry.py` and `backend/tools/executors/repo_scan.py`; paths outside workspace raise `PolicyError`.
- [ ] **Audit logging**: Every tool run is logged via `backend/tools/audit_log.py` (`write_audit_event`) and `backend/tools/registry.py`; entries appear in `logs/tools_audit.jsonl` and are redacted (no secrets).
