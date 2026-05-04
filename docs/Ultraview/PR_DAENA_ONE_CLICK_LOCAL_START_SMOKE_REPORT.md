# PR-DAENA-ONE-CLICK-LOCAL-START-SMOKE -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Date:** 2026-05-04
**Sprint:** DAENA-LAPTOP-USABLE-TODAY-SPRINT-7 (PR-1 of 7)

---

## 1. Goal

One reliable command takes Masoud from "laptop on, terminal open" to
"Daena ready in browser". No more remembering which window to start
first, which port to clear, or which folder to cd into.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| Path-scoped cleanup only (no blanket python.exe / node.exe kills) | YES -- delegates to existing `cleanup-stale-dev.ps1` which checks CommandLine for repo path before killing |
| No uvicorn --reload (Windows worker bug) | YES -- pinned by `test_script_does_not_use_uvicorn_reload` (parses non-comment lines only) |
| No npm install / pip install | YES -- script never runs install commands; failure hints reference setup-daena.bat |
| No .env / vault / secret writes | YES -- script touches no persistent state |
| No production deploy / cloud writes | YES -- localhost only |
| No external network beyond loopback | YES -- only probes 127.0.0.1:8000 + 127.0.0.1:5173 |
| Backend in its own window so logs are visible | YES -- `start "Daena Backend" cmd /c ...` |
| Frontend in its own window so logs are visible | YES -- `start "Daena Frontend" cmd /c ...` |
| Operator sees URLs after success | YES -- 6 URLs printed (backend, health, diagnostic, OpenAPI, frontend, connections) |
| Operator sees next-action on failure | YES -- common-cause hints for backend (port held, .venv deps, alembic) and frontend (npm install, cross-repo Vite) |

---

## 3. Surface area

### Scripts

#### `scripts/start-daena-local.bat` (NEW)

Five-step launcher:

```
[1/5] Cleaning stale Daena dev processes (path-scoped)
      -> powershell scripts\cleanup-stale-dev.ps1
[2/5] Starting backend in a new window
      -> start "Daena Backend" cmd /c scripts\start-backend-dev.bat
[3/5] Starting frontend in a new window
      -> start "Daena Frontend" cmd /c scripts\start-frontend-dev.bat
[4/5] Waiting for backend /health on 127.0.0.1:8000 (poll up to ~30s)
[5/5] Waiting for frontend on 127.0.0.1:5173 (poll up to ~30s)
```

On READY: prints 6 URLs + "Next: open http://127.0.0.1:5173/connections".
On PARTIAL: explicit common-cause hints per failed service.

Exit code is always 0 -- the script's job is to LAUNCH, not gate. The
operator reads the summary to decide next action.

### Tests

#### `backend/tests/test_local_startup_smoke.py` (NEW, 8 tests)

Static validation -- always runs:

1. **`test_script_exists`** -- launcher present at expected path.
2. **`test_script_references_path_scoped_helpers`** -- delegates to
   the THREE existing safe helpers.
3. **`test_script_prints_user_urls`** -- health, 5173, /connections,
   self-diagnostic all surfaced.
4. **`test_script_has_no_blanket_destructive_calls`** -- forbids
   `taskkill /F /IM python.exe`, `format`, `rd /s`,
   `Stop-Process -Name python`, etc.
5. **`test_script_does_not_use_uvicorn_reload`** -- parses non-comment
   lines only, refuses any executable line that mentions `--reload`.
6. **`test_script_documents_next_action_on_failure`** -- `[WARN]`
   appears + recovery commands (alembic, pip install).

Opt-in network probes -- skip if backend not running:

7. **`test_health_endpoint_responds`** -- 200 from `/health`.
8. **`test_self_diagnostic_endpoint_route_is_registered`** -- 401/403
   from `/api/v1/system/self-diagnostic` (Sprint-6 PR-7 route + auth gate).

---

## 4. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_local_startup_smoke.py -q
........                                                                 [100%]
8 passed in 1.29s
```

All 6 static-validation tests + both opt-in probes (backend was up
during this sprint).

---

## 5. Smoke

The launcher is a wrapper over scripts that have already been smoked
in Sprint-6 PR-1. No new process-management behavior is introduced;
the new code is a sequencer + polling + pretty-print layer.

Manual smoke by the operator tomorrow morning:

```cmd
D:\Ideas\Daena> scripts\start-daena-local.bat
```

Expected: two new windows ("Daena Backend", "Daena Frontend") open;
this window prints `[1/5]` ... `[5/5]`; ends with READY summary +
URL list.

---

## 6. What did NOT change

* No backend behavior change.
* No frontend behavior change.
* No connector behavior change.
* No dependency added (no npm, pip, docker, MCP install).
* No test removed.
* Phase 3 writes -- still impossible.

---

## 7. Follow-up PRs

1. Optional: a `--no-frontend` flag for Masoud's "I just want to
   poke the API" sessions.
2. Optional: parse `cleanup-stale-dev.ps1` "Final port state" output
   so the launcher can refuse to start if a foreign Vite holds 5173.
3. Optional: write a `.daena-startup-summary.txt` artifact so cron
   /heartbeat tasks can read the last successful start time.
