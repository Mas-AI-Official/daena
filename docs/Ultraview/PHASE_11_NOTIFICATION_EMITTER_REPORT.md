# Phase 11 PR-S2 — Notification Emitter Stub Report

**Date:** 2026-05-01
**Operator:** Claude Code (Opus 4.7) under founder-direction Phase 11 PR-S2 task
**Scope:** Make the `notif_*` user settings honest by giving them a
real backend consumer. **Only in-app notifications**. No email, no
SMS, no desktop OS push, no external sends.

> **Headline:** **5 of 9 `notif_*` toggles flip from "Coming soon"
> to "Enforced by backend"** — they now gate row creation in a new
> `notifications` table read by the existing header bell. Two
> ungated event types (`system_info`, `privacy_blocked`) always
> emit. Three toggles (`notif_sound`, `notif_email`,
> `notif_daily_digest`) stay Coming Soon because no delivery channel
> exists.
>
> **No external notification was sent.** The brief's hard rule
> ("Do not send real email, SMS, desktop OS, or external
> notifications") was respected.
>
> Tests: **6 new emitter tests pass**. **22 Phase 10/10b/11 PR-S1
> regression tests pass**. **43 chat + memory tests pass.** Frontend
> `tsc` clean (exit 0).

---

## 1. Files changed

| File | Change | Lines |
|---|---|---|
| `backend/app/models/notification.py` | NEW — minimal `Notification` model (id, tenant_id, user_id, type, title, message, severity, source, read_at, created_at, updated_at) | +96 (new file) |
| `backend/app/models/__init__.py` | Register `Notification` in import + `__all__` | +2 |
| `backend/app/services/notification_service.py` | NEW — `NotificationService.emit / list_recent` with per-event flag gate | +247 (new file) |
| `backend/app/api/v1/notifications.py` | NEW — `GET /notifications`, `POST /notifications/test` | +123 (new file) |
| `backend/app/api/v1/__init__.py` | Register `notifications` router | +5 |
| `backend/tests/test_phase11_notification_emitter.py` | NEW — 6 tests covering gate, ungated types, both endpoints, cross-user isolation, unread filter | +252 (new file) |
| `frontend/src/pages/settings/SettingsNotifications.tsx` | Real `handleSendTest` calls `POST /notifications/test`; 5 per-event toggles flip from `disabled` + amber Coming-Soon to interactive + green Enforced-by-backend; sound/email/daily-digest unchanged | +82 / -24 |
| `frontend/src/stores/uiStore.ts` | NEW `hydrateNotificationsFromBackend(limit)` exported helper | +51 |
| `frontend/src/components/layout/Header.tsx` | Import + once-on-mount call to `hydrateNotificationsFromBackend(20)` so the bell shows persisted rows after browser refresh | +9 / -1 |

Total: **9 files, +867 / -25**.

---

## 2. Tests run

### 2.1 New tests (Phase 11 PR-S2)

```
tests/test_phase11_notification_emitter.py            6 passed in 9.77s
  test_emit_default_writes_row                         PASSED
  test_emit_disabled_flag_suppresses_row               PASSED
  test_emit_ungated_type_always_writes                 PASSED
  test_post_test_endpoint_creates_row                  PASSED
  test_get_list_returns_recent_for_user                PASSED  (cross-user isolation)
  test_get_list_unread_only_filter                     PASSED
```

### 2.2 Regression — Phase 10/10b + Phase 11 PR-S1

```
tests/test_phase11_privacy_enforcement.py             6 passed
tests/test_phase10b_ghost_call_fixes.py               8 passed
tests/test_phase10_unsafe_gates.py                    5 passed
tests/test_phase10_chat_session_audit.py              3 passed
                                                  ─────────
                                                  22 passed in 22.51s
```

### 2.3 Regression — chat + memory (the actual blast-radius)

```
tests/test_chat.py                                    11 passed
tests/test_memory.py                                  32 passed
                                                  ─────────
                                                  43 passed in 43.61s
```

**Total scoped sweep: 6 new + 22 phase regression + 43 chat/memory = 71 pass / 0 fail.**

### 2.4 Frontend

```
$ cd frontend && npx tsc --noEmit; echo $?
0
```

Zero TypeScript errors.

---

## 3. Which toggles are now real

### 3.1 Per-event in-app toggles — ENFORCED BY BACKEND

| `notif_*` key | UI label | Event type | Behavior when False |
|---|---|---|---|
| `notif_task_complete` | Task completion | `task_complete` | Row not written; sentinel returned |
| `notif_budget_alert` | Budget alerts | `budget_alert` | Row not written |
| `notif_heartbeat` | Daena Heartbeat findings | `heartbeat` | Row not written |
| `notif_gov_reject` | Governance rejections | `governance_rejection` | Row not written |
| `notif_runtime_disconnect` | Runtime disconnection | `runtime_disconnect` | Row not written |

When True or unset → `Notification` row created in `notifications` table.

### 3.2 Always-emit event types (no opt-out flag — by design)

| Event type | Why ungated |
|---|---|
| `privacy_blocked` | A privacy-block decision is something the user MUST see. Hiding it would be a worse trust hazard than the row in the bell. |
| `system_info` | Used by `Send Test` and any future "system says X" message. Suppressing the test would defeat its purpose ("did the plumbing work?"). |

### 3.3 Master gate (client-side only — UNCHANGED)

| `notif_*` key | UI label | Behavior |
|---|---|---|
| `notif_desktop` | Enable desktop notifications | Master gate: controls whether the browser asks for OS notification permission and whether the test fires an OS notification. **Server-side row creation is orthogonal** — turning this off does not stop in-app rows from landing. |

---

## 4. Which toggles remain Coming Soon

| `notif_*` key | UI label | Reason | Phase 11 PR that closes it |
|---|---|---|---|
| `notif_sound` | Notification sound | No audio delivery channel (no `<audio>` pipeline, no sound asset registry) | none yet — needs audio surface design |
| `notif_email` | Enable email notifications | No SMTP / provider endpoint — `emailConfigured = false` hard-coded in the component (consistent with Phase 10C-D copy: "this page will not pretend email tests can send") | none yet — needs an outbound email provider |
| `notif_daily_digest` | Daily digest | Depends on `notif_email` AND a scheduler-driven digest job (neither exists) | none yet — depends on `notif_email` first |

These three correctly stay disabled with their existing Coming Soon
copy. Per Rule 17 ("if a feature cannot answer 'where does this
persist?' and 'how does the user see it fail?', it does not ship"),
flipping these without a delivery channel would be the same trust
hazard PR-S1 fixed for privacy.

---

## 5. Was any external notification sent? **No.**

| External channel | This PR? | Notes |
|---|---|---|
| Email (SMTP / SendGrid / Resend / etc.) | NO | No SMTP wired anywhere in the codebase. `emailConfigured = false` in `SettingsNotifications.tsx`. |
| SMS | NO | No SMS provider wired. |
| Desktop OS push (browser `Notification` API) | NO from server | The Send Test button MAY fire a browser-side `new Notification(...)` call **only if** the user previously granted permission AND `notif_desktop` is True. That fires entirely client-side; the server makes no OS call. |
| LinkedIn / X / Slack DMs | NO | Per CLAUDE.md social-media-marketing-soul: never auto-send DMs. |
| External webhooks | NO | No webhook endpoint registered or called. |

The brief's hard rule was: "Do not send real email, SMS, desktop OS,
or external notifications." Respected in full.

The browser `Notification` API call inside `handleSendTest` is
preserved from the existing component (not added by this PR) and is
an entirely client-side OS notification gated by browser permission +
the `notif_desktop` master toggle. No server-side OS push is involved.

---

## 6. Caveats + design decisions worth surfacing

### 6.1 Why a dedicated `notifications` table (not `goa_audit_events`)

The brief said: "create the smallest safe model/migration or use
existing audit/goa event stream only if appropriate." `goa_audit_events`
was tempting (it already exists) but rejected:

* **Mutability:** notifications need a `read_at` write. Audit events
  are immutable + hash-chained — every UPDATE breaks the chain. Reusing
  the table would force either a write-through "shadow row" pattern or
  a denormalized "notification_read_state" sidecar table. Both add
  complexity for marginal benefit.
* **Semantic mismatch:** `severity` (info/success/warning/error) is a
  UI color decision. `risk_level` (LOW/MEDIUM/HIGH/CRITICAL) is a
  governance ranking. Conflating them at the column level pollutes
  either the bell UI ("HIGH severity = ?") or the audit page.
* **Different consumers:** notifications surface in the bell;
  audit events surface in `/governance/audit`. Mixing them would
  require a `kind` discriminator column to filter audit-vs-notif
  reads — adds an index, an enum, and a join cost.

A dedicated table with **9 columns + 2 timestamps** is small enough
that a future PR can extend (add `group_key`, `actions[]`, etc.)
without a destructive migration. The brief said "smallest safe" —
this is.

### 6.2 Production migration: dev-only auto-create

The new `notifications` table is created in dev via
`Base.metadata.create_all` on lifespan startup (`main.py:818`).
**Production uses Alembic** (per `main.py:823` — refuses to boot if
`alembic_version` is empty), and the project's Alembic versions
directory does not currently exist on this branch.

**Action required before prod deploy:** generate an Alembic migration
for the `notifications` table:

```bash
cd backend && alembic revision --autogenerate -m "add notifications table (Phase 11 PR-S2)"
# review the generated file under backend/alembic/versions/
# then `alembic upgrade head` in the Cloud Run start.sh path.
```

This PR does **not** ship the migration because the brief said
"Do not deploy production." When the founder is ready to deploy
Phase 10 + 10b + 10c + 11 PR-S1 + 11 PR-S2, the migration is one
command.

### 6.3 Server-only `emit`, no public POST endpoint with a `type` parameter

`POST /api/v1/notifications/test` always emits `system_info`. There is
**no** public `POST /notifications` that lets a client choose the
`type`. Reason: a client allowed to forge `governance_rejection` rows
could spam the bell or fake high-stakes events.

All other event types come from backend services calling
`NotificationService.emit(...)` directly. PR-S2 ships the emitter
plumbing; **PR-S2-followups will retrofit existing services to call
emit at the right moments** (heartbeat findings, cost-guard breaches,
governance rejections at chat-orchestrator stage 4, runtime disconnect
detection, task completion).

### 6.4 Bell hydration is once-on-mount, not real-time

`Header.tsx` calls `hydrateNotificationsFromBackend(20)` exactly once
when it mounts. Subsequent backend rows that arrive between mount and
unmount are NOT auto-pushed to the bell — the operator would need to
refresh the page to see them.

**Why not SSE?** The brief said "wire it only if low-risk. Otherwise
document next step." Adding an SSE channel for notifications requires
either (a) extending the existing `/chat/messages/stream` SSE with
multiplexing, or (b) standing up a new `/notifications/stream`
endpoint. Both are bigger than PR-S2 scope. **Documented as next
step** — see §7 PR-S2-followup.

In the meantime: the in-memory `addNotification` path (used by
toast-style banners) still works for any UI surface that wants to
push to the bell client-side.

### 6.5 Mark-read endpoint deferred

The brief said: "Add an endpoint to list recent in-app notifications."
+ "Add an endpoint or service helper to emit a test notification."
**No mention of mark-read.** I shipped the model field (`read_at`)
because it's free and avoids a future destructive migration, but I
did NOT ship a `POST /notifications/{id}/read` endpoint.

The bell's existing "Dismiss" + "Clear all" controls are still
in-memory-only. If the founder wants them to PERSIST mark-read state,
that's PR-S2-followup #2.

### 6.6 The unread-only filter is tested but no UI uses it

`GET /notifications?unread_only=true` is tested
(`test_get_list_unread_only_filter`) and works against `read_at IS
NULL`. No UI consumes it yet — the bell just shows the most recent
20 rows. The endpoint is ready for a future "Show only unread" filter
button without further backend work.

### 6.7 Suppressed-by-setting events are NOT audit-logged

When `notif_task_complete=false` blocks an emit, the service returns
the sentinel and writes nothing to the audit ledger. **Reason:**
notification preferences are routine UX choices, not governance
events. Audit-logging every blocked emit would generate one row per
event per user per session — the same spam problem PR-S1's "warn
once per process" pattern was designed to solve.

If the founder wants visibility into "is the gate firing?", the
service emits a debug log (`notification.suppressed_by_setting`) on
every block. `tail -F | grep suppressed_by_setting` answers the
question without polluting the ledger.

---

## 7. Deferred to PR-S2-followups + remaining Phase 11 plan

PR-S2 ships the emitter plumbing. Two natural follow-ups + the rest
of the Phase 11 PR sequence:

| PR | Scope | Estimate |
|---|---|---|
| **PR-S2.1** | Retrofit existing services to call `NotificationService.emit`: heartbeat findings → `heartbeat`; cost_tracker breach → `budget_alert`; chat_orchestrator stage 4 reject → `governance_rejection`; runtimes/test failure → `runtime_disconnect`; task service completion → `task_complete`. Each retrofit is a 3-5 line emit call + a test. | ~3h |
| **PR-S2.2** | `POST /notifications/{id}/read` + `POST /notifications/read-all` + bell wires Dismiss / Clear-all to backend. SSE channel for live push (replaces hydrate-on-mount). | ~3h |
| PR-S3 | Budget vocab unification + wire to `user.settings` (Phase 10b §6 #3) | ~3h |
| PR-S4 | Routing toggle wires (`local_first_routing`, `cost_aware_routing`) | ~4h |
| PR-S5 | Hydrate completeness — extend `hydrateUiFromBackend` to walk all `_UI_PREF_KEYS` | ~1h |
| PR-S6 | `developer_mode` rename to `developer_ui_mode` (migration) | ~30min |
| PR-T1 | Tasks audit emit (Phase 10C-B §10C-D #7) | ~2h |
| PR-T2 | Chat audit completeness (file_attach, export_session) | ~1h |
| PR-P1 | Policy soft-archive (DELETE → `archived=true`) | ~1.5h |
| PR-H1 | Heartbeat config DB persistence (Phase 10C-B "REDESIGN_FLOW" rows) | ~3h |

The audit doc estimated ~21h for the full Phase 11 milestone. PR-S1
took ~1h. PR-S2 took ~1.5h this session. Remaining ≈ ~18h.

---

## 8. Hard rules respected

- ✓ No production deploy.
- ✓ `USE_CONNECTION_REGISTRY_V2=true` not flipped.
- ✓ No `vault --apply`.
- ✓ `vault.py` / `oauth_credentials_store.py` not touched.
- ✓ No secrets read or printed.
- ✓ No external scans.
- ✓ **No external email / SMS / OS push / DM sent.** §5 walks every channel.
- ✓ No broad redesign — exactly the notif_* surface; sound/email/daily-digest correctly stay Coming Soon.
- ✓ No parallel settings store created — gate reads existing `users.settings` JSONB directly.
- ✓ Default behavior preserved when settings unset (fail-open).
- ✓ Smallest safe model — single new table with 9 columns + 2 timestamps.
- ✓ Existing audit/goa event stream evaluated and rejected for documented reasons (§6.1).

End of report.
