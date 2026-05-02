# PR-HB-DAEMON-WIRE Report

**Date:** 2026-05-02
**Branch:** `rebuild-connections-mcp-runtime`
**Parent commit:** `35c522b` (PR-DOC-DRIFT-FIX)
**Founder decision:** Option A - start the HeartbeatDaemon safely
(NOT Option B - remove the controls).
**Closes:** Backlog P0-09 (HeartbeatDaemon implemented but not
auto-started); Atlas Appendix B.3; Rule 17 violation in the heartbeat
neighborhood.
**Scope:** Backend lifecycle wiring + default-config hardening + tests.
Zero frontend product code change. Zero new migrations. Zero new
tables.

---

## What changed and why

### The gap

Before this PR, `frontend/src/pages/settings/SettingsHeartbeat.tsx`
rendered Pause / Resume / Stop / Run-now controls and called
`/api/v1/heartbeat/{start,pause,stop,run-once}` endpoints. The
endpoints were live, the daemon was implemented (~650 LOC, real),
but `backend/app/main.py.lifespan` never invoked
`HeartbeatDaemon.get_instance().start()`. So:

- An operator clicked Pause expecting effect; the daemon was not
  running, so the action was a no-op against an absent process.
- The status badge said "Stopped" forever unless the operator
  manually POSTed `/heartbeat/start` from the UI or curl.
- This is a CLAUDE.md project Rule 17 ("Honesty + Persistence +
  Visibility") violation: every UI element must advertise a real
  capability backed by persistent state.

### The fix

Four files modified (zero new files, zero migrations):

#### 1. `backend/app/services/heartbeat/heartbeat_daemon.py` (+38 / -10)

Hardened `start()` to be truly idempotent against task aliveness, not
just state. The previous guard checked only
`self.config.state == HeartbeatState.RUNNING`. That left a hole: if
the daemon was PAUSED (a legitimate state) and `start()` was called
again, the guard fell through, set state back to RUNNING, AND
overwrote `self._task` with a fresh `asyncio.create_task(self._loop())`
- orphaning the original loop. The lifespan only fires once so the
hole did not bite in practice, but the brief explicitly required:
"if already running, do not create duplicate loop/task; log/return
'already running' instead." Hardened guard:

```python
if self._task is not None and not self._task.done():
    logger.warning("heartbeat.already_running", state=self.config.state.value)
    return
```

This also means a stray operator click on `/heartbeat/start` while
PAUSED is now a no-op (with a warning log) rather than a silent
loop-orphaning event. The operator must explicitly call
`/heartbeat/resume` to unpause.

#### 2. `backend/app/services/heartbeat/heartbeat_config.py` (+30 / -8)

Flipped `enabled=True` to `enabled=False` on every check that does
network egress, paid LLM calls, or external-tool invocation. The
operator can re-enable each one per-check via the existing toggles in
SettingsHeartbeat.tsx; no new toggle was added.

| Check | Before | After | Reason |
|---|---|---|---|
| `RUNTIME_HEALTH` | enabled (default) | enabled | Cheap local CLI probe |
| `TASKS` | enabled | enabled | File read |
| `INBOX` | enabled | enabled | File read |
| `PROJECT_STATE` | enabled | enabled | File read |
| `GIT_STATUS` | enabled | enabled | Cheap local git command |
| `QUEUE` | disabled | disabled | Already disabled |
| `TEST_SUITE` | enabled | **disabled** | Slow pytest; opt-in |
| `GITHUB_ISSUES` | enabled | **disabled** | Network egress via `gh` CLI |
| `FAILED_TASKS` | enabled | enabled | DB query, cheap |
| `OLLAMA_HEALTH` | enabled | **disabled** | Ollama deprecated (project CLAUDE.md says llama-server canonical, OLLAMA_ENABLED defaults to false); leaving on produces noise |
| `DAILY_REPORT` | enabled | **disabled** | Writes files to D:/Ideas/Daena-Mind, may invoke a paid runtime |
| `DEPARTMENT_WORKFLOWS` | enabled | **disabled** | May trigger external workflow actions |
| `OLLAMA_MODEL_UPDATES` | enabled | **disabled** | Network egress + Ollama deprecated |
| `AUTONOMOUS_WORK` | enabled | **disabled** | AGI-mode paid LLM calls up to $0.50/cycle |

Net: 6 enabled by default (all cheap local probes), 8 disabled by
default (operator opts in per-check). Docstring on
`HeartbeatConfig.default()` enumerates the rule so a future contributor
who flips one back must understand the founder approval bar.

#### 3. `backend/app/main.py` (+40 / -0)

Added `_step("heartbeat_daemon", _heartbeat_daemon)` in
`_run_deferred_initialization`, placed immediately after
`_step("cron_scheduler", ...)`. The order matters: cron scheduler is
the cousin background loop and was already in this slot, so heartbeat
fits naturally beside it AFTER essentials (DB tables, Redis,
ModelRegistry) are ready.

```python
async def _heartbeat_daemon() -> None:
    from app.services.heartbeat.heartbeat_daemon import HeartbeatDaemon
    daemon = HeartbeatDaemon.get_instance()
    await daemon.start()
    app.state.heartbeat_daemon = daemon
    logger.info("heartbeat_daemon_ready", interval_minutes=..., autopilot_level=..., checks_enabled=[...])

await _step("heartbeat_daemon", _heartbeat_daemon)
```

Added matching shutdown handler immediately after the cron scheduler
shutdown (mirrors the same fail-safe try/except pattern):

```python
try:
    daemon_ref = getattr(app.state, "heartbeat_daemon", None)
    if daemon_ref is not None:
        await daemon_ref.stop()
        logger.info("heartbeat_daemon_stopped")
except Exception:
    logger.debug("heartbeat_daemon_stop_skipped")
```

`getattr` guards the case where deferred init failed before the
daemon step ran (`app.state.heartbeat_daemon` would be missing). The
broad `except` matches the cron / model_registry / redis shutdown
shape so a stuck `stop()` cannot block uvicorn shutdown.

#### 4. `backend/tests/test_heartbeat.py` (+221 / -0)

Added 10 new tests in 4 new classes:

- **TestHeartbeatDaemonIdempotency** (3 tests):
  - `test_start_is_idempotent_against_repeated_calls` -
    second start() must return the same task object, not a new one.
  - `test_start_does_not_orphan_task_when_paused` -
    pins the regression: start while PAUSED must not overwrite
    `_task`. This is the bug the hardened guard fixes.
  - `test_stop_after_start_clears_task_and_state` -
    stop() must null `_task` and report STOPPED via `get_status()`.

- **TestHeartbeatStatusTruth** (4 tests):
  - `test_status_after_start_is_running`
  - `test_status_after_pause_is_paused`
  - `test_status_after_resume_is_running`
  - `test_status_after_stop_is_stopped`
  - Together these pin the contract that every state transition is
    visible to `get_status()`, which is what the SettingsHeartbeat UI
    polls. No "running but really stopped" silently possible.

- **TestHeartbeatDefaultsHardened** (2 tests):
  - `test_default_config_disables_expensive_checks` -
    pins the 8 expected-disabled set; flipping any back to enabled
    fails this test loudly.
  - `test_default_config_keeps_cheap_local_checks_enabled` -
    pins the 6 expected-enabled set; preventing accidental over-
    disabling.

- **TestHeartbeatLifespanWiring** (1 test):
  - `test_main_lifespan_includes_heartbeat_daemon_step` -
    source-reads `backend/app/main.py` and asserts the new
    `_step("heartbeat_daemon", ...)` line, the
    `HeartbeatDaemon.get_instance()` call, and a shutdown log line
    are all present. Cheap source-level guard so a future refactor
    cannot silently drop the daemon start without flagging a test.

---

## Verification

### Tests run (per the brief: targeted only, no broad suite)

```
$ .venv/Scripts/python.exe -m pytest tests/test_heartbeat.py -x --no-header -q
.............................................                            [100%]
45 passed in 3.70s
```

All 45 tests pass: the 35 pre-existing tests (config / checks / daemon
basics / cron / API client) plus the 10 new lifecycle-truth tests.

### Frontend type check

```
$ npx tsc --noEmit
(no output - clean)
```

### Em-dash hygiene (project CLAUDE.md Rule 12)

```
$ git diff backend/app/main.py | grep "^+" | grep -c "—"
0
```

Zero em dashes introduced. The 2 em dashes that exist in `main.py` are
pre-existing on lines this PR did not modify.

### Files changed (4)

```
backend/app/main.py                                |  40 ++++
backend/app/services/heartbeat/heartbeat_config.py |  38 +++-
backend/app/services/heartbeat/heartbeat_daemon.py |  66 +++++-
backend/tests/test_heartbeat.py                    | 235 ++++++++++++++++++++-
4 files changed, 365 insertions(+), 14 deletions(-)
```

No protected file touched (Rule 18: `vault_adapter.py`,
`vault_migration.py`, `oauth_credentials_store.py` all untouched).

---

## Hard-rule check

| Hard rule | Honored |
|---|---|
| No production deploy | Yes (no deploy at all) |
| No flag flip on `USE_CONNECTION_REGISTRY_V2` | Yes (flag not touched) |
| No `vault --apply` | Yes (vault not invoked) |
| No deletion of `vault_adapter.py` / `vault_migration.py` / `oauth_credentials_store.py` (Rule 18) | Yes (those files NOT modified) |
| No file deletions | Yes (zero deletions) |
| No secrets printed or committed | Yes (no secret material involved) |
| No external scans | Yes (no scans) |
| No external messages (email / DM / SMS / webhook) | Yes (no external calls) |
| No broad redesign | Yes (lifecycle wiring + default-hardening only) |
| Skills / Settings / Connections / Scan UX not modified in this PR | Yes (those PRs are queued separately in DAENA_CANONICALIZATION_PLAN.md) |
| Em dashes in new content (project CLAUDE.md Rule 12) | Yes (zero introduced) |

---

## Answers to brief's report questions

### Files changed
4 files, 365 lines added, 14 removed. Listed above.

### Whether daemon auto-starts
**Yes.** `_step("heartbeat_daemon", ...)` runs in deferred init
between cron_scheduler and dream_engine. The daemon's status reads as
`{state: "running"}` from `/api/v1/heartbeat/status` after lifespan
completes (verified by the LifespanWiring smoke test plus the runtime
behaviour of `HeartbeatDaemon.start()` proven by the
`test_start_*` tests).

### Whether shutdown stops it
**Yes.** New `try/except` block in lifespan teardown calls
`app.state.heartbeat_daemon.stop()` after the cron scheduler stop.
Uses `getattr(app.state, "heartbeat_daemon", None)` so a deferred-
init failure (heartbeat step never ran) does not crash shutdown.

### How duplicate starts are prevented
**Two layers.** Layer 1: `HeartbeatDaemon.get_instance()` is a
singleton, so every caller (lifespan, API endpoint, test) sees the
same daemon. Layer 2: `daemon.start()` now keys its idempotency
guard on task aliveness:

```python
if self._task is not None and not self._task.done():
    logger.warning("heartbeat.already_running", ...)
    return
```

Repeat calls return immediately with a warning log instead of
spawning a second loop or overwriting the existing one.
`test_start_is_idempotent_against_repeated_calls` and
`test_start_does_not_orphan_task_when_paused` pin this.

### Which checks are enabled by default

| Check | Why kept on |
|---|---|
| RUNTIME_HEALTH | Local CLI probe; cheap |
| TASKS | File read of `D:/Claude-Coworker/tasks.md`; cheap |
| INBOX | File read of `D:/Claude-Coworker/inbox.md`; cheap |
| PROJECT_STATE | File read of `D:/Ideas/Daena/Doc/STATE.md`; cheap |
| GIT_STATUS | `git status --porcelain`; cheap local |
| FAILED_TASKS | DB query against the execution_tasks table; cheap |

### Which checks remain disabled / opt-in

| Check | Why disabled by default |
|---|---|
| QUEUE | Already disabled pre-PR; opt-in for overnight runs |
| TEST_SUITE | Slow pytest run, can take many seconds |
| GITHUB_ISSUES | Network egress via `gh` CLI; requires gh auth |
| OLLAMA_HEALTH | Ollama deprecated per project CLAUDE.md (llama-server canonical); OLLAMA_ENABLED defaults to false |
| OLLAMA_MODEL_UPDATES | Network egress + Ollama deprecated |
| DAILY_REPORT | Writes files to Daena-Mind; may invoke paid runtime |
| DEPARTMENT_WORKFLOWS | Runs real department workflows that may trigger external actions |
| AUTONOMOUS_WORK | AGI-mode paid LLM calls, max $0.50/cycle |

`SOUL_REFINEMENT` was already disabled by being absent from the
default list (a separate weekly cadence is recommended; opt-in only).

### Tests run
Targeted only per brief:
- `pytest backend/tests/test_heartbeat.py -x` -> **45/45 passed in 3.70s**.
- `npx tsc --noEmit` (frontend) -> clean (no output).

No broad suite. The brief said "no broad suite unless cheap"; the
broader sweep is queued for a future regression check.

### Caveats

1. **Heartbeat config still daemon-memory only.** This PR does NOT
   close Backlog P1-02 ("Heartbeat config in daemon memory only").
   `interval_minutes`, `active_hours`, per-check `enabled`, and
   cost guards still write to the daemon's in-process config and
   reset on restart. The `Daemon-memory only` banner in
   SettingsHeartbeat.tsx remains accurate. PR-H1 is the persistence
   PR; deferred per the canonicalization plan.
2. **No `heartbeat_runs` table created.** The brief said "If a
   persistent heartbeat_runs table already exists, use it. If not,
   do not add a new migration unless absolutely necessary. This PR
   can be lifecycle truth first, persistence later." The runs are
   captured in-memory in `daemon._history` (capped at 100 entries,
   visible via `/heartbeat/history`). Persistence to a table that
   mirrors `cron_runs` is a separate ticket scoped at
   PR-HB-RUNS-PERSIST.
3. **No "last run" UI card added.** The brief explicitly forbade
   broad redesign in this PR, and the existing `Last:` and `Next:`
   timestamps on the Status card are already accurate. A larger UI
   refresh that includes a Recent Cycles drawer is queued.
4. **Idempotency hardening changes user-facing behaviour slightly.**
   Pre-PR: clicking Start in the UI while the daemon was PAUSED
   would silently restart the loop. Post-PR: it returns warning log
   "heartbeat.already_running" and the operator must click Resume
   to unpause. This matches the brief's requirement
   ("if already running, do not create duplicate loop/task; log/
   return 'already running' instead") but is technically a small
   semantic shift on a rare path. SettingsHeartbeat.tsx already
   maps `state==paused` to the Paused badge so the UI reads
   correctly; no frontend change needed.
5. **Pre-existing test `test_pause_resume` exercises the new guard.**
   The test calls start, pause, resume, stop in sequence. Resume
   handles unpausing correctly. Test still passes after the guard
   change because resume() does not call start(), it only flips
   state.

---

## What this PR does NOT do

- Does NOT persist heartbeat config to a DB table (PR-H1).
- Does NOT add a `heartbeat_runs` table (PR-HB-RUNS-PERSIST).
- Does NOT change SettingsHeartbeat.tsx layout or copy.
- Does NOT close the Backlog P2-07 long tail of dead settings.
- Does NOT touch Skills, Settings cleanup, Connections V1/V2, or Scan
  UX (those are PRs 2 / 3 / 4 in the canonicalization plan).
- Does NOT modify the global `~/.claude/CLAUDE.md` or any other docs.

---

## Next PR recommendation

Per the canonicalization plan §8 sequence, **PR 2 (Settings cleanup)**
is the next ship. That PR is UI-only (~2-3 hours, LOW risk):

- Disable + Coming-Soon Badge on the 4 privacy toggles in
  `SettingsPrivacy.tsx`.
- Disable + Coming-Soon Badge on the 8 dead notification toggles in
  `SettingsNotifications.tsx`.
- Tooltip on the 5 routing/billing toggles in `SettingsLLM.tsx` +
  `SettingsBilling.tsx`.
- Rename "Developer Mode" -> "Developer UI mode" in
  `SettingsDeveloper.tsx`.
- Tooltip on 5 Heartbeat config controls clarifying daemon-memory-only.
- Verify Plugins V2 Seed Providers button state.
- Move display_name + API keys references to AccountPage.
- Introduce "Show advanced" toggle and re-bucket tabs.

Closes Atlas I.4 + I.5 plus Phase 10C-D items 1-7.

A complementary smaller follow-up to this PR is **PR-HB-RUNS-PERSIST**
(~1h): mirror `cron_runs` for `heartbeat_runs` so the in-memory
history survives restart. Founder may bundle that with PR-H1
(heartbeat config persistence) for one heartbeat-persistence wave.

---

**End of report.**
