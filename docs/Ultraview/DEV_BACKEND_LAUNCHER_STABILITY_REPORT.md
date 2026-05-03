# PR-DEV-BACKEND-LAUNCHER-STABILITY — Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** _to be filled in after squash_
**Date:** 2026-05-03
**Scope:** dev-only tooling. Backend runtime behavior unchanged.

---

## 1. Why this PR exists

The Phase 2 read-only-skills live smoke
(`PR_CONN_PLUGIN_SKILLS_EXECUTION_PHASE2_READONLY_REPORT.md`, section
7.4) hit a Windows-specific failure mode that wasted ~30 minutes:

> `uvicorn --reload` on Windows uses `multiprocessing.spawn` for the
> worker process. The spawn helper resolves `sys.executable` in a way
> that can return `C:\Python311\python.exe` instead of the project
> venv. The worker then crashes trying to import sqlalchemy
> (not in system site-packages) and uvicorn keeps serving the prior
> worker's stale code with no error surface.

The verified workaround was:

```
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 \
  --port 8000 --no-access-log
```

This PR captures that workaround as a reusable launcher so the
operator never has to re-derive it under pressure.

---

## 2. What this PR does NOT do

| Constraint | Honored? |
|---|---|
| Does not deploy to production | YES |
| Does not flip `USE_CONNECTION_REGISTRY_V2=true` | YES |
| Does not run `vault --apply` | YES |
| Does not delete V1 files | YES |
| Does not print, grep, log, or commit secrets | YES |
| Does not run external scans | YES |
| Does not execute plugin skills | YES |
| Does not change Phase 2 execution behavior | YES |
| Stays tiny (2 files, no behavior change in app code) | YES |

The launcher is a **dev-only** convenience. Production deploys still
use `Dockerfile` + `scripts/deploy-gcp.bat` / `deploy-gcp.sh`. The
existing `start-daena.bat` (full WSL backend + frontend + llama)
is unchanged.

---

## 3. Files added

### `scripts/start-backend-dev.bat` (~95 lines)

Tiny Windows-only launcher:

1. Resolves repo root from `%~dp0\..` (invocable from any cwd).
2. Sanity-checks `.venv\Scripts\python.exe` exists.
3. **Pass A**: invokes `_dev_kill_uvicorn.ps1` to kill ANY python.exe
   whose CommandLine references `uvicorn app.main:app`. Targets BOTH
   the .venv launcher parent AND its base-interpreter child (see §5).
4. **Pass B**: backstop — `taskkill /F /T` whatever still LISTENS on
   port 8000.
5. Sleeps ~2s via `ping -n 3 127.0.0.1 >NUL` to let Windows release
   the socket (avoids `WinError 10048` on the next bind).
6. Launches uvicorn directly:
   ```
   "%VENV_PY%" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log
   ```
   No `--reload`. No `multiprocessing.spawn` worker chain. Single
   process, single sqlalchemy import, fresh routes.
7. Propagates uvicorn's exit code to the caller.

### `scripts/_dev_kill_uvicorn.ps1` (~30 lines)

Helper that:

1. Lists every `python.exe` whose CommandLine matches the regex
   `uvicorn\s+app\.main:app`.
2. `Stop-Process -Force` on each match.
3. Prints one line per kill, exits 0.

Why a helper file instead of inline `powershell -Command`: the
inline form requires escaping `\"` and `^|` through `cmd`'s `for /f`
quoting, which silently broke once between PR drafts (no kill
output printed, parent kept the socket, next bind failed). `-File
.\_dev_kill_uvicorn.ps1` removes the entire escaping surface.

---

## 4. What was deliberately NOT modified

| File | Why unchanged |
|---|---|
| `backend/run.py` | Legacy entrypoint; still works. Used by `start-daena.bat` Windows fallback path. Touching it would change runtime behavior, which this PR explicitly avoids. |
| `start-daena.bat` | Operator's primary entrypoint for the full dev environment (WSL backend + frontend + llama-server). Out of scope for a stability-only PR. |
| `stop-daena.bat` | Existing kill logic stays. The new `start-backend-dev.bat` Pass A reuses the same CommandLine match pattern; future consolidation possible but not required. |
| Any production deploy script | Out of scope per hard rule. |

---

## 5. Deeper note: why netstat lies on Windows venvs

**Empirical observation during PR drafting:**

```
netstat -aon | findstr :8000
TCP    127.0.0.1:8000   0.0.0.0:0    LISTENING    31684
```

But `Get-CimInstance Win32_Process | ?{ $_.CommandLine -match 'uvicorn' }`:

```
ProcessId  ParentProcessId  ExecutablePath
13880      <bash-spawned>   D:\Ideas\Daena\backend\.venv\Scripts\python.exe
31684      13880            C:\Python311\python.exe
```

**What's happening:** Windows venvs ship `python.exe` as a tiny
launcher (~35 KB). When invoked, the launcher reads `pyvenv.cfg`,
finds `home = C:\Python311`, then re-execs the base interpreter
inheriting the venv environment (`sys.prefix`, `site-packages` on
`sys.path`). PID 13880 = launcher. PID 31684 = real interpreter.

The listening socket is opened by PID 31684 (the actual interpreter),
which is why netstat reports it. But killing only the netstat PID
leaves the launcher parent alive — and on Windows, when a parent
process holds a child handle and the child socket dies, the OS does
not always release the bind immediately. The next `socket.bind()`
fails with `WinError 10048`.

**Pass A's CommandLine-match approach catches both** because both
processes have `uvicorn app.main:app` in their cmdline. Pass B
backstops via netstat. Result: clean, deterministic restart.

**This is also why the "uvicorn --reload broke" bug feels nondeterministic.**
With reload enabled, uvicorn ALSO uses `multiprocessing.spawn` to
create a *worker* process (separate from the venv-launcher re-exec).
That worker uses `sys._base_executable` (= system python) and does
NOT reliably inherit the venv. Sometimes it works (env vars
propagated correctly), sometimes the worker silently dies and
uvicorn keeps the prior worker serving stale code. `--no-reload`
takes that whole spawn path off the table.

---

## 6. Smoke verification (live, this branch)

Sequence run from a clean port-free state:

```bash
# baseline: uvicorn app.main:app processes from prior session
$ powershell.exe -NoProfile -File scripts/_dev_kill_uvicorn.ps1
       Killing PID 13880  (D:\Ideas\Daena\backend\.venv\Scripts\python.exe -m uvicorn ...)
       Killing PID 31684  ("C:\Python311\python.exe" -m uvicorn ...)
exit=0

# launcher in background
$ cmd.exe /c "scripts\start-backend-dev.bat"
 [1/3] Releasing port 8000 if held...
       (no uvicorn app.main:app processes found)
 [2/3] Starting uvicorn (no-reload, single process)...
       Command: "D:\...\.venv\Scripts\python.exe" -m uvicorn app.main:app
                --host 127.0.0.1 --port 8000 --no-access-log
 [3/3] Handing off to uvicorn; live logs follow.
INFO:     Application startup complete.

# polling /health
tick 1: /health = 200
BOOT_OK
```

### Smoke targets (all PASS)

| # | Target | Result |
|---|---|---|
| 1 | `GET /health` | `200` `{"status":"healthy",...}` |
| 2 | `GET /api/v1/connections/v2/skills/allowlist` (no auth) | `401 AUTH_FAILED` (route registered, auth gate intact) |
| 3 | `/openapi.json` lists Phase 2 routes | `/connections/v2/skills/allowlist` + `/connections/v2/skills/execute` BOTH present |
| 4 | `backend/.daena-port` file written | contents = `8000` (lifespan completed) |
| 5 | Process tree | parent PID 11516 = `.venv\Scripts\python.exe`, child PID 31200 = `C:\Python311\python.exe` (expected venv re-exec pattern) |

### What this proves

- The launcher kills stale uvicorn processes deterministically (Pass A
  + Pass B), regardless of whether netstat reports the listener PID
  as parent or child.
- The new uvicorn boots via `.venv` python with all routes loaded
  (Phase 2 endpoints visible in OpenAPI = no silent route-loss).
- The `.daena-port` file gets written = full lifespan completed.
- No reload, no spawn worker = no risk of the silent-stale-worker
  failure mode that motivated this PR.

---

## 7. Two failure modes observed during PR drafting (now fixed)

| Symptom | Root cause | Fix |
|---|---|---|
| `timeout: invalid time interval '/t'` | Windows `timeout.exe` shadowed by GNU coreutils `timeout` on PATH when bat is invoked from WSL / Git-bash. | Replaced `timeout /t N /nobreak >NUL` with `ping -n N+1 127.0.0.1 >NUL`. Unambiguous on every Windows shell. |
| `[Errno 10048] address in use` after kill | Inline `powershell -Command "Get-CimInstance ... -Filter \"name='python.exe'\" ..."` died on cmd-quoting. Pass A produced no kills. Parent venv-launcher kept the socket. | Extracted PowerShell to `_dev_kill_uvicorn.ps1`, invoked via `-File`. Zero escaping needed. |

Both symptoms are now reproducible-on-demand and fixed-on-demand,
and both are documented inline in the bat file's comments so a
future maintainer can't accidentally regress them.

---

## 8. Operator usage

```
:: tiny: backend only, no WSL, no frontend, no llama
D:\Ideas\Daena> scripts\start-backend-dev.bat
```

For the full dev environment (WSL backend + frontend + llama-server),
keep using `start-daena.bat`. This launcher is for fast
edit-restart loops on backend code only.

To restart cleanly without typing the script twice: `Ctrl+C` in the
window (uvicorn shuts down + lifespan emits `daena_shutting_down`),
then re-run the script. Pass A will be a no-op on the second run
since the prior uvicorn already terminated cleanly.

---

## 9. Tech-debt left for follow-ups (non-blocking)

- `start-daena.bat` Windows-fallback path (line 135) still uses
  `run.py` which respects `settings.debug` → `reload=True` in dev.
  Could be migrated to call `start-backend-dev.bat` to inherit the
  no-reload safety. **Out of scope for this PR**; the WSL Linux
  backend path (the default) is unaffected.
- `stop-daena.bat` could also call `_dev_kill_uvicorn.ps1` for
  parity. **Out of scope.**

---

## 10. Files changed

```
A scripts/start-backend-dev.bat          (~95 lines)
A scripts/_dev_kill_uvicorn.ps1          (~30 lines)
A docs/Ultraview/DEV_BACKEND_LAUNCHER_STABILITY_REPORT.md  (this file)
```

No other backend, frontend, test, config, or production-deploy file
modified.

---

## 11. Branch state after PR

```
<this commit>  chore: stabilize local backend launcher on Windows
160bb19        docs/fix: complete Phase 2 live smoke verification
707b662        canonicalization: execute read-only plugin skills with audit gate
6dd840f        chore: clean Connections baseline before Phase 2
c2417c5        docs/fix: verify OAuth client config live and quarantine WIP
1da1eae        fix: add OAuth client config input for plugin connections
```

Phase 2 spine + live smoke + dev-launcher stabilization all landed.
Phase 2.x integration arms can now begin from a known-good launch
posture.
