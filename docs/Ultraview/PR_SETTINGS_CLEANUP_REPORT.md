# PR-SETTINGS-CLEANUP Report

**Date:** 2026-05-02
**Branch:** `rebuild-connections-mcp-runtime`
**Parent commit:** `7dd85ba` (PR-HB-DAEMON-WIRE)
**Closes:** Atlas I.4 + I.5 (Coming Soon labels + dual-source-of-truth);
DAENA_CANONICALIZATION_PLAN.md §4 (Settings reduction); Phase 10C-D
items 1, 4, 5, 7, 8 (the cleanup that was deferred from Phase 10C-D
to avoid scope-creep into the heartbeat / privacy enforcement PRs).
**Scope:** Frontend UI only. Zero backend code modified. Zero migrations.
Zero tests run on backend (no backend code changed). No backend wiring.

---

## What changed and why

PR-SETTINGS-CLEANUP is a five-file UI cleanup that makes every visible
control honest about its backend state, relocates duplicated editors
to their canonical home (AccountPage), and introduces a Normal /
Advanced grouping so the default Settings surface stays simple. The
brief is explicit that this is NOT a wiring PR; backend consumer
work for the dead toggles is queued separately (PR-NOTIF-FANOUT,
PR-S3, PR-S4).

### Pre-edit verification (audit was stale on privacy)

`PHASE_10B_SETTINGS_DOWNSTREAM_READ_AUDIT.md` flagged
`memory_generation` and `search_past_conversations` as DEAD with no
backend enforcer. Direct grep against current code shows the audit
is OUT OF DATE and PR-S1 has shipped:

- `backend/app/services/memory.py:138` reads
  `settings.get("memory_generation")` and refuses writes when the
  flag is False, emitting a `privacy.memory_write_blocked` audit
  row once per process per user (`memory.py:172`).
- `backend/app/services/chat_orchestrator.py:1628` reads
  `_u_settings.get("search_past_conversations")` and skips Stage 6
  recall when False (`chat_orchestrator.py:1648` audit).

Both privacy toggles ARE truly enforced today. The current "Enforced
by backend" labels on those two are kept; per the brief no other
privacy toggle gets that pill.

`notif_heartbeat` and `notif_runtime_disconnect` are a different
case: `NotificationService` honors the gate (when the flag is False
it skips writing the row), but no service ever emits with those event
types (Backlog P1-03). The previous single "Enforced by backend"
badge applied uniformly to all five per-event toggles overstated the
two with no source. Each of those rows now carries a per-row "Source
pending" badge so the operator can tell at a glance which events
actually fire.

### Files changed (5)

```
M frontend/src/pages/SettingsPage.tsx                +146 net
M frontend/src/pages/settings/SettingsGeneral.tsx     -36 net (editor relocated)
M frontend/src/pages/settings/SettingsDeveloper.tsx   +9 net
M frontend/src/pages/settings/SettingsHeartbeat.tsx   +14 net (tooltips)
M frontend/src/pages/settings/SettingsNotifications.tsx +28 net (per-row honesty)
```

No backend code touched. No new files. No deletions. The three
protected files (Rule 18: `vault_adapter.py`, `vault_migration.py`,
`oauth_credentials_store.py`) all untouched.

---

## Edit-by-edit detail

### 1. `frontend/src/pages/SettingsPage.tsx`

Introduced Normal vs Advanced grouping. The CATEGORIES array now
carries an `advanced: boolean` per entry; rendering buckets the 13
tabs into seven Normal (General / Memory / Privacy & Data /
Notifications / Voice / Billing & Usage / About) and six Advanced
(LLM Providers / Governance / Models & Runtimes / Daena Heartbeat /
Developer / Shortcuts).

A "Show advanced" checkbox in the sidebar persists to localStorage
under the key `daena.settings.show_advanced`. Default is OFF. The
sidebar's existing search filter is preserved and operates over the
visible-by-group set so "Filter..." still works exactly as before.

**Deep-link safety net:** if the operator visits `/settings/heartbeat`
(or any advanced tab) directly while `showAdvanced=false`, the toggle
auto-flips on. The user is never trapped on a hidden route with an
empty sidebar. Implemented in a `useEffect` keyed on
`current.advanced`.

### 2. `frontend/src/pages/settings/SettingsGeneral.tsx`

Removed the inline `display_name` editor (Input + Save Changes
button). Replaced with a read-only summary card (display name, email,
role) plus a "Manage in Account" link that navigates to `/account`.

This closes the Atlas F.2 dual-source-of-truth (the same
`display_name` field had two write surfaces, one on Settings >
General and one on AccountDetails, both calling
`PUT /settings/user`). AccountPage is now the single canonical write
site.

Side-effect: removed the `useEffect` that fetched `display_name` from
`/settings/user` (no longer needed since the summary uses the
authStore's `user.display_name` which is hydrated at login and kept
fresh by the AccountDetails edit flow).

### 3. `frontend/src/pages/settings/SettingsDeveloper.tsx`

Replaced the mock API Keys block (which had a fake masked
`dk_...` placeholder + a Coming-Soon "Generate New Key" button) with
a card containing a "Manage in Account" link. AccountApiKeys
(`POST /api-keys`, `GET /api-keys`, `DELETE /api-keys/{id}`) is the
canonical CRUD surface.

Webhooks block kept (no consumer exists in the backend yet per Atlas
I.3) but moved behind a "Coming soon" badge:

- Inline `<Badge variant="warning">Coming soon</Badge>` next to the
  card heading.
- Honest helper sentence: "Webhook dispatcher pending. Saved values
  would not fire today."
- Form fields wrapped in `opacity-60 pointer-events-none
  select-none aria-disabled` so the operator cannot accidentally
  type into a non-functional URL field.
- Save button now `disabled` (not just opacity).

The existing `Environment` readout is preserved unchanged. The
"DEVELOPER_MODE (system)" line is correctly labeled as system per
the long-standing comment; no rename needed (per brief item 5: "if
it does not control backend deletion/unsafe power" - the system
flag DOES control the archive-vs-hard-delete decision per CLAUDE.md
Rule 2, so the rename is not applied).

### 4. `frontend/src/pages/settings/SettingsHeartbeat.tsx`

Added `title=` tooltips to every interval button, both active-hours
inputs, every check-toggle row, the cost-guard card heading, and
both cost-guard inputs. Each tooltip explains the daemon-memory-only
persistence + restart reset behaviour. The existing top-of-card
"Daemon-memory only" amber banner is kept (the founder's brief
explicitly required keeping it).

The check-toggle tooltip references PR-HB-DAEMON-WIRE so a future
contributor who flips a check from disabled-by-default to
enabled-by-default knows there is an explicit founder-approval bar.

No semantic change. The interval / active-hours / check toggles
still write to daemon memory only; persistence to a `heartbeat_config`
DB row remains the future PR-H1.

### 5. `frontend/src/pages/settings/SettingsNotifications.tsx`

Three changes inside the per-event toggle group (rendered when the
desktop master toggle is on):

- Added a `title=` tooltip on the group container that distinguishes
  emitter-real toggles from gate-only toggles, citing Backlog P1-03
  + PR-NOTIF-FANOUT.
- Added per-row `title=` tooltips citing the specific emitter for
  each row (or the missing-emitter fact for heartbeat /
  runtime_disconnect).
- Added per-row `<Badge variant="warning">Source pending</Badge>`
  badges next to the labels for "Daena Heartbeat findings" and
  "Runtime disconnection" so the operator can see at a glance which
  events actually fire.

The single group-level "Enforced by backend" green badge stays at
the top because all five toggles ARE consumed by NotificationService
gate logic; the per-row "Source pending" badges narrow the claim to
the two with no upstream emitter, without removing the truthful
gate-level enforcement claim.

The other notification rows are unchanged: notif_sound,
notif_email, notif_daily_digest stay disabled with their existing
"Coming soon" labels (no audio pipeline / no SMTP / no scheduler-
driven digest job).

---

## Verification

### Frontend type check

```
$ npx tsc --noEmit
(no output -- clean)
```

### Em-dash hygiene (project CLAUDE.md Rule 12)

Per-file additions check via `git diff <file> | grep "^+" | grep -c "—"`:

```
SettingsPage.tsx                  -> +0
SettingsGeneral.tsx               -> +0  (had 2 placeholder em dashes for empty
                                          values; replaced with "-" hyphens
                                          mid-PR)
SettingsDeveloper.tsx             -> +0
SettingsHeartbeat.tsx             -> +0
SettingsNotifications.tsx         -> +0
```

Zero em dashes introduced.

### Tests run

Per the brief: "frontend npx tsc --noEmit; run any existing settings
tests if present; no backend tests unless backend code changes."

- `npx tsc --noEmit` -> clean.
- No existing settings unit tests in the frontend (verified via
  `find frontend/src -name "*test*settings*"`); nothing to run.
- No backend code changed; no backend tests run.

---

## Hard-rule check

| Hard rule | Honored |
|---|---|
| No production deploy | Yes (UI-only) |
| No `USE_CONNECTION_REGISTRY_V2` flip | Yes (flag not touched) |
| No `vault --apply` | Yes (vault not invoked) |
| No file deletions | Yes (zero deletions) |
| No secrets read or printed | Yes |
| No external scans | Yes |
| No external messages | Yes |
| Skills, Connections V1/V2, Scan UX, Workstream spine NOT modified | Yes (all out of scope per brief) |
| No speculative backend wiring | Yes (zero backend code touched) |
| Em dashes in new content (project CLAUDE.md Rule 12) | Yes (zero introduced) |

---

## Answers to brief's report questions

### Controls disabled (no functional change; existing or strengthened)

| Control | Before | After |
|---|---|---|
| `notif_sound` | disabled + Coming Soon | unchanged |
| `notif_email` | disabled (email not configured) | unchanged |
| `notif_daily_digest` | disabled (no scheduler) | unchanged |
| `improve_from_usage` | disabled + Coming Soon | unchanged |
| `location_metadata` | disabled + Coming Soon | unchanged |
| `debug_mode`, `verbose_logging` (Developer tab) | disabled + Coming Soon | unchanged |
| Webhooks URL field + checkboxes + Save | enabled (mock) | now `disabled` + wrapped in `pointer-events-none` so the form is honestly inert |

### Controls renamed

None in this PR. Per brief item 5, "Developer Mode" is not renamed
because the SYSTEM `DEVELOPER_MODE` (read-only env display)
correctly controls the system-wide archive-vs-hard-delete behaviour
per CLAUDE.md Rule 2 (it DOES control unsafe power, so the rename
condition does not trigger). The user-level
`users.settings.developer_mode` JSONB key exists in the schema but
is not surfaced as a toggle on any settings tab today, so there is
nothing user-facing to rename. The schema rename to
`developer_ui_mode` remains the future PR-S6.

### Controls moved or linked to Account

| Control | Old location | New canonical location | Old surface now |
|---|---|---|---|
| `display_name` editor + Save Changes | `SettingsGeneral.tsx` Profile card (inline `<Input>` + `<Button>`) | `/account` (`AccountDetails.tsx`) | Read-only summary + "Manage in Account" link |
| API Keys (mock display + Coming-Soon button) | `SettingsDeveloper.tsx` API Keys card | `/account` (`AccountApiKeys.tsx` - real CRUD against `/api-keys`) | One-line description + "Manage in Account" link |

### Controls labelled "Wiring pending" / "Source pending" / "Coming soon"

| Control | Label | Reason |
|---|---|---|
| `local_first_routing` | "Wiring pending" (pre-existing) | STUB; ModelRouter does not read it. PR-S4. |
| `cost_aware_routing` | "Wiring pending" (pre-existing) | STUB; same. PR-S4. |
| `monthly_budget`, `budget_alert_threshold`, `over_budget_action` | "Wiring pending" banner (pre-existing) | PARTIAL / STUB; cost-guard reads `Subscription.monthly_budget_usd`, BudgetManager hard-codes the over-budget enum. PR-S3. |
| `notif_heartbeat` | NEW per-row "Source pending" badge | Gate honored, no service emits with type=heartbeat. Backlog P1-03; PR-NOTIF-FANOUT. |
| `notif_runtime_disconnect` | NEW per-row "Source pending" badge | Same. PR-NOTIF-FANOUT. |
| Webhooks card | NEW "Coming soon" badge | Atlas I.3: no webhook dispatcher exists in backend. |

### Controls still fully working (truth surface)

| Control | Backing |
|---|---|
| Privacy `memory_generation` toggle | Real - `MemoryService` refuses writes when False (`memory.py:138`). Audit row on first block per process per user. |
| Privacy `search_past_conversations` toggle | Real - chat orchestrator skips Stage 6 recall when False (`chat_orchestrator.py:1628`). Audit row. |
| Notification master `notif_desktop` | Real - browser permission gate. |
| `notif_task_complete` | Real - chat_orchestrator emits on Workstream / task COMPLETE (PR-S2). |
| `notif_budget_alert` | Real - cost_guard emits on threshold cross (PR-S2.1). |
| `notif_gov_reject` | Real - governance / SecurityGate emits on BLOCKED (PR-S2). |
| Send Test button | Real - POST /notifications/test creates a system_info row, pushes into uiStore bell, fires OS notification when permission granted. |
| Heartbeat Pause / Resume / Stop / Run-now | Real - hits `/heartbeat/{pause,resume,stop,run-once}` against the now-auto-started daemon (PR-HB-DAEMON-WIRE). |
| Default chat mode / routing mode | Real - WIRED via request body (Phase 10b §2.1-2.3). |
| Default governance mode | Real - WIRED via request body. |
| Dark mode toggle | Real - UI store. |
| AGI mode (Autopilot) toggle | Real - autopilot store + backend health gate. |
| Persist Thinking Process toggle | Real - chat surface respects. |
| Voice provider settings | Unchanged (out of scope of this PR). |

### Tests run

- `npx tsc --noEmit` -> clean (no output).
- No existing frontend settings tests; nothing to run.

### Remaining settings debt (not in this PR)

These are tracked but explicitly OUT OF SCOPE per the brief
("UI cleanup, not backend rewiring"):

1. **PR-S1 follow-up** -- The two enforced privacy toggles (verified
   shipped today) still need expanded coverage for
   `improve_from_usage`, `location_metadata`, and the cloud variant
   of `storage_local`. Each requires a founder-defined semantic
   before a meaningful enforcer can be written.
2. **PR-S3 (budget vocabulary)** -- Unify the `over_budget_action`
   enum between `UserPreferencesUpdate` API and `BudgetConfig`
   dataclass; wire `BudgetManager` to read `monthly_budget` from
   `user.settings`. Closes the dual-source-of-truth.
3. **PR-S4 (routing toggles)** -- Plumb `local_first_routing` +
   `cost_aware_routing` through `ModelRouter` per-request override.
4. **PR-S5 (hydrate completeness)** -- Extend
   `uiStore.hydrateUiFromBackend` from 8 keys to all 47
   `_UI_PREF_KEYS`.
5. **PR-S6 (developer_mode rename)** -- Rename
   `users.settings.developer_mode` to `developer_ui_mode` in the
   JSONB schema + API + UI references. Migration required.
6. **PR-NOTIF-FANOUT** -- Add real per-tenant emitters for
   `notif_heartbeat` (per-tenant heartbeat schedule) and
   `notif_runtime_disconnect` (provider-to-tenant mapping). Closes
   Backlog P1-03 and lets the two "Source pending" badges drop.
7. **PR-H1 (heartbeat config persistence)** -- Move heartbeat config
   from daemon memory to `user.settings.heartbeat_config` so the
   tooltips can drop the "restart resets" warning.
8. **Webhooks dispatcher** -- Build the webhook subsystem (event
   dispatcher + delivery worker + retry policy) so the Webhooks card
   in SettingsDeveloper can drop its Coming-Soon badge and become
   a real configuration surface.

Effort estimate (per Backlog + PRD): ~21 hours total across PR-S1
through PR-S6 + ~6 hours for PR-NOTIF-FANOUT + ~3 hours for PR-H1.
A single Phase 11 sprint can close items 2-5 cleanly; 1, 6, 7, 8
each justify their own ticket.

---

## What this PR does NOT do

- Does NOT wire any backend consumer. The brief explicitly said
  "this is mostly UI cleanup, not backend rewiring."
- Does NOT modify the Skills page or `skill_refinery` (founder
  amendment to canonicalization plan: Skills is first-class).
- Does NOT modify the Connections V1/V2 split (PR 3 in the plan).
- Does NOT modify any Scan UX surface (PR 4 in the plan).
- Does NOT introduce the Workstream spine (PR 5 in the plan).
- Does NOT delete any setting from the schema. Every dead toggle is
  labeled honestly so a future PR can either ship the consumer or
  delete the schema field with a migration.
- Does NOT touch the global `~/.claude/CLAUDE.md` or the project
  `CLAUDE.md`.
- Does NOT modify any test file.

---

## Caveats

1. **Show-advanced state is per-browser, not per-user.** It uses
   `localStorage`, not `users.settings`. Trade-off: persisting to
   the JSONB row would require a backend round-trip on every load
   and would conflict with the brief's "no backend rewiring" rule.
   localStorage is honest about its scope (per-browser preference).
2. **Notifications group "Enforced by backend" badge stays.** The
   five per-event toggles ARE all consumed by NotificationService
   gate logic, so the group-level claim is true. The narrowing of
   "which two have no source" is communicated via the per-row
   "Source pending" badges introduced in this PR. A future PR-NOTIF-
   FANOUT removes the per-row badges once real emitters land.
3. **Webhooks Save button is `disabled` AND `pointer-events-none`,
   redundantly.** The `disabled` attribute alone would suffice but
   the wrapping div pattern (already used in this codebase for the
   AccountApiKeys "just-created key" reveal flow) is the
   conventional belt-and-suspenders. Net cost: zero render change;
   net benefit: matches the existing codebase pattern.
4. **The `useEffect` removal from SettingsGeneral could leave a
   subtle stale-display window** (~50ms) immediately after a name
   change on AccountDetails before the authStore propagates. In
   practice authStore updates the user object synchronously after
   the PUT response, so the next render of SettingsGeneral
   (triggered by the Settings tab navigation) reads the fresh value.
   Verified by reading authStore behavior.

---

## Next PR recommendation

Per the canonicalization plan §8 sequence, **PR 3 (Connections truth
cleanup)** is next: V1 connection panels collapse behind "Legacy /
Advanced" toggle, V2 stays the dev-canonical truth surface. Effort
~3-4 hours, MED risk. Pre-requisite (~1 hour): implement
`connection_v2/probe.py:59` `NotImplementedError` so V2 can return
honest "probe unavailable" status instead of the stub.

The complementary follow-up to this PR is **PR-S1-EXTENSION** (~2h):
write three new privacy enforcers (`improve_from_usage`,
`location_metadata`, cloud-variant `storage_local`) IF the founder
can define their semantics. Until then those three stay honestly
disabled with Coming-Soon labels.

---

**End of report.**
