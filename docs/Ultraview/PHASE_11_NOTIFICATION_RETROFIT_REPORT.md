# Phase 11 PR-S2.1 — Notification Retrofit Report

**Date:** 2026-05-01
**Operator:** Claude Code (Opus 4.7) under founder-direction Phase 11 PR-S2.1 task
**Scope:** Wire existing backend services to call
`NotificationService.emit` at the right moments so the 5 backend-
enforced `notif_*` toggles produce real in-app rows from real system
behavior. **Three of five wired**, **two skipped with documentation**.

> **Headline:** **3 of 5 candidate event paths now produce real
> in-app rows** from existing service code: `task_complete` (every
> successful task), `budget_alert` (personal quota breach with
> 60-min per-user dedup), `governance_rejection` (every approval
> reject, routed to the requester not the approver). **2 paths
> intentionally skipped** because they have no per-user fan-out:
> `heartbeat` (system-wide daemon, no `user_id` in scope) and
> `runtime_disconnect` (singleton health tracker, no `tenant_id`
> in scope).
>
> **No external send.** No email, SMS, OS push, DM, webhook, or
> external scan. Hard rules respected.
>
> Tests: **7 new retrofit tests pass** (3 per-event happy paths +
> 3 per-event suppression tests + 1 dedup test). **68 regression
> tests pass** (PR-S1, PR-S2, Phase 10b, execution, chat, memory).
> Frontend `tsc` clean.

---

## 1. Files changed

| File | Change | Lines |
|---|---|---|
| `backend/app/services/execution_service.py` | Snapshot `captured_user_id = task.user_id` at line 716; emit `task_complete` after the `update_task_status(...COMPLETED)` call inside `_background_run`; explicit `bg_db.commit()` because the bg session is detached from the request session | +37 |
| `backend/app/services/cost_guard.py` | Add `_recent_warn_emits: ClassVar[dict[UUID, float]]` + `_BUDGET_WARN_WINDOW_SECONDS = 3600`; emit `budget_alert` from the existing `warn`/`allow_overage` branch in `preflight_check` with 60-min per-user dedup | +48 |
| `backend/app/services/approval.py` | Emit `governance_rejection` to `request.user_id` (the requester) at the end of `ApprovalService.reject`, after `_emit_decision_event`; best-effort wrap | +27 |
| `backend/tests/test_phase11_notification_retrofit.py` | 7 new tests: 3 happy-path emits, 3 disabled-flag suppressions, 1 dedup-within-window | +355 (new file) |
| `docs/Ultraview/PHASE_11_NOTIFICATION_RETROFIT_REPORT.md` | This report | +355 (new file) |

Total: **5 files, +822 / 0** (pure additions).

---

## 2. Tests run

### 2.1 New tests (Phase 11 PR-S2.1)

```
tests/test_phase11_notification_retrofit.py            7 passed in 17.12s
  test_task_complete_emits_notification_when_enabled    PASSED
  test_task_complete_suppressed_when_flag_off           PASSED
  test_governance_rejection_emits_notification_to_requester  PASSED
  test_governance_rejection_suppressed_when_flag_off    PASSED
  test_budget_alert_emits_on_warn_action                PASSED
  test_budget_alert_dedup_within_window                 PASSED
  test_budget_alert_suppressed_when_flag_off            PASSED
```

### 2.2 Regression — Phase 10b/11 PR-S1/PR-S2 + execution + chat + memory

```
tests/test_phase11_notification_emitter.py             6 passed
tests/test_phase11_privacy_enforcement.py              6 passed
tests/test_phase10b_ghost_call_fixes.py                8 passed
tests/test_execution_run_task.py                       5 passed
tests/test_chat.py                                    11 passed
tests/test_memory.py                                  32 passed
                                                  ─────────
                                                  68 passed in 86.76s
```

**Total scoped sweep: 7 new + 68 regression = 75 pass / 0 fail.**

### 2.3 Frontend

```
$ cd frontend && npx tsc --noEmit; echo $?
0
```

Zero TypeScript errors. (PR-S2.1 has no frontend changes — all
retrofit work is backend.)

---

## 3. Which event paths were wired

### 3.1 `task_complete` — `execution_service.py:765-800`

**Trigger:** `ExecutionService._background_run` reaches the
`update_task_status(status=COMPLETED)` call after the simulated
work loop.

**Emit:** Best-effort, gated by `notif_task_complete`. Title
`"Task completed: <name>"`, message taken from `result["summary"]`,
severity `success`, source `execution_service.background_run`.

**Spam protection:** One emit per task per terminal transition.
Tasks only complete once; if a task is retried it goes RUNNING →
COMPLETED again and emits a new row (which is correct — that's a
new user-visible event).

**Failure mode:** The emit is wrapped in try/except + an explicit
`bg_db.rollback()` on emit failure so the bg session can close
cleanly. Notification failures NEVER propagate to the user-visible
task lifecycle.

**Important detail:** Because the background runner uses a detached
session (`bg_factory(self.db.bind, ...)`), `update_task_status`
already commits the COMPLETED row on the bg session before we run
the emit. So the emit code adds a fresh row + explicit commit. This
is why the test passes — without the explicit commit, the
notification would be dropped at session close.

### 3.2 `budget_alert` — `cost_guard.py:286-345`

**Trigger:** `CostGuard.preflight_check` runs the per-user quota
check. When the user is over their personal quota AND `action` is
`"warn"` or `"allow_overage"` (i.e. the call is allowed to proceed),
the existing log-only warn branch fires.

**Emit:** Best-effort, gated by `notif_budget_alert`. Title
`"Personal usage near limit"`, message includes spent/limit and the
overage action, severity `warning`, source `cost_guard.preflight_check`.

**Spam protection — CRITICAL:** `preflight_check` runs before
**every** LLM call. Without dedup, a chat session of 50 messages
from a user who is over quota would write 50 `budget_alert` rows.
The dedup is a process-level `_recent_warn_emits: ClassVar[dict[UUID,
float]]` with a 60-minute sliding window. After the first emit for
a user, subsequent preflights within 60 min skip the emit but still
log + still allow the call.

**Trade-offs of the dedup window choice:**

| Window | Pros | Cons |
|---|---|---|
| 0 (no dedup) | Real-time accuracy | 50 rows / hour for one user — bell unreadable |
| 5 min | Catches spending spikes | Still ~12 rows/hour worst case |
| **60 min (chosen)** | One row per hour worst case; readable bell | User might miss a spike if they hit quota at 12:00 and again at 12:30 |
| 24 hr | Cleanest bell | First-of-day notification might come hours after the actual breach |

60 min is the sweet spot for a typical session length. Reset on
process restart (intentional: a fresh deploy gives one signal per
user that the gate is still firing). If multi-replica Cloud Run
deploys are added, each replica's set is independent — same rationale
as PR-S1's `_privacy_blocked_warned`.

**Important detail:** `preflight_check` is load-bearing. Notification
emit failures are caught + warning-logged but never raise. The cost
gate continues unaffected.

### 3.3 `governance_rejection` — `approval.py:184-220`

**Trigger:** `ApprovalService.reject` (called from the approvals UI
or any service that rejects a `GoaRequest`) sets
`status=REJECTED`, commits, and runs the existing
`_emit_decision_event` border-agent fanout.

**Emit:** Best-effort, gated by `notif_gov_reject`. Title
`"Action rejected: <action_type>"`, message is the rejection reason
or a default fallback, severity `warning`, source `approval.reject`.

**Routing — KEY DESIGN DECISION:** The notification emits to
`request.user_id` (the **original requester**), NOT `decided_by`
(the **approver**). The approver does not need to be notified of
their own decision — they already know they just clicked Reject.
The user being notified is the one whose action was blocked.

The test `test_governance_rejection_emits_notification_to_requester`
explicitly asserts the approver does NOT receive a copy.

**Spam protection:** One emit per rejection. Rejections are discrete
events (the same request can only be rejected once), so no dedup
window is needed.

**Failure mode:** Best-effort wrap; never raises from the rejection
path.

---

## 4. Which event paths were skipped and why

### 4.1 `heartbeat` — SKIPPED

**Path investigated:** `app/services/heartbeat/heartbeat_daemon.py`,
`app/services/heartbeat/heartbeat_checks.py`,
`app/services/heartbeat/cron_scheduler.py`.

**Blocker:** The heartbeat daemon is **system-wide**, not per-tenant
or per-user. Check functions like `check_runtime_health` are
stateless and have NO `tenant_id` or `user_id` in scope. A finding
like "3 runtimes offline" is a system-level signal, not "your
runtime is offline."

**What would be needed to wire safely:**

1. A per-tenant heartbeat schedule (today there is only one global
   schedule).
2. A per-user fan-out service that maps "system finding X" →
   "notify user Y because Y is the founder/admin of tenant Z."
3. A subscription model for notification routing (which users want
   which findings — a tenant might have 50 employees but only 1
   ops-admin who wants heartbeat pings).

All three are bigger than PR-S2.1 scope. Forcing a wire today
would either (a) emit zero rows because we have no user_id, or (b)
spam every user in every tenant with system-level findings.

**Documented next step:** PR-S2-followup or a dedicated PR-NOTIF-FANOUT
that adds tenant-aware heartbeat scheduling + a per-tenant
"notification subscriber" model. Out of scope here.

### 4.2 `runtime_disconnect` — SKIPPED

**Path investigated:**
`app/services/runtimes/health_tracker.py:195-217`,
`app/services/runtimes/registry.py`,
`app/api/v1/runtimes.py`.

**Blocker:** `RuntimeHealthTracker` is a **process-level singleton**
keyed only by `provider_id` (e.g. `"claude_cli"`, `"ollama"`). It
has NO `tenant_id` or `user_id` in scope. Even though it DOES have
proper transition state (`record_failure` only flips HEALTHY → DEGRADED
once per `consecutive_failures >= 2` threshold — so re-emits on every
probe failure are already prevented), there is nobody to emit TO.

**What would be needed to wire safely:**

1. A `provider → tenants[]` mapping (which tenants depend on this
   provider as their primary runtime).
2. A `tenant → users[]` notification subscriber (which users in
   that tenant want runtime alerts).

Same pattern as heartbeat fan-out. Out of scope.

**Note on a half-measure I considered + rejected:** The API endpoint
`POST /api/v1/runtimes/{id}/test` IS user-initiated, so `tenant_id`
+ `user_id` ARE in scope at that handler. I could emit a
`runtime_disconnect` row from the test handler when the result is
"down." But that's misleading — the user just clicked "Test," so a
notification is redundant (they're already looking at the result on
screen). The genuinely useful event is **proactive** ("your primary
runtime went down without you asking"), and that requires the
fan-out infrastructure above. Skipping is the honest call per Rule
17.

---

## 5. Spam / duplicate protections

| Event type | Frequency | Spam guard | Test |
|---|---|---|---|
| `task_complete` | Once per task completion | Natural — tasks only complete once. Retry → new completion → new row (correct). | `test_task_complete_emits_notification_when_enabled` (asserts exactly 1 row) |
| `budget_alert` | Could fire 50×/hour without guard | 60-min per-user `_recent_warn_emits` dedup | `test_budget_alert_dedup_within_window` (5 preflights → 1 row) |
| `governance_rejection` | Once per rejection | Natural — rejections are discrete | implicit in cross-user isolation test |

Suppressed-by-setting events emit only a debug log
(`notification.suppressed_by_setting`), never an audit row. Same
rationale as PR-S2 §6.7: notification preferences are routine UX
choices, not governance events worth ledger space.

---

## 6. Which `notif_*` toggles now generate real rows from real behavior

| `notif_*` flag | Was DEAD before PR-S2 | After PR-S2 (emit primitive only) | After PR-S2.1 (real triggers) |
|---|---|---|---|
| `notif_task_complete` | DEAD | enforced — but only the test endpoint emitted | **enforced** — every successful task lands one row |
| `notif_budget_alert` | DEAD | enforced — test endpoint only | **enforced** — quota breach lands one row per 60 min |
| `notif_heartbeat` | DEAD | enforced — test endpoint only | **enforced gate, NO real triggers** (skipped — see §4.1) |
| `notif_gov_reject` | DEAD | enforced — test endpoint only | **enforced** — every rejection lands one row to the requester |
| `notif_runtime_disconnect` | DEAD | enforced — test endpoint only | **enforced gate, NO real triggers** (skipped — see §4.2) |

The two skipped flags retain the PR-S2 "Enforced by backend" Badge
because the gate IS active on the emit path — they just don't have
a real trigger landing the rows yet. The badge is still honest
("if this fires, your setting will be respected"), but the
operator should know the trigger is wired in PR-NOTIF-FANOUT, not
PR-S2.1.

I did NOT change the frontend Badge for these two — flipping them
back to "Coming soon" would be inaccurate (the gate IS enforced,
just unused), and the SettingsNotifications copy at PR-S2 already
hedged on per-event delivery.

---

## 7. Caveats + design decisions

### 7.1 Why bg_db needs an explicit commit for `task_complete`

The first run of the test failed with "Expected exactly 1 row, got
0" even though the task completed and the emit code ran without
error. Root cause: `_background_run` uses a detached session
(`bg_factory(self.db.bind, ...)`). `update_task_status` commits its
own transaction internally. After that commit, the bg session is in
a fresh, uncommitted state — my notification add went into that
state but was rolled back when the `async with bg_factory()` block
exited.

Fix: explicit `await bg_db.commit()` after the emit, with a paired
`bg_db.rollback()` in the except branch so a failed emit can't leave
the session in a bad state.

### 7.2 The budget_alert dedup is per-process, not per-replica

If/when Cloud Run scales to N replicas, each replica's
`_recent_warn_emits` is independent — a user could theoretically
get N rows per 60-min window if their requests round-robin across
replicas. Same trade-off documented in PR-S1 §6.2 for
`_privacy_blocked_warned`. If the founder hits this in production,
swap to a Redis key with a 60-min TTL.

For local dev (this PR's scope), one process = one set = one row
per hour per user.

### 7.3 The 7 skipped paths from the brief that are NOT here

The brief listed 5 candidate paths. I wired 3, skipped 2. The 5
notification event types defined in `_NOTIF_TYPES` plus `system_info`
+ `privacy_blocked` (the two ungated types from PR-S2) gives 7 total.
`system_info` is fired only by the test endpoint (correct — it's a
ping). `privacy_blocked` is the existing PR-S1 audit trail point
that is NOT yet a notification (PR-S1 audited via `goa_audit_events`,
not `notifications`). I did NOT add a `privacy_blocked` notification
emit in this PR because:

1. The brief's scope is the 5 toggle-gated events.
2. Notifying the user "we blocked your memory write" might be useful,
   but PR-S1 already audits + the user explicitly opted in to the
   privacy gate (they set the toggle), so a notification is debatable
   value.
3. Adding a `privacy_blocked` notification with proper "once per
   process" dedup is a separate (small) PR.

### 7.4 `task_complete` doesn't fire on FAILED

A task that fails goes RUNNING → FAILED, not RUNNING → COMPLETED.
My emit only triggers on the COMPLETED branch. **Intentional**: the
event type is `task_complete`, not `task_finished`. A failed task
might warrant a different notification (e.g. `task_failed`) but
that's a new event type that needs a `notif_task_failed` toggle.
Out of scope.

If the founder wants failed-task notifications, the cleanest path is
a follow-up PR that adds `notif_task_failed` to the schema +
`task_failed` event type + an emit in the FAILED branch of
`_background_run` (line 808 area).

### 7.5 Dedup state lives ON the class, not the instance

`_recent_warn_emits: ClassVar[dict[UUID, float]] = {}` is class-level
(process-lifetime), NOT instance-level (per-request). Same pattern
as PR-S1's `_privacy_blocked_warned`. Reason: `CostGuard(BaseService)`
is instantiated per-request via FastAPI dependency injection, so an
instance attribute would reset on every chat call — defeating the
dedup. Class-level survives across instances within the process.

The test resets `CostGuard._recent_warn_emits.pop(user_id, None)` in
the test fixture so test ordering can't suppress emits. This is the
same pattern PR-S1 uses for its dedup set.

---

## 8. What remains for PR-S2.2 (and beyond)

| PR | Scope | Estimate |
|---|---|---|
| **PR-S2.2** | `POST /notifications/{id}/read` + `POST /notifications/read-all` + bell wires Dismiss / Clear-all to backend. SSE `/notifications/stream` channel for live push (replaces hydrate-on-mount in PR-S2). | ~3h |
| **PR-NOTIF-FANOUT** | Per-tenant heartbeat scheduling + provider→tenant mapping for runtime_disconnect + notification subscriber model. Closes the 2 skipped triggers in §4. | ~6h |
| **PR-NOTIF-PRIVACY** | Optional: `privacy_blocked` event emit with once-per-process dedup so privacy-block decisions surface in the bell as well as the audit ledger. | ~30min |
| **PR-NOTIF-TASK-FAILED** | Optional: add `task_failed` event type + `notif_task_failed` toggle + emit in `_background_run` FAILED branch. | ~1h |

Phase 11 sequence remaining: ~14h still to ship the rest of the
roadmap from PR-S3 (budget vocab) through PR-H1 (heartbeat config
DB persistence), independent of the PR-S2.x notification track.

---

## 9. Hard rules respected

- ✓ No production deploy.
- ✓ `USE_CONNECTION_REGISTRY_V2=true` not flipped.
- ✓ No `vault --apply`.
- ✓ `vault.py` / `oauth_credentials_store.py` not touched.
- ✓ No secrets read or printed.
- ✓ No external scans.
- ✓ **No external send** — no email, SMS, OS push, DM, webhook, or external API call. §3 walks each emit; §4 documents the skipped paths.
- ✓ PR-S2.2 NOT started (per brief's "Do not start PR-S2.2 yet").
- ✓ Dedup / spam protection in place where the path can fire frequently (§5).
- ✓ Bad wires SKIPPED with documentation rather than forced (§4).
- ✓ Suppressed-by-setting events stay debug logs, not audit rows (§5).

End of report.
