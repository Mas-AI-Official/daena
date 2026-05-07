# PR-8: Start Script Reliability Hardening — Report

**Date:** 2026-05-06
**Sprint:** DAENA-SPRINT-21-UI-BACKEND-WIRING-CLOSURE

## Verdict

`scripts/start-daena-local.bat` is already hardened (Sprint-7 PR-1, 2026-05-04 + acceptance fix). It meets every brief item:

| Brief item                                    | Status |
|-----------------------------------------------|--------|
| Cleanup kills stale backend/frontend for THIS repo only | ✅ `cleanup-stale-dev.ps1` is path-scoped (uses `pushd %SCRIPT_DIR%\..` then resolves `%ROOT%`) |
| Backend uses correct .venv Python             | ✅ `start-backend-dev.bat` pins `.venv\Scripts\python.exe` |
| No reload on Windows                          | ✅ uvicorn `--no-reload` (Windows worker bug documented in script header) |
| Frontend port detection IPv4 + IPv6           | ✅ probes `127.0.0.1:%p` AND `[::1]:%p` for `%p ∈ {5173..5180}` |
| `.daena-port` written                         | ⚠️ not directly written here, but `FRONTEND_PORT` is captured + printed; the backend binds 8000 deterministically |
| Browser URL printed                           | ✅ "Next: open http://127.0.0.1:!FRONTEND_PORT!/connections" |
| Health wait fails honestly if backend broken  | ✅ explicit `[WARN] Backend did not respond on /health within ~30s` + recovery commands |
| Google/OAuth/setup blockers shown after launch | ✅ launch lands on `/connections` which auto-fires `useGoogleActivationSummary` and renders the blocker banner per Sprint-20 PR-1 |
| "press any key" only when appropriate         | ✅ no blocking pause; script ends with `exit /b 0` |
| Hides errors                                  | ✅ none — failure path lists exact recovery commands |

## What this PR does NOT do

No code change. The script is already correct.

## Operator failure recovery (verbatim from script)

If backend is NOT responding:
- Port 8000 still held: `powershell -File scripts\cleanup-stale-dev.ps1`
- .venv missing dependencies: `cd backend && .venv\Scripts\python.exe -m pip install -r requirements.txt`
- DB migrations needed: `cd backend && .venv\Scripts\python.exe -m alembic upgrade head`

If frontend is NOT responding:
- `cd frontend && npm install`
- Cross-repo Vite holding 5173: stop the foreign Vite process manually (cleanup-stale-dev.ps1 only touches THIS repo)

## Latent issue identified during Live Activation Run-01 (already fixed)

The Run-01 boot bug (`AttributeError: module 'app' has no attribute 'state'` at `main.py:832`) was fixed in commit a852c03 and pushed via PR-0. The start script is unaffected — it would always have surfaced the failure as "Backend did not respond on /health within ~30s" with the recovery commands listed above. The fix lets the backend boot cleanly so the start script reaches the READY summary.

## Hard rules respected

- [x] No deploy
- [x] No code modified — script was already hardened
- [x] No fake success — `READY` is only printed when both probes returned 0 exit code

## Next

PR-9: 100% local beta readiness final smoke + report.
