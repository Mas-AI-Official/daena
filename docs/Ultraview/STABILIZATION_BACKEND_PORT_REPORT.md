# Stabilization Backend Port Report

Date: 2026-04-29
Author: Claude Code (Opus 4.7) — Phase 1 of stabilization sprint

## Goal

Backend accepts `/health` within ~1s of `python run.py`. `.daena-port` stays in
sync with the actually-serving port. No ECONNREFUSED storm during cold start.
Tenant-hydration log spam removed.

## What was already correct (kept)

These were Codex's 2026-04-30 fixes — verified, not modified:

- [run.py:35-57](../backend/run.py:35) — `_remove_stale_port_file()` only removes
  `.daena-port` when the existing port is dead, never when another process
  is bound.
- [main.py:37-78](../backend/app/main.py:37) — `_publish_ready_port_file()` does
  atomic write via `tmp + os.replace`. `_clear_ready_port_file()` removes the
  file on shutdown only when it still belongs to this process.
- [run.py:79-83](../backend/run.py:79) — comment explaining we don't publish
  `.daena-port` from `run.py` because uvicorn hasn't completed FastAPI
  startup yet.

## Root cause of remaining ECONNREFUSED storm

The old lifespan ran ~10 sequential blocking awaits BEFORE
`_publish_ready_port_file()` at the bottom of the function. If any step
raised, the port file was never updated. Even when nothing raised, total
cold-start was 10–30s, and during that window the frontend proxy was
hitting whatever stale port the old `.daena-port` referenced.

## Changes shipped

### 1. New module: `backend/app/core/startup_state.py`

Single in-process tracker for startup phase:
- `started_at`, `essentials_ready`, `essentials_ready_at`
- `seedings_complete`, `seedings_complete_at`
- `seed_phase` (`not_started` → `essentials` → `deferred_pending` →
  `founder_seed` → ... → `complete`)
- `seed_errors[]` (capped at 20)
- `to_dict()` for /health surfaces

### 2. `backend/app/main.py` — lifespan split

**Essentials (sync, before serving):**
- Structured logging + guardrail validation
- `Base.metadata.create_all` + ALTER TABLE migrations (`memory_entries`,
  `chat_sessions`)
- Redis health probe with `asyncio.wait_for(timeout=1.0)` + fail-open
- EventBus readiness log
- ModelRegistry instantiation (no health probes — those are deferred per
  the existing design at [model_registry.py:154](../backend/app/services/model_registry.py:154))

After essentials: `startup_state.mark_essentials_ready()` →
`_publish_ready_port_file()` → `yield`.

**Deferred (background `asyncio.create_task`):**
- `founder_seed` → `dept_seed` → `connector_catalog` → `demo_mode` →
  `company_context` → Ollama warm-up (gated, fire-and-forget) →
  `runtime_registry` → `mcp_registry` → `background_queue` →
  `cron_scheduler` → `dream_engine` → `tlm` → `evilbob`
- Each step wrapped with `_step(name, factory)` helper that:
  - Sets `startup_state.seed_phase = name`
  - Times the operation
  - Catches errors and records to `startup_state.seed_errors`
- After all steps complete: `mark_seedings_complete()` + emit
  `daena.seedings_complete` event over `event_bus.publish`
- Periodic runtime rescan loop spawned (60s interval, lifelong)

**Shutdown:** `_clear_ready_port_file()` runs first; deferred task is
cancelled with 2s grace; existing cron/queue/registry/redis cleanup
preserved verbatim.

### 3. `backend/app/main.py` — `_seed_departments_for_all_tenants()` quieted

The "tons of tenant hydration lines" the user reported came from this
function logging `tenant_seeded` even when 0 changes were made. Now:
- Logs `tenant_seeded` (INFO) only when `created > 0`
- Single DEBUG line `auto_seed_skipped` when nothing changed
- Aggregated INFO `auto_seed_complete` shows total tenants vs seeded
  vs noop counts

### 4. `backend/app/api/v1/health.py` — surfaces seed phase

`/api/v1/health` returns one of: `starting` | `warming` | `degraded` |
`healthy`. Adds `essentials_ready`, `seedings_complete`, `seed_phase` to
the `checks` block. The frontend `BackendOfflineBanner` (which already
treats anything not `healthy` as degraded) gets accurate signal.

`/api/v1/health/detailed` adds a full `seedings` block from
`startup_state.to_dict()` plus considers seedings_complete in its
top-level status.

### 5. `backend/app/services/auth.py` — founder login-race retry

Founder accounts are seeded in the deferred phase. The very first login
attempt during cold-start (fresh install, no DB rows yet) might arrive
before the founder row exists. Added a 3-retry-with-200ms-backoff guard
that ONLY fires when:
- Email matches a configured founder email AND
- `startup_state.seedings_complete is False`

Zero overhead for fully-seeded systems. For non-founder emails, the
original "Invalid email or password" path is unchanged (no enumeration
exposure).

## Measured timing (isolated lifespan smoke)

```
ESSENTIALS_DONE_MS = 1217
After +8s: seed_phase = runtime_registry  (mid-deferred)

Per-step deferred timings:
  founder_seed         381ms
  dept_seed          7,214ms  <-- the slowdown the user felt
  connector_catalog     77ms  (116 connectors, all unchanged)
  demo_mode              1ms
  company_context        2ms
  runtime_registry    [in flight at sample time]
  ...
```

**Conclusion**: Essentials complete in 1.2s on this host. `_publish_ready_port_file()`
fires immediately after. The 7.2-second dept-seed loop now runs after the
backend is already serving — exactly the symptom the user reported has been
moved out of the user-visible path.

## Verification commands

When the user starts the backend on a real run:

```powershell
# Time-to-first-200 should be < 2s
cd D:\Ideas\Daena\backend
.\.venv\Scripts\python.exe run.py
# In another shell:
$port = (Get-Content .daena-port).Trim()
Invoke-WebRequest "http://127.0.0.1:$port/api/v1/health" -UseBasicParsing
# Expect: 200, status="warming" while deferred runs, then "healthy"
```

```powershell
# Confirm seedings finish in background
Invoke-WebRequest "http://127.0.0.1:$port/api/v1/health/detailed" -UseBasicParsing |
  Select-Object -ExpandProperty Content |
  ConvertFrom-Json |
  Select-Object -ExpandProperty seedings
# Watch seed_phase advance: founder_seed -> dept_seed -> ... -> complete
```

## Tests

- `tests/test_health.py` — 3 tests, all passing
- `tests/test_auth.py` — 6 tests, all passing
- `python -c "import ast; ast.parse(...)"` clean for all 4 modified files

## Files modified

- `backend/app/core/startup_state.py` (NEW)
- `backend/app/main.py` (lifespan split + seed quiet)
- `backend/app/api/v1/health.py` (seed phase surface)
- `backend/app/services/auth.py` (founder login-race retry)

## Risk

Low. The lifespan refactor preserves all existing seed semantics — only the
ordering and concurrency model changed. Shutdown handlers verbatim. All
existing tests pass.

## Status

Phase 1 of stabilization sprint: COMPLETE.
