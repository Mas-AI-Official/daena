# Launch And Test Report

Date: 2026-04-30

## Frontend

Status: running.

Evidence:

- `node_repl` fetched `http://localhost:5173/src/pages/ConnectionsPage.tsx` with HTTP 200.
- Transformed module contains `Configured, untested`, `onRefresh`, and the no-safe-test title.
- Transformed module no longer contains the stale `Database` import.
- `node_repl` fetched `http://localhost:5173/src/pages/SecurityDashboardPage.tsx` with HTTP 200.
- Security module contains `SECURITY_REQUEST_TIMEOUT_MS` and explicit backend failure copy.

## Backend

Status: not running now.

Evidence:

- `node_repl` probe of `http://127.0.0.1:8000/health` returns `ECONNREFUSED`.
- Windows Python venv cannot import `asyncio` because `_overlapped` fails with `WinError 10106`.
- WSL command execution fails with `Wsl/Service/0x8007072c`.
- `wsl.exe --shutdown` did not repair command execution.

## Source Validation

- `backend/app/services/runtime_truth_registry.py` compiles via Python `compile(...)` without writing pycache.
- `frontend/src/pages/ConnectionsPage.tsx` transforms through Vite.
- `frontend/src/pages/SecurityDashboardPage.tsx` transforms through Vite.

## Not Passed

- Backend launch.
- `/health` live check after latest source patch.
- `/api/v1/runtime/truth` live check after latest source patch.
- Full frontend page screenshot after backend recovery.

## Next Required Command Outside This Broken Shell

From a normal Windows terminal or a repaired WSL session:

```powershell
wsl -d kali-linux -- bash /mnt/d/Ideas/Daena/backend/start-detached.sh
```

Then verify:

```powershell
# Use browser/node_repl if PowerShell curl remains broken.
GET http://127.0.0.1:8000/health
GET http://127.0.0.1:8000/api/v1/runtime/truth
```
