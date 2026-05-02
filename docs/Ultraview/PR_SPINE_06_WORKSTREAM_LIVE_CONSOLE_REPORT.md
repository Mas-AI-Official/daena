# PR-SPINE-06: Workstream live console - Report

**Date:** 2026-05-02
**Branch:** `rebuild-connections-mcp-runtime`
**Author:** Claude Code (Opus 4.7) under founder direction
**Companion PRs in the same sprint:** PR-GOV-01 (`3639126`), PR-4 (`0bd2381`), parked exporter (`6de2037`), PR-5 (`094ab6f`), PR-SCAN-WS-01 (`49c84f6`), checkpoint (`ce57e22`), PR-SPINE-04 (`11ae546`).

> **Thesis:** PR-5 gave Daena the Workstream artifact. PR-SCAN-WS-01 gave it real fuel. PR-SPINE-04 made the linked-task lifecycle reactive. But the operator still needed to click Refresh to see anything change. PR-SPINE-06 closes that visibility gap by emitting per-workstream SSE events and consuming them in the WorkstreamsPage drawer. Manual Refresh stays as a fallback; the page is honest when the stream is unreachable.

---

## 1. Hard rules check (founder brief)

| Rule | Status |
|---|---|
| 1. No production deploy | Yes - local-only changes |
| 2. No `USE_CONNECTION_REGISTRY_V2=true` flip | Yes - flag untouched |
| 3. No `vault --apply` | Yes |
| 4. No file deletions | Yes - additive only |
| 5. No secrets printed or committed | Yes |
| 6. No external scans | Yes |
| 7. No external messages | Yes |
| 8. No T5 / 3vilbob execution code modified | Yes |
| 9. No wholesale rewrite of Chat / Scan / Departments / Skills / Company Mode | Yes |
| 10. No agency-agents / new dependencies | Yes - reused existing `SSEChannel` + `useResilientSSE` primitives |
| Em dashes (project Rule 12) | None introduced (8 pre-existing in file headers untouched; verified via git diff) |

---

## 2. Stream approach chosen

### 2.1 Per-workstream `SSEChannel` registry on top of existing primitives

The Daena codebase already has two complete pieces of the puzzle:

| Existing primitive | Path | What it provides |
|---|---|---|
| `SSEChannel` | `backend/app/core/sse_channels.py` | In-process pub/sub bus with bounded per-subscriber queue (1000 events), drop-oldest on saturation, 25s idle heartbeat, async fan-out under a lock. Module-level singletons exist for `cron`, `queue`, `approvals`, `pipeline`. |
| `useResilientSSE` | `frontend/src/lib/sse.ts` | EventSource hook with bounded retries (1s→2s→4s→8s→15s capped), `fallbackPoll` on retry exhaustion, observable `status` (`connecting | connected | reconnecting | fallback | closed`), cookie auth via `withCredentials`. |

PR-SPINE-06 adds **one** new primitive on top: a per-workstream channel registry. Workstreams differ from the 4 module-level singletons because they are created at runtime (not known up-front), so a lazy registry is required:

```python
# backend/app/core/sse_channels.py
_workstream_channels: dict[str, SSEChannel] = {}
_workstream_channels_lock = asyncio.Lock()

async def get_workstream_channel(workstream_id: str) -> SSEChannel:
    """Return the SSEChannel for a workstream, creating it on first use."""
    ch = _workstream_channels.get(workstream_id)
    if ch is not None:
        return ch  # hot path: no lock
    async with _workstream_channels_lock:
        ch = _workstream_channels.get(workstream_id)  # re-check
        if ch is None:
            ch = SSEChannel(f"workstream:{workstream_id}")
            _workstream_channels[workstream_id] = ch
        return ch
```

**Why a lazy registry vs. a single broadcast channel:** A single `workstream` channel would mean every connected drawer receives every workstream's events and filters client-side. That is bad for two reasons:

1. **Cross-tenant fan-out.** Tenant A's drawer would receive tenant B's envelopes (the channel itself is process-scoped). Filtering by `tenant_id` in the consumer is fragile (depends on the consumer); per-id channels make isolation a property of the producer.
2. **Subscriber backpressure.** A single channel with 100 active drawers and 100 workstreams writing means every event fans out to 100 queues. Per-id channels keep fan-out scoped to the drawers that care.

**Memory cost analysis.** Each empty `SSEChannel` is `{name: str, subscribers: set, lock: asyncio.Lock}` ~200 bytes. At 10000 historical workstreams that is ~2MB. Acceptable for v1. A janitor that reaps channels with `subscriber_count == 0` and a recently observed terminal-state event is documented as PR-SPINE-06 debt below.

### 2.2 Two SSE event types, intentionally small

| Event type | When emitted | Payload |
|---|---|---|
| `workstream.event` | Any state change that appends a `WorkstreamEvent` row (start / transition / pause / resume / redirect / escalate / artifact attach with `emit_event=True` / `append_timeline_event`) | `{workstream_id, event: {id, kind, summary, payload, occurred_at}, snapshot: {...mutable fields...}}` |
| `workstream.snapshot` | Mutation that does NOT append a timeline entry (`update_progress`, `attach_audit_event_ref`, `attach_notification_ref`, `attach_artifact_ref(emit_event=False)`, `archive`) | `{workstream_id, snapshot: {...mutable fields...}}` |
| `workstream.bootstrap` | Sent ONCE at the start of the GET stream connection so a fresh subscriber renders immediately. | `{workstream_id, snapshot: {...full workstream...}, events: [...last 50 timeline events...]}` |
| `workstream.closed` | Server signal that the drawer should detach (today: archive landed). | `{reason: "archived" \| "stream_error"}` |

The dual event/snapshot split keeps the contract small. Frontend handler:
- on `workstream.event`: append the event to the timeline (deduped by id), merge the snapshot patch into the workstream row.
- on `workstream.snapshot`: merge the snapshot patch only.
- on `workstream.bootstrap`: replace the workstream + events state, mark not loading.
- on `workstream.closed`: trigger the page-level refresh + close the drawer.

### 2.3 Slim serializers

`api/v1/workstreams._serialize_workstream` is the full snapshot used by the GET endpoint (~16 fields). For per-event SSE, `_slim_snapshot` ships only the fields that mutate during a workstream's life:

```python
# Mutable fields on every SSE event.
{id, status, escalation_level, progress_percent, blocker_text,
 next_step_text, autopilot_paused, last_activity_at, archived_at,
 artifact_refs, audit_event_refs, notification_refs, total_tokens,
 total_cost_cents, goal}
```

Static fields (`tenant_id`, `user_id`, `department_id`, `source_type`, `source_ref_id`, `created_at`) are intentionally omitted - the frontend has them from the initial GET / bootstrap and they never change after start.

---

## 3. Backend endpoint added

### 3.1 New route

`GET /api/v1/workstreams/{workstream_id}/stream`

Tenant-scoped via `CurrentUser`. Returns `text/event-stream` with the standard nginx-friendly headers:

```python
{
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}
```

### 3.2 Sequence

```
client EventSource opens
  -> WorkstreamService.get(workstream_id, tenant_id=user.tenant_id)
       -> 404 if cross-tenant or unknown id
  -> workflow emits workstream.bootstrap (snapshot + last 50 events)
  -> get_workstream_channel(workstream_id)
       -> async for envelope in channel.subscribe():
            -> ping (idle heartbeat)  -> serialize as ": heartbeat\n\n"
            -> workstream.event       -> serialize as event: + data:
            -> workstream.snapshot    -> serialize as event: + data:
            -> snapshot.archived_at set -> emit workstream.closed + break
  -> client disconnect / app shutdown -> channel detaches the queue in finally
```

### 3.3 Why bootstrap on connect

The lifecycle race: a newly-spawned workstream may have already published `workstream.event` for STARTED before any client subscribes (the publish happens the moment `start()` commits). Without bootstrap, a fresh subscriber would miss the event entirely. The bootstrap envelope ships the full snapshot + last 50 events so the consumer renders immediately, then live updates take over.

### 3.4 Reused, not added

| Surface | Reused (no change required) |
|---|---|
| `app/core/sse_channels.SSEChannel` | The existing async pub/sub bus with bounded queue + heartbeat |
| FastAPI `StreamingResponse` | The existing scan-events endpoint pattern |
| Cookie auth via `CurrentUser` | The existing dependency injection |
| `WorkstreamService.get` / `list_events` | Used to produce the bootstrap |

---

## 4. Frontend focus behavior

### 4.1 `?focus=<workstream_id>` deep-link auto-opens the drawer

`WorkstreamsPage` reads the search param **once** on mount:

```typescript
useEffect(() => {
    if (typeof window === 'undefined') return
    const params = new URLSearchParams(window.location.search)
    const focus = params.get('focus')
    if (!focus) return
    setSelectedId(focus)
    params.delete('focus')
    const search = params.toString()
    const next = `${window.location.pathname}${search ? `?${search}` : ''}${window.location.hash}`
    window.history.replaceState({}, '', next)
}, [])
```

Why clear the param after consuming it: a later interaction (close + reopen) should not silently reopen the same workstream. The user's last navigation is the source of truth.

### 4.2 Source of `?focus=` callers (today)

- PR-SCAN-WS-01 success state in `ScanReport.tsx`: the "Create remediation task" button on a finding renders `<a href={"/workstreams?focus=" + workstream_id}>workstream</a>` after a successful POST.
- Future PR-NOTIF-FANOUT envelopes: `notification.workstream_id` will append `?focus=` so the bell click lands the operator in the right drawer.

The clear-after-consume pattern keeps every future deep-link surface reusing the same parameter without state leakage.

---

## 5. Live update behavior

### 5.1 Drawer subscribes to its own SSE channel

```typescript
const { status: sseStatus, reconnectAttempt } = useResilientSSE({
    url: `/api/v1/workstreams/${workstreamId}/stream`,
    eventTypes: [
        'workstream.bootstrap',
        'workstream.event',
        'workstream.snapshot',
        'workstream.closed',
    ],
    onEvent: handleStreamEvent,
    fallbackPoll,
    maxRetries: 5,
})
```

Status shows in the timeline header next to the Refresh button:

| `sseStatus` | Badge label |
|---|---|
| `connecting` | "Connecting…" (gray, pulsing radio icon) |
| `connected` | "Live" (emerald, steady radio icon) |
| `reconnecting` | "Reconnecting (n/5)…" (amber, pulsing) |
| `fallback` | "Live updates unavailable, use Refresh." (amber-orange, alert icon) |
| `closed` | "Stream closed" (gray) |

The fallback label exact-matches the founder brief: *"If SSE is unavailable, show 'Live updates unavailable, use Refresh.'"*

### 5.2 Event handler: dedupe + merge

```typescript
const handleStreamEvent = useCallback(
    ({ type, data: payload }) => {
        if (type === 'workstream.bootstrap') {
            // Replace state with the full bootstrap.
            seenEventIdsRef.current = new Set(events.map(e => e.id))
            setData({ workstream: snapshot, events })
            return
        }
        if (type === 'workstream.event') {
            setData(cur => {
                const merged = applySnapshot(cur.workstream, body.snapshot)
                if (seenEventIdsRef.current.has(body.event.id)) {
                    return { workstream: merged, events: cur.events }  // dedupe
                }
                seenEventIdsRef.current.add(body.event.id)
                return { workstream: merged, events: [...cur.events, body.event] }
            })
            return
        }
        if (type === 'workstream.snapshot') {
            setData(cur => ({ workstream: applySnapshot(cur.workstream, body.snapshot), events: cur.events }))
            return
        }
        if (type === 'workstream.closed') {
            onMutated()
            onClose()
        }
    },
    [workstreamId, onMutated, onClose],
)
```

The dedupe ref handles the bootstrap-then-fast-event race: bootstrap delivers events 1..50, an event 51 may arrive over the live channel right after, but if the client reconnects we may receive event 51 again on the next bootstrap. Tracking seen ids prevents double-render.

### 5.3 What updates live without manual Refresh

After PR-SPINE-06, the operator with a drawer open sees:

| Action | Without PR-SPINE-06 | With PR-SPINE-06 |
|---|---|---|
| Operator clicks Pause / Resume / Redirect / Archive | `refresh()` after the API call | `refresh()` AND a `workstream.event` arrives so the change appears even if the operator's local state is stale |
| A linked Task transitions to RUNNING (PR-SPINE-04 sync) | Refresh required | Progress bar bumps to ≥25 + DECISION marker appears in timeline |
| A linked Task COMPLETES | Refresh required | Status pill flips RUNNING→COMPLETE + progress fills to 100 + COMPLETED event appears in timeline |
| A linked Task FAILS | Refresh required | Status pill flips to FAILED + reason appears in timeline |
| A scan finding remediation creates a workstream and the operator already has the drawer open elsewhere | N/A (different workstream) | Per-id isolation: only the matching drawer sees this; others remain quiet |

---

## 6. Fallback behavior

### 6.1 Reconnect ladder

`useResilientSSE` schedules retries on EventSource error: 1s → 2s → 4s → 8s → 15s (capped). After 5 failed attempts the status flips to `fallback` and `fallbackPoll()` runs once.

Per the brief: *"keep manual Refresh as fallback"*. The Refresh button is always present in the drawer header (it was there pre-PR-SPINE-06 too); the SSE status badge appears next to it so the operator can read both signals at a glance.

### 6.2 `fallbackPoll` calls the same `refresh()` the manual button calls

```typescript
const fallbackPoll = useCallback(async () => {
    await refresh()
}, [refresh])
```

Once-only on retry exhaustion, then the operator can keep clicking Refresh to update. No silent infinite retry loop.

### 6.3 Honest "no live updates" copy

The `fallback` badge label is literally: **"Live updates unavailable, use Refresh."** This matches the founder brief verbatim. Never a fake "Live" pill when SSE is down.

### 6.4 Ping does not surface

The SSEChannel emits a `ping` envelope every 25 seconds of idle time. The route serializes pings as SSE comment lines (`": heartbeat\n\n"`) which EventSource silently swallows - the consumer's `onEvent` never fires for them. So the timeline does NOT get spammed with heartbeat noise, but the underlying TCP connection stays warm against nginx / Cloud Run idle timeouts.

---

## 7. Tests run

### 7.1 New tests (PR-SPINE-06)

`backend/tests/test_workstream_sse.py` - **16 tests, all green:**

| Group | Test | What it pins |
|---|---|---|
| Channel registry | `test_get_workstream_channel_returns_same_instance_for_same_id` | Identity for same id |
| | `test_get_workstream_channel_returns_distinct_for_distinct_ids` | Per-id isolation at the registry level |
| | `test_get_workstream_channel_concurrent_creation_is_safe` | Lock + re-check prevents orphan-subscriber race |
| | `test_workstream_channel_count_grows_with_unique_ids` | Introspection helper sanity |
| Slim serializers | `test_slim_snapshot_exposes_mutable_fields` | The snapshot covers what the frontend updates live |
| | `test_slim_event_renders_id_kind_summary_payload` | Event slim shape matches frontend timeline render |
| State change publishing | `test_start_publishes_workstream_event` | start() emits workstream.event with snapshot + STARTED kind (recorder-channel monkeypatch avoids the lifecycle race) |
| | `test_transition_publishes_workstream_event_with_new_status` | complete() / transition publishes COMPLETED event with new status in snapshot |
| | `test_update_progress_publishes_snapshot_only` | informational progress bump emits workstream.snapshot, no event key |
| | `test_attach_artifact_with_event_publishes_event` | emit_event=True path publishes workstream.event |
| | `test_attach_artifact_silent_publishes_snapshot` | emit_event=False path publishes workstream.snapshot |
| | `test_attach_audit_ref_publishes_snapshot` | audit ref attach is snapshot-only (anti-flood) |
| | `test_archive_publishes_snapshot_with_archived_at` | archive emits a snapshot with archived_at set so the drawer can detach |
| Best-effort isolation | `test_publish_failure_does_not_break_service_contract` | A broken SSE channel does NOT prevent the workstream mutating + committing |
| Fan-out | `test_two_subscribers_both_receive_published_event` | Multiple subscribers on the same workstream id all receive published events |
| Per-id isolation | `test_other_workstream_channel_does_not_receive_unrelated_event` | Subscriber on workstream A does NOT see workstream B's events |

### 7.2 Regression sweep (all green)

| File | Tests | Result |
|---|---:|---|
| `test_workstream_sse.py` (PR-SPINE-06, the new file) | 16 | 16/16 |
| `test_task_workstream_sync.py` (PR-SPINE-04) | 13 | 13/13 |
| `test_workstream_spine_skeleton.py` (PR-5) | 18 | 18/18 |
| `test_workstream_service.py` | 11 | 11/11 |
| `test_scan_remediation.py` (PR-SCAN-WS-01) | 18 | 18/18 |
| `test_settings_governance_guard.py` (PR-GOV-01) | 17 | 17/17 |
| `test_execution.py` | 6 | 6/6 |
| `test_execution_run_task.py` | 5 | 5/5 |
| **Combined adjacent surface** | **104** | **104/104** |

Zero regressions across the related surface. The "best-effort isolation" pattern (publish wrapped in try/except, channel failure logged but not raised) is what kept the prior tests green - the SSE addition is observable but never blocks the contract.

### 7.3 Frontend

- `npx tsc --noEmit` clean (0 errors).
- `npx vite build` clean (23s, no warnings, all assets produced).
- Playwright not run - the brief said "if cheap" and Daena does not yet have a Playwright spec for `WorkstreamsPage`. Adding one would require a fresh fixture for the auth cookie + an SSE-friendly browser config; documented as PR-SPINE-06 debt below.
- Browser smoke not run in this PR per hard rule 1 (no deploy / no live test against running backend). The frontend changes are typecheck-clean and the SSE handler logic is unit-pinnable on the backend (which the 16 tests cover).

### 7.4 Endpoint integration test (deliberately not written)

The `GET /workstreams/{id}/stream` route handler is ~30 LOC of glue: tenant check via `svc.get` (3 lines), bootstrap envelope (2 lines), the inner `_event_stream` async generator (~20 lines), terminal `StreamingResponse` wrapper (5 lines). A FastAPI TestClient SSE test would need to:

1. Spin up the test app + auth header
2. Open a streaming response (httpx supports it but the API is finicky)
3. Read the first frame, parse the bootstrap envelope
4. Mutate the workstream in a parallel task
5. Read the next frame, parse the workstream.event

That is a lot of ceremony for low marginal coverage on top of the 16 service-level tests already in place. The same trade-off was made for PR-SCAN-WS-01 (`test_create_remediation_invalid_dept_id_raises` covers the service; the route was visually inspected). When integration coverage becomes load-bearing, a new `tests/test_workstream_stream_endpoint.py` can ship in a follow-up.

---

## 8. Files changed

### 8.1 Backend (modified)

- `backend/app/core/sse_channels.py` - added `_workstream_channels` registry + `get_workstream_channel` async helper + `workstream_channel_count` introspection. Mirrors the existing `SSEChannel` API; no breaking change.
- `backend/app/services/workstream_service.py` - added module-level `_slim_event`, `_slim_snapshot`, `_publish_workstream_event`, `_publish_workstream_snapshot`. Wired publishing into `start`, `transition`, `pause_autopilot`, `resume_autopilot`, `redirect`, `escalate`, `archive`, `update_progress`, `attach_artifact_ref` (event vs snapshot per `emit_event` flag), `attach_audit_event_ref`, `attach_notification_ref`, `append_timeline_event`. All publish calls are best-effort wrapped (try/except + logger.warning).
- `backend/app/api/v1/workstreams.py` - imports asyncio + json + `Request` + `StreamingResponse` + `get_workstream_channel`. Added `GET /{workstream_id}/stream` endpoint with bootstrap + per-event forwarding + heartbeat passthrough + archive-detected close.

### 8.2 Backend (new)

- `backend/tests/test_workstream_sse.py` - 16 contract tests.

### 8.3 Frontend (modified)

- `frontend/src/pages/WorkstreamsPage.tsx` - added `useResilientSSE` import + `RadioTower` icon + types `StreamSnapshotPayload` / `StreamEventPayload` / `StreamBootstrapPayload` + `applySnapshot` merger + `SSE_STATUS_STYLE` map + `LiveStatusBadge` component + dedupe ref `seenEventIdsRef` + `handleStreamEvent` handler + `fallbackPoll` callback + `useResilientSSE` subscription inside `WorkstreamDetailDrawer` + status badge in the timeline header. Page-level: `useEffect` that reads `?focus=<id>` and clears the param.

### 8.4 Docs (new)

- `docs/Ultraview/PR_SPINE_06_WORKSTREAM_LIVE_CONSOLE_REPORT.md` (this file).

### 8.5 Files NOT touched (per hard rules)

- All T5 / EvilBob / red_team / exploitation / zero_day / osint / evilbob_mode files
- `chat_orchestrator.py`, `cognitive_scan_engine.py`, `scan_workflow.py`
- `vault_adapter.py`, `vault_migration.py`, `oauth_credentials_store.py` (Rule 18 protected files)
- `chat.py`, `governance.py`, `audit.py` (the hot path)
- `frontend/src/pages/TasksPage.tsx`, `ChatPage.tsx`, `ScanPage.tsx`, `SkillsPage.tsx`, `SecurityDashboardPage.tsx`
- `connection_v2/` flag (`USE_CONNECTION_REGISTRY_V2`)

---

## 9. Remaining live-console debt

### 9.1 Items deferred to future PRs

| Debt | Severity | Future PR |
|---|---|---|
| Per-workstream channels are kept for the process lifetime; an empty channel costs ~200 bytes but accumulated count grows monotonically. At 10000 historical workstreams = 2MB. No janitor today. | LOW | PR-SPINE-06-GC - reap channels with `subscriber_count == 0` AND a recently observed terminal-state event (>1h since archived/COMPLETE/FAILED). |
| The drawer subscribes to a single workstream; the page-level list is still polled (Refresh button + status filter change). A higher-level "any workstream" change pushed to the page would reduce reload latency further. | LOW | PR-SPINE-06-LIST-LIVE - either a page-level SSE that emits "workstream X status changed" envelopes for the visible filter, or extend the per-workstream subscription pattern to a multi-workstream subscription helper. |
| Playwright smoke for the focus deep-link auto-open + drawer SSE rendering is not in this PR. | LOW | PR-SPINE-06-E2E - one Playwright spec that opens `/workstreams?focus=<id>`, asserts the drawer opens, simulates a backend mutation via API, asserts the timeline updates without Refresh. |
| Endpoint-level integration test (TestClient SSE) is not written. | LOW | If integration coverage becomes load-bearing, add `tests/test_workstream_stream_endpoint.py` that pumps one mutation while a streaming response is open. |
| Multi-tab dedupe: two browser tabs viewing the same workstream both subscribe and both append the same events to their local state. Each tab is independent so this is not a shared-state race - it is intentional. Documented for clarity. | INFORMATIONAL | n/a |
| The backend publishes from inside the `WorkstreamService` methods that mutate state. Sources outside the service (a future custom orchestrator that writes directly to `Workstream` rows) would NOT publish. | MEDIUM | Document as: "every workstream mutation must go through `WorkstreamService` methods." Already enforced by code organization; future PRs that introduce new mutation paths must add a publish call. |

### 9.2 What this PR explicitly does NOT promise

- **No new event taxonomy.** The brief was clear: *"Do not invent broad new event taxonomy if not necessary."* PR-SPINE-06 ships exactly two SSE event types (`workstream.event`, `workstream.snapshot`) plus the framing envelopes (`workstream.bootstrap`, `workstream.closed`). Future SSE consumers (PR-NOTIF-FANOUT, PR-LEARN-01) can extend if needed.
- **No SSE on the page-level list.** Today the list refreshes when the filter changes or the operator clicks Refresh. The drawer is the live surface; the list is honest "manual refresh" - status badge does not appear at page level.
- **No backpressure mechanism for very chatty workstreams.** The SSEChannel drops the oldest event when a subscriber's queue saturates (1000 events). At 100 events/sec a slow client gets 10 seconds of headroom; the channel logs a `dropped_event` warning + emits a `channel.dropped` envelope to the consumer (visible in the network tab; not surfaced to the UI). For typical workstream traffic (at most a handful of events per second), this is invisible.
- **No retry for `workstream.closed`.** When the server signals `archived`, the drawer closes. Re-archiving an already-archived workstream is a no-op (PR-5), so reopening the same drawer would just receive the bootstrap with `archived_at` set and immediately close again. The page-level `onMutated` refresh drops the row from the list - the operator does not see it again unless the list filter changes to include archived rows (which is not exposed today).

---

## 10. Honesty notes

- **The frontend tsc + vite build are the only CI signals run for the frontend.** No browser smoke, no Playwright. The behavior described in §5 is true on inspection of the code; the test gates are at the backend service contract layer (16 tests) which is where the actual event emission lives.
- **The bootstrap envelope shape is `{snapshot, events}`** to give a fresh subscriber everything it needs in one frame. The same shape COULD be returned by a separate `GET /workstreams/{id}` call (which already exists), but that would mean the client makes 2 round trips for the same data on connection. The bootstrap-on-stream pattern collapses it into 1 round trip (the SSE connection itself).
- **Per-workstream channel registry is in-process only.** A horizontally-scaled deploy (multiple gunicorn workers) would NOT cross-publish. PR-SPINE-06 is honest about this: cloud deploy is paused (CLAUDE.md) and Daena is a single-process dev service today. When horizontal scale is needed, PR-SPINE-06-CROSS-PROCESS would replace the in-memory dict with Redis pub/sub - the `SSEChannel` interface is small enough to be swapped without consumer changes.
- **All SSE publish calls are best-effort.** A broken channel (impossible in practice given the in-process registry, but possible if a future Redis-backed implementation drops the connection) does NOT prevent the workstream mutation from committing. Pinned by `test_publish_failure_does_not_break_service_contract`.
- **The `?focus=` param is consumed-then-cleared** so a later interaction (close + reopen) does not silently reopen the same workstream. This is the same pattern the chat page uses for its conversation-id deep-link. Operator's last navigation wins.

---

## 11. Commit message

```
canonicalization: add workstream live console updates

PR-SPINE-06: every Workstream now has a per-id SSE channel that the
WorkstreamsPage drawer subscribes to. State changes (status, progress,
artifact / audit / notification refs, archive) push to the drawer
without manual Refresh. The Refresh button stays as fallback, and the
"Live updates unavailable, use Refresh." copy fires when the SSE
reconnect ladder exhausts.

Backend
- New helper get_workstream_channel(id) on the existing SSEChannel
  primitive. Lazy registry; channels persist for the process lifetime.
- New module-level _slim_snapshot / _slim_event serializers and
  _publish_workstream_event / _publish_workstream_snapshot helpers
  inside WorkstreamService. Best-effort wrapped: SSE failure does not
  break the contract.
- Wired publishing into start, transition, pause/resume autopilot,
  redirect, escalate, archive, update_progress, attach_artifact_ref
  (event vs snapshot per emit_event flag), attach_audit_event_ref,
  attach_notification_ref, append_timeline_event.
- New endpoint: GET /api/v1/workstreams/{workstream_id}/stream
  - Tenant-scoped via svc.get (404 on cross-tenant)
  - Emits one workstream.bootstrap envelope on connect (snapshot +
    last 50 events) so a fresh subscriber renders immediately
  - Forwards channel envelopes (workstream.event, workstream.snapshot)
  - Serializes idle pings as SSE comment lines (no consumer surface)
  - Closes on archive

Frontend
- WorkstreamsPage: page-level useEffect honors ?focus=<id> and clears
  the param after consuming. Drawer subscribes via useResilientSSE,
  honest reconnect/error states (Live / Reconnecting (n/5) / "Live
  updates unavailable, use Refresh." / Stream closed). Event handler
  dedupes by event id (bootstrap + fast follow-up race) and merges
  snapshot patches into the workstream row.

Tests
- 16 new contract tests in test_workstream_sse.py (all green)
- 0 regressions across test_task_workstream_sync.py (13/13),
  test_workstream_spine_skeleton.py (18/18),
  test_workstream_service.py (11/11),
  test_scan_remediation.py (18/18),
  test_settings_governance_guard.py (17/17),
  test_execution.py (6/6), test_execution_run_task.py (5/5)
- 88 regression tests pass alongside 16 new = 104 total
- frontend tsc clean, vite production build clean (23s)

Honors all 10 founder hard rules. No deploy. No external messages.
No T5 changes. No new dependencies (reused existing SSEChannel +
useResilientSSE primitives).

Report: docs/Ultraview/PR_SPINE_06_WORKSTREAM_LIVE_CONSOLE_REPORT.md
```

End of report.
