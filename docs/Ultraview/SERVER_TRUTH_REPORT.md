# Server Truth Report

Date: 2026-04-30

## Current Truth

| Check | Evidence | Result |
|---|---|---|
| Backend port file | `D:\Ideas\Daena\backend\.daena-port` contains `8000`. | Correct for the active backend. |
| Backend root health | Playwright fetch `http://127.0.0.1:8000/health` returned 200 with `status=healthy`. | Backend is running. |
| Backend API health | Playwright fetch `http://127.0.0.1:8000/api/v1/health` returned 200 with `status=degraded`, `redis=unavailable`, `database=healthy`. | API is reachable. Redis is down or not configured. |
| Auth login route | Playwright fetch `POST /api/v1/auth/login` reached FastAPI and returned schema validation for a probe email. Authenticated login with founder credentials from `.env` returned 200. | Login route is reachable. |
| Frontend localhost | Playwright navigation to `http://localhost:5173` loaded the Daena login page. | Frontend is running on `localhost`. |
| Frontend 127.0.0.1 | Playwright fetch/navigation to `http://127.0.0.1:5173` failed. | Frontend is not reachable on IPv4 loopback from Playwright. |
| Shell HTTP tools | PowerShell `Invoke-WebRequest` and `curl.exe` fail with `requested service provider could not be loaded or initialized`. | Host shell networking is broken independently of Daena. |
| WSL | `wsl.exe -l -v` lists `kali-linux` running, but executing commands returns `Wsl/Service/0x8007072c`. | WSL command execution is broken. |

## Founder Symptom Verdict

The screenshot symptom `/api/v1/auth/login ECONNREFUSED 127.0.0.1:8000` was real at the time of the frontend log. Current live evidence says the backend is now reachable at `127.0.0.1:8000`. The stale symptom remains possible when the backend is stopped or when the shell/WSL runtime is broken.

The current frontend is reachable at `localhost:5173`, not `127.0.0.1:5173`. That matters because local tooling and docs mix both hostnames.

## Active Defects

1. Backend health truth is split:
   - `/health` says healthy.
   - `/api/v1/health` says degraded because Redis is unavailable.
   - UI should not collapse those into a single green active status.

2. Shell-based verification is unreliable on this machine:
   - `curl.exe` cannot open sockets.
   - PowerShell HTTP cannot open sockets.
   - WSL command execution fails.
   - Browser/Playwright can still reach the backend, so Daena itself is not necessarily down.

3. Frontend host truth is inconsistent:
   - `localhost:5173` works.
   - `127.0.0.1:5173` fails.
   - Vite proxy still targets backend `127.0.0.1:8000`, which is currently fine.

4. Header status text can still mislead:
   - `AGI ACTIVE` is driven by frontend autopilot state, not backend health.
   - It must be treated as autopilot preference, not system reachability.

## Required Fixes

- Add a backend truth endpoint for runtime/provider/MCP/plugin state rather than spreading status across `/runtimes`, `/mcp-sync`, `/connections`, `/settings`, and config files.
- Show backend degraded/offline state separately from autopilot/AGI mode.
- Do not mark Redis-dependent capabilities healthy while `/api/v1/health` reports Redis unavailable.
- Document that shell HTTP probes are blocked by the host provider error in this environment.

## 2026-04-30 Regression/Runtime Blocker

After replacing two ACL-restricted source files, `node_repl` probes show `http://127.0.0.1:8000/health` is currently `ECONNREFUSED`. The frontend Vite server still serves modules on `http://localhost:5173`.

This is not being classified as a successful backend launch:

- Windows Python cannot import `asyncio` or `uvicorn` because `_overlapped` raises `WinError 10106`.
- `wsl.exe -l -v` can list `kali-linux`, but any command execution, including `/bin/true`, fails with `Wsl/Service/0x8007072c`.
- `Start-Process wsl.exe` also fails with "specified module could not be found" from this shell environment.
- `wsl.exe --shutdown` completed, but command execution still fails afterward.

Current launch verdict: backend source compiles, but live backend restart is blocked by host WSL/Windows networking/runtime failure. Do not claim `/api/v1/runtime/truth` is live again until WSL command execution or Windows Python networking is repaired and `/health` returns 200.
