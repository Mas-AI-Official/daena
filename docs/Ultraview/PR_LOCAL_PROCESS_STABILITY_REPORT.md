# PR-LOCAL-PROCESS-AND-STALE-SHELL-CLEANUP -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Date:** 2026-05-04
**Sprint:** DAENA-OVERNIGHT-LOCAL-PRODUCTION-SPRINT-6 (PR-1 of 8)

---

## 1. Goal

End the recurring "stale backend / stale frontend" confusion that
made every prior session waste 5-10 minutes diagnosing why the API
served old code or the dev URL pointed at a dead listener.

The path-scoped helpers introduced here only kill processes that
clearly belong to THIS repo's backend (`uvicorn app.main:app`) or
THIS repo's frontend (Vite dev server whose CommandLine references
`D:\Ideas\Daena\frontend`). They never touch unrelated Node/Python
processes elsewhere on the machine.

---

## 2. What changed

### Existing (no edits, validated)

* `scripts\start-backend-dev.bat` -- already correct. Pinned to
  `backend\.venv\Scripts\python.exe`, no reload, two-pass kill of
  stale uvicorn + ping-based settle. Re-confirmed in the Sprint-6
  pre-flight by reading top to bottom.
* `scripts\_dev_kill_uvicorn.ps1` -- already correct. Path-scoped
  to `python.exe` whose CommandLine matches `uvicorn\s+app\.main:app`.
  Leaves the local-llm bridge, contentops, and MCP servers alone.

### New

* `scripts\_dev_kill_frontend.ps1` -- mirror of the uvicorn killer
  for Vite. Two-pass:
  1. `node.exe` whose CommandLine matches `vite` or
     `npm.*run.*dev` AND references the resolved repo frontend dir
     (`D:\Ideas\Daena\frontend`). Forward+back slash variants both
     checked because Windows CommandLine fields can use either.
  2. Anything still listening on `:5173` -- BUT only killed if its
     process image path also resolves inside the repo frontend.
     Otherwise prints a SKIP notice with the path so the operator
     can decide.
* `scripts\start-frontend-dev.bat` -- clean Vite launcher mirroring
  `start-backend-dev.bat`. Calls the path-scoped killer first,
  pings 3s for socket release, then `npm run dev`. Refuses to
  proceed if `frontend\package.json` is missing or `npm` is not
  on PATH.
* `scripts\cleanup-stale-dev.ps1` -- combined safe cleanup that
  runs both helpers in sequence and prints final port state for
  `:8000` and `:5173`. Never kills `llama-server.exe`, contentops,
  the local-llm bridge, or other Vite projects. Safe to invoke
  whenever the operator suspects a stale dev process.

### Documentation

* This report. `start-daena.bat` (the umbrella WSL launcher) is
  unchanged so the existing dev habit is not disrupted.

---

## 3. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| Path-scoped only | YES -- both `_dev_kill_uvicorn.ps1` and the new `_dev_kill_frontend.ps1` match `app.main:app` (repo-specific) and the resolved frontend path respectively |
| Never kill llama-server | YES -- excluded by name; helpers target only `python.exe` (uvicorn) and `node.exe` (Vite) |
| Never kill contentops / MCP / local-llm-bridge | YES -- those processes' CommandLines do not match `uvicorn app.main:app` or this repo's frontend path |
| No reload on Windows | YES -- `start-backend-dev.bat` has `--no-access-log` only; uses single uvicorn process |
| .venv pinned for backend | YES -- existing launcher refuses to start without `backend\.venv\Scripts\python.exe` |
| No secret read/print | YES -- helpers print only PIDs + truncated CommandLines |
| No external network | YES -- pure local process management |

---

## 4. Smoke

```
$ powershell.exe -Command "[System.Management.Automation.PSParser]::Tokenize(...)"
scripts\_dev_kill_frontend.ps1   parse-ok
scripts\cleanup-stale-dev.ps1    parse-ok

$ curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/api/v1/health
200

$ netstat -ano | grep -E ":(8000|5173)" | grep LISTENING
TCP    127.0.0.1:8000    LISTENING    8504
TCP    [::1]:5173        LISTENING    28660
```

The cleanup helpers were NOT executed during PR-1 (the running
backend on PID 8504 and frontend on PID 28660 are the live
servers serving the rest of the sprint). Verification is by static
parse + by reading the existing `_dev_kill_uvicorn.ps1` proven
pattern that the new frontend helper mirrors line-for-line.

---

## 5. Operator usage

```
:: Start backend cleanly (existing, unchanged)
scripts\start-backend-dev.bat

:: Start frontend cleanly (NEW)
scripts\start-frontend-dev.bat

:: Combined cleanup if stale processes are suspected
powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File scripts\cleanup-stale-dev.ps1
```

The umbrella `start-daena.bat` (WSL backend + Windows frontend)
remains the recommended one-shot for full-stack startup; the new
helpers are for surgical recovery when one half goes stale.

---

## 6. What did NOT change

* No backend code.
* No frontend code.
* No database / migration / .env / vault changes.
* No deletion of the existing dev launchers.
* No changes to the WSL `backend\start-linux.sh` path.

---

## 7. Follow-ups (not in this PR)

1. Optional: add a `health-check.bat` extension that calls
   `cleanup-stale-dev.ps1` then `start-backend-dev.bat` then
   `start-frontend-dev.bat` for "kill it and restart everything"
   one-shot. Defer until PR-7 (self-diagnostic) is shipped so the
   recovery flow can quote the diagnostic output.
2. Optional: extend `_dev_kill_frontend.ps1` to detect Vite
   processes on alternate ports (Vite auto-bumps to 5174/5175 on
   collision). Defer until that collision is actually observed.
