# PR-SPINE-04: Task -> Workstream status sync - Report

**Date:** 2026-05-02
**Branch:** `rebuild-connections-mcp-runtime`
**Author:** Claude Code (Opus 4.7) under founder direction
**Companion PRs in the same sprint:** PR-GOV-01 (`3639126`), PR-4 (`0bd2381`), parked exporter (`6de2037`), PR-5 (`094ab6f`), PR-SCAN-WS-01 (`49c84f6`), checkpoint doc (`ce57e22`).

> **Thesis:** PR-5 spawned Workstreams from Tasks but never closed the loop - a Task could complete, fail, or pause without the spine artifact mirroring the change. PR-SPINE-04 hooks the Task lifecycle into the Workstream so the operator's "what is running" surface stops lying. Refresh-only (no SSE yet); the next PR adds streaming.

---

## 1. Hard rules check (founder brief)

| Rule | Status |
|---|---|
| No deploy | Yes - local-only changes |
| No external scans / messages | Yes |
| No T5 changes | Yes - no T5 file touched |
| No broad rewrite | Yes - additive helpers + 2 small hooks in ExecutionService |
| No new dependencies | Yes - stdlib + existing project libs |
| Em dashes (project Rule 12) | None introduced |

---

## 2. Status mapping

The mapping is deliberately small. Three lifecycle outcomes plus one no-op bucket.

| Task status (normalized upper-case) | Workstream intent | Workstream effect | Timeline event |
|---|---|---|---|
| `RUNNING` | `running` | If WS is RUNNING and `progress_percent < 25`, bump to 25. No transition. | DECISION + `payload.kind=task_status_changed` + `to_status=RUNNING` |
| `COMPLETED` / `COMPLETE` / `SUCCESS` | `complete` | If WS not already terminal: `complete()` (transitions to COMPLETE + emits COMPLETED event) + `update_progress(100)`. | DECISION first, then COMPLETED (auto-emitted by `transition()`) |
| `FAILED` / `CANCELLED` | `fail` | If WS not already terminal: `fail()` (transitions to FAILED + emits FAILED event with the reason). | DECISION first, then FAILED (auto-emitted by `transition()`) |
| `PENDING` / `PAUSED` | `noop` | No transition, no progress change. | DECISION only |
| Anything else | `noop` (default) | No transition. | DECISION only |

The full mapping table lives at `app.services.workstream_service.TASK_STATUS_TO_WS_INTENT` so future SSE consumers (PR-SPINE-04+) can introspect it.

### 2.1 Why `RUNNING` only bumps progress (no transition)

The Workstream is created in RUNNING by `ExecutionService.create_task(also_create_workstream=True)` (PR-5). The state machine forbids `RUNNING -> RUNNING` transitions (terminal idempotency: `LEGAL_TRANSITIONS[RUNNING]` does not include RUNNING). So when a task transitions PENDING -> RUNNING, the WS stays RUNNING and we just bump progress to give the operator a visible "the task started" signal.

### 2.2 Why a single `DECISION` event kind (not a new `TASK_STATUS_CHANGED` enum value)

- Adding a new enum value would require migration 010 + Postgres `ALTER TYPE workstream_event_kind ADD VALUE 'TASK_STATUS_CHANGED'`. Acceptable cost, but bigger scope than this PR.
- The existing `DECISION` kind ("a synthesis or chairman call") is the closest semantic fit for "task lifecycle reached a checkpoint."
- The payload carries `kind=task_status_changed` so future SSE consumers can filter on it without parsing prose.
- A future PR-SPINE-04+ that introduces the SSE channel can promote this to a dedicated enum value if filter-by-enum performance ever matters.

---

## 3. Dual-link lookup (PR-5 direct + PR-SCAN-WS-01 indirect)

The new helper `find_workstream_linked_to_task(db, tenant_id, task_id)` in `app/services/workstream_service.py` covers both link shapes that the sprint introduced:

### 3.1 Direct link (PR-5)

Workstream where `source_type=TASK` AND `source_ref_id=task_id`. Written by `ExecutionService._spawn_workstream_for_task` when the operator passes `also_create_workstream=True` to the create-task endpoint.

```sql
SELECT * FROM workstreams
 WHERE tenant_id = :tenant
   AND source_type = 'task'
   AND source_ref_id = :task_id
   AND archived_at IS NULL
 LIMIT 1
```

This is the primary case and resolves in O(1) with the per-tenant + per-source-type indexes.

### 3.2 Indirect link via `artifact_refs.task_ids` (PR-SCAN-WS-01)

Workstream where `source_type=SCAN` AND `artifact_refs.task_ids` (a JSON list) contains `str(task_id)`. Written by `scan_remediation.create_remediation` when an operator clicks "Create remediation task" on a scan finding - the workstream's source_type stays SCAN (the scan IS the source), but the linked Task id is recorded in artifact_refs so the spine still tracks the relationship.

The lookup is a per-tenant linear scan filtered to SCAN-sourced workstreams + Python-side `task_id_str in refs.task_ids`. Acceptable cost: SCAN-sourced workstreams stay small per tenant; a future composite functional index can be added when N grows past ~500 (documented in PR-SCAN-WS-INDEX from the PR-SCAN-WS-01 report).

### 3.3 Archived workstreams are skipped

Both lookups filter `archived_at IS NULL`. A soft-deleted workstream MUST NOT silently re-flip back to RUNNING because a long-running task associated with it finally completed - that would defeat the operator's archive action. Pinned by `test_find_linked_workstream_skips_archived`.

---

## 4. Lifecycle handling

### 4.1 Two integration points in `ExecutionService`

1. **`update_task_status`** - the canonical update method used by the API (`PATCH /execution/tasks/{id}`) AND by the simulated background runner inside `_background_run`. The sync fires after the commit, only when `status` was supplied AND actually changed (the `prior_status != status` guard prevents idempotent re-emit).

2. **`run_task`** - the synchronous "kick off RUNNING" path bypasses `update_task_status` because it also clears `completed_at`, `error`, and `progress`. Sync is called explicitly after the commit, also guarded by `prior_status != RUNNING`.

Both paths converge into `_sync_linked_workstream(task, new_status)` so the lifecycle behavior is identical regardless of which entry point fired.

### 4.2 Best-effort isolation

The sync helper is wrapped in `try/except`:

```python
try:
    # find + transition + emit
except Exception as exc:
    logger.warning("task.workstream_sync_failed", ...)
```

A spine sync failure NEVER raises into the task path. The Task is the source of truth for its own lifecycle; the Workstream is the spine artifact mirror. If the mirror breaks, the task continues normally and the operator sees a stale workstream until the next sync attempt or an explicit refresh. This mirrors the same pattern PR-5 used for `_spawn_workstream_for_task` and PR-SCAN-WS-01 used for the audit attachment.

### 4.3 Idempotency on terminal workstreams

`complete()` and `fail()` go through `transition()` which raises `WorkstreamTransitionError` when transitioning out of a terminal state. The sync helper catches this:

```python
try:
    await ws_svc.complete(...)
except WorkstreamTransitionError:
    pass  # Concurrent terminal transition; idempotent skip.
```

Pinned by `test_terminal_workstream_not_retransitioned`. Combined with the pre-check `if ws.status not in (COMPLETE, FAILED)`, this gives belt-and-suspenders idempotency: pre-check skips the call, exception catch handles the race.

### 4.4 Frontend - refresh only

The brief allowed "Frontend should show updated status after refresh only. Live console can wait." Per that:

- No frontend file modified by this PR. The existing `WorkstreamsPage.tsx` (PR-5) already polls on Refresh + when a status filter is changed; the synced workstream state shows up after the next load.
- No SSE channel added. The Execution Spine PRD §9 SSE event taxonomy is the next PR (PR-SPINE-04+); this PR ships the data model + sync logic that future SSE consumers will publish.
- The `payload.kind=task_status_changed` marker on the DECISION event is the contract that lets the future SSE PR emit `spine.task_status_changed` events without re-engineering the producer side.

---

## 5. Files changed

### 5.1 Backend (modified)

- `backend/app/services/workstream_service.py` - added `find_workstream_linked_to_task` helper + `TASK_STATUS_TO_WS_INTENT` mapping table.
- `backend/app/services/execution_service.py` - hooked `_sync_linked_workstream` into `update_task_status` (status-changed path) and `run_task` (direct RUNNING flip path); added the helper method itself.

### 5.2 Backend (new)

- `backend/tests/test_task_workstream_sync.py` - 13 contract tests.

### 5.3 Docs (new)

- `docs/Ultraview/PR_SPINE_04_TASK_WORKSTREAM_STATUS_SYNC_REPORT.md` (this file).

### 5.4 Frontend

- No frontend changes (refresh-only behavior; SSE deferred).

### 5.5 Files NOT touched (per hard rules)

- All T5 / EvilBob / red_team / exploitation / zero_day / osint / evilbob_mode files
- `chat_orchestrator.py`, `cognitive_scan_engine.py`, `scan_workflow.py`
- All vault / OAuth / V2 connection paths
- All `frontend/src/pages/*` files (no UI delta in this PR)
- `chat.py`, `governance.py`, `audit.py` (the hot path)

---

## 6. Tests run

### 6.1 New tests (PR-SPINE-04)

`backend/tests/test_task_workstream_sync.py` - **13 tests, all green:**

| Group | Test | What it pins |
|---|---|---|
| Lookup | `test_find_linked_workstream_via_direct_task_source` | PR-5 source_type=TASK link |
| | `test_find_linked_workstream_via_scan_artifact_refs` | PR-SCAN-WS-01 indirect link |
| | `test_find_linked_workstream_returns_none_when_unlinked` | No link returns None |
| | `test_find_linked_workstream_skips_archived` | Archived workstreams excluded |
| Status sync | `test_task_completed_flips_workstream_complete` | COMPLETED -> WS COMPLETE + progress 100 |
| | `test_task_failed_flips_workstream_failed` | FAILED -> WS FAILED + reason in summary |
| | `test_task_running_bumps_workstream_progress` | RUNNING bumps progress >= 25 (no transition) |
| | `test_task_paused_emits_timeline_no_transition` | PAUSED leaves status; emits DECISION marker |
| Isolation + idempotency | `test_task_without_workstream_unaffected` | Default create_task path is unaffected |
| | `test_terminal_workstream_not_retransitioned` | Terminal WS not re-flipped by later task changes |
| | `test_status_unchanged_does_not_emit_sync_event` | Idempotent re-write does not re-emit |
| | `test_cross_tenant_task_does_not_sync_other_tenants_workstream` | Cross-tenant lookup miss |
| Run-task path | `test_run_task_direct_flip_syncs_workstream_progress` | The synchronous RUNNING flip in run_task is also synced |

### 6.2 Regression sweep (all green)

| File | Tests | Result |
|---|---:|---|
| `test_workstream_spine_skeleton.py` (PR-5) | 18 | 18/18 |
| `test_workstream_service.py` | 11 | 11/11 |
| `test_settings_governance_guard.py` (PR-GOV-01) | 17 | 17/17 |
| `test_execution.py` | 6 | 6/6 |
| `test_execution_run_task.py` | 5 | 5/5 |
| `test_scan_remediation.py` (PR-SCAN-WS-01) | 18 | 18/18 |
| **Combined regression** | **75** | **75/75** |

Combined with the 13 new tests: **88 tests pass across the related surface**.

### 6.3 No frontend tsc run

No frontend file modified; the previous PR-SCAN-WS-01 tsc-clean state is unchanged.

---

## 7. Remaining debt + next-step pull-throughs

### 7.1 Closed by this PR

- **P0-02 from the sprint checkpoint** (status sync Task -> Workstream): closed.
- **PR-5 §10 honesty note** ("Tasks page is not removed and is not relabeled"): unchanged - this PR does not touch the Tasks page.
- **PR-SCAN-WS-01 §10 honesty note** ("Status sync from Task -> Workstream is one-way today"): closed - the sync now fires in both directions documented in §3.

### 7.2 Still open after this PR

- **No SSE channel.** The Workstream drawer still requires manual Refresh to see the new state. Promoting `payload.kind=task_status_changed` to a dedicated `spine.task_status_changed` SSE event is the next PR (PR-SPINE-04+). Current behavior is honest: the timeline view shows the DECISION marker after refresh, the status pill shows the synced state after refresh.
- **No new event-kind enum.** The DECISION + payload pattern works for refresh-based UI; SSE consumers will keep working with payload-filtering. A future PR can introduce `WorkstreamEventKind.TASK_STATUS_CHANGED` if filter-by-enum becomes load-bearing.
- **No reverse sync.** A Workstream archive does NOT propagate to its linked Task (the Task stays in whatever status it was in). This is intentional: archive is a UI declutter, not a lifecycle signal.
- **Performance: indirect-link lookup is O(N) per tenant on SCAN-sourced workstreams.** Already documented as PR-SCAN-WS-INDEX in the PR-SCAN-WS-01 report. Not made worse by this PR.

### 7.3 Demo readiness delta

After PR-SPINE-04, the founder can:

1. Open `/workstreams` -> click "Demo workstream" (PR-5 affordance) to see a populated workstream.
2. Open a completed scan -> click "Create remediation task" on a finding (PR-SCAN-WS-01).
3. Visit `/tasks` -> kick off the spawned task (it goes through `run_task`).
4. Refresh `/workstreams` -> see the linked workstream's progress bar advance from 0 to >=25 (RUNNING sync).
5. Wait for the bg simulator to mark the task COMPLETED. Refresh again -> see the workstream flip to COMPLETE + 100% + a DECISION event ("Linked task transitioned to COMPLETED") + a COMPLETED event ("Linked task completed: <name>") on the timeline.

That's the first end-to-end "scan finding turns into trackable work that automatically reflects progress" demo. The only manual step is Refresh; the next PR removes that.

---

## 8. Honesty notes

- The status mapping is intentionally narrow. PENDING and PAUSED do not transition the workstream because there is no compatible lifecycle target (the workstream was not in PENDING; it does not have a PAUSED state - that is what `autopilot_paused` is for, which is independent of the lifecycle). The DECISION event is the only signal in those cases, which is correct.
- The DECISION event fires on EVERY status change including no-ops (PAUSED, PENDING). This is by design - operators viewing the timeline should see the cause regardless of whether the workstream changed state. Pinned by `test_task_paused_emits_timeline_no_transition`.
- The `WorkstreamTransitionError` catch in the complete/fail branches is for the race where two concurrent task updates fire while the workstream is mid-transition. Today there is no concurrent updater, but the catch documents the contract and prevents future regressions.
- The `try/except Exception` wrapper around the entire sync is broad on purpose. The Task is the contract; if any spine code path raises (DB error, missing department, anything), the warning is logged and the Task lifecycle continues. A future hardening PR can narrow this to specific exception types once the failure modes are catalogued.
- The PR ships ZERO frontend changes. The existing PR-5 WorkstreamsPage already renders status, source, progress, artifact_refs, audit_event_refs, and the timeline drawer. After this PR, those renders just become honest in the linked-task case.

---

## 9. Commit message

```
canonicalization: sync task status into linked workstreams

PR-SPINE-04: when a Task that has a linked Workstream changes status,
the Workstream lifecycle mirrors the change. Refresh-only (SSE
deferred). No frontend changes. Best-effort isolation - sync failure
does not break the task path.

Backend
- New helper: workstream_service.find_workstream_linked_to_task that
  resolves both link shapes:
    1. source_type=TASK + source_ref_id=task_id (PR-5 direct)
    2. source_type=SCAN + artifact_refs.task_ids contains task id
       (PR-SCAN-WS-01 indirect)
  Skips archived workstreams.
- New mapping: TASK_STATUS_TO_WS_INTENT classifies each task status
  into running / complete / fail / noop intents.
- New method: ExecutionService._sync_linked_workstream that:
  - Always emits a DECISION timeline event with
    payload.kind=task_status_changed
  - Bumps progress >= 25 on RUNNING (no transition; WS is already
    RUNNING from spawn)
  - complete() + progress=100 on COMPLETED/SUCCESS
  - fail() with task.error or task.name on FAILED/CANCELLED
  - Skips terminal workstreams (idempotent)
  - Wrapped try/except so sync failure never raises into the task
    path
- Hooks into update_task_status (status-changed path) and run_task
  (direct RUNNING flip path).

Tests
- 13 new contract tests in test_task_workstream_sync.py (all green)
- 0 regressions across test_workstream_spine_skeleton.py (18/18),
  test_workstream_service.py (11/11),
  test_settings_governance_guard.py (17/17), test_execution.py (6/6),
  test_execution_run_task.py (5/5), test_scan_remediation.py (18/18)
- 75 regression tests pass alongside the 13 new = 88 total

Honors all founder hard rules. No deploy. No external messages.
No T5 changes. No new dependencies.

Report: docs/Ultraview/PR_SPINE_04_TASK_WORKSTREAM_STATUS_SYNC_REPORT.md
```

End of report.
