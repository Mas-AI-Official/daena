# Phase 10b — Settings Downstream-Read Audit

**Date:** 2026-05-01
**Operator:** Claude Code (Opus 4.7) under founder-direction Phase 10b task
**Branch:** `rebuild-connections-mcp-runtime`
**Companion docs:** `PHASE_10_PRODUCT_INTEGRATION_VERIFICATION.md` §1 (the
methodology correction this audit was created to satisfy),
`UI_ACTION_CONTRACT_MATRIX.md` (Phase 9B, settings cluster).

> **One-liner:** Persistence works end-to-end for every focus setting.
> Three of them (`default_governance_mode`, `default_routing_mode`,
> `default_chat_mode`) are also read by the live pipeline — but
> indirectly, via the chat request body, not by direct DB lookup. The
> remaining nine focus settings (routing toggles, billing values,
> notification + privacy toggles) **persist but no backend consumer
> reads them**. The Phase 9B "FAKE" finding was wrong about the
> *cause* (it was the diff method, not the persistence layer); the
> underlying user concern — "does the system act on what I told it?"
> — is in many cases still correct, just for a different reason.

---

## 0. How to read this document

Each setting row answers seven questions in order:

1. **persists to `users.settings` JSONB:** yes / no
2. **frontend reads it on hydrate (uiStore.hydrateUiFromBackend):** yes / no
3. **frontend uses it in any subsequent action:** yes / no
4. **backend service reads it (any code path):** yes / no
5. **if yes, file:line of the read** — concrete citation
6. **if no, whether it should** — deferred to founder review
7. **recommended fix** — minimum viable wire (or "no-op, document only")

Rows are graded `WIRED`, `PARTIAL`, `STUB`, `DEAD`:

- **WIRED** — the value reaches a consumer that acts on it.
- **PARTIAL** — persistence + hydrate works, but the consumer reads a
  different source (e.g. `Subscription.monthly_budget_usd` instead of
  `user.settings.monthly_budget`). The user's edit has no effect.
- **STUB** — persists + hydrates, but **zero** backend consumer.
- **DEAD** — backend consumer doesn't exist yet (notification emitter,
  privacy enforcer). Setting is on disk waiting for a feature.

---

## 1. Findings table (focus list per Phase 10b brief)

| Setting | Status | Persists | Frontend hydrate | Frontend uses | Backend reads | Reader cite |
|---|---|:-:|:-:|:-:|:-:|---|
| `default_governance_mode` | **WIRED via request body** | ✓ | ✓ uiStore.ts:274 | ✓ chatStore.ts:491 | ✗ direct read | (chat req body) chat_orchestrator.py:497 |
| `default_routing_mode` | **WIRED via request body** | ✓ | ✓ uiStore.ts:273 | ✓ chatStore (routing_mode) | ✗ direct read | (chat req body) chat_orchestrator.py:558 |
| `default_chat_mode` | **WIRED via request body** | ✓ | ✓ uiStore.ts:272 | ✓ chatStore (mode) | ✗ direct read | (chat req body) chat_orchestrator.py:555 |
| `local_first_routing` | **STUB** | ✓ | ✓ uiStore.ts:275 | UI display only | ✗ | — |
| `cost_aware_routing` | **STUB** | ✓ | ✓ uiStore.ts:276 | UI display only | ✗ | — |
| `monthly_budget` | **PARTIAL** (parallel source of truth) | ✓ | uncertain | UI display only | reads `Subscription.monthly_budget_usd` | cost_guard.py:129 |
| `budget_alert_threshold` | **STUB** | ✓ | uncertain | UI display only | ✗ | — |
| `over_budget_action` | **PARTIAL** (BudgetManager hard-codes) | ✓ | uncertain | UI display only | reads `BudgetConfig()` defaults | budget_manager.py:65 |
| `notif_desktop` (+7 other notif_*) | **DEAD** (no emitter) | ✓ | uncertain | UI display only | ✗ | — |
| `memory_generation` | **DEAD** (no enforcer) | ✓ | uncertain | UI display only | ✗ | — |
| `search_past_conversations` | **DEAD** (no enforcer) | ✓ | uncertain | UI display only | ✗ | — |
| `improve_from_usage` | **DEAD** (no consumer) | ✓ | uncertain | UI display only | ✗ | — |
| `location_metadata` | **DEAD** (no consumer) | ✓ | uncertain | UI display only | ✗ | — |
| `storage_local` | **DEAD** (no consumer) | ✓ | uncertain | UI display only | ✗ | — |

**Persistence path** (same for every row): UI calls `persistUiPref(key, value)` →
500 ms debounce → `PUT /api/v1/settings/user` → `_update_user_preferences_impl`
filters against `_UI_PREF_KEYS` whitelist (settings.py:136) → writes to
`users.settings` JSONB → `flag_modified` so SQLAlchemy emits the UPDATE →
subsequent `GET /api/v1/settings/user` returns the merged dict. Verified
live this run: `PUT /settings/user {default_governance_mode:'UNLEASHED'}`
→ 200; subsequent GET returns the new value.

**Frontend hydrate path:** `uiStore.ts:264-291` (`hydrateUiFromBackend`)
walks the response and copies a subset of keys into the in-memory store
+ localStorage cache. Notably this hydrate function only handles 8 of
the 47 settings keys — the billing / notification / privacy keys are
NOT explicitly hydrated, only round-tripped. (See Section 4.)

---

## 2. Per-setting detail

### 2.1 `default_governance_mode` — WIRED via request body

- **Persists:** ✓ (settings.py:138, 162; PUT writes JSONB).
- **Frontend hydrate:** ✓. `uiStore.ts:274` reads `data.default_governance_mode`
  on app load and writes to `useUiStore.governanceMode` + localStorage.
- **Frontend uses it:** ✓. `chatStore.ts:491` puts
  `body.governance_mode = uiState.governanceMode ?? 'GOVERNED'` on every
  chat stream request.
- **Backend reads it:** indirectly. Orchestrator does NOT query
  `user.settings` itself; it consumes the request body's
  `governance_mode` field (chat_orchestrator.py:497 —
  `governance_mode_override or governance_mode_str or app_default`).
- **Should it read direct?** Optional. The current chain works as long
  as the frontend stays the only producer of chat requests. If a future
  CLI / API client posts to `/chat/messages/stream` *without* setting
  `governance_mode`, the orchestrator falls back to the app config
  default, NOT the user's persisted preference.
- **Recommended fix:** **document only** for now. If founder wants
  defense-in-depth, add a one-line read in chat.py at request time:
  `body.governance_mode = body.governance_mode or db_user.settings.get('default_governance_mode')`.
  Kept off this commit because no test surface failed without it.

### 2.2 `default_routing_mode` — WIRED via request body

Same shape as 2.1. Hydrated at uiStore.ts:273; injected at chatStore as
`body.routing_mode`; consumed at chat_orchestrator.py:558.

### 2.3 `default_chat_mode` — WIRED via request body

Same shape as 2.1. Hydrated at uiStore.ts:272; injected at chatStore as
`body.mode`; consumed at chat_orchestrator.py:555 (`action_mode_override`).

### 2.4 `local_first_routing` — STUB

- **Persists:** ✓.
- **Frontend hydrate:** ✓ (uiStore.ts:275).
- **Frontend uses it:** display-only — `SettingsLLM.tsx:204` reads it for
  the toggle's checked state. No call site sends it to the backend.
- **Backend reads it:** **zero hits anywhere in `backend/`.**
- **Should it read?** Yes — the ModelRouter scoring weights document
  locality preference at 0.25 (CLAUDE.md). When the toggle is OFF, that
  weight should drop / flip; when ON, it should be enforced strictly.
- **Recommended fix:** **future work — design a routing-policy
  injection pattern.** Either (a) add `body.local_first_routing` to
  the chat request and have ModelRouter accept a per-request override,
  or (b) cache the user's flag at session-create time and stash on
  `ChatSession`. Both are bigger changes than commit-3's scope. No-op
  for now.

### 2.5 `cost_aware_routing` — STUB

Same shape as 2.4. ModelRouter has a `cost` scoring weight (0.20) but
nothing reads the user toggle. No backend consumer.

### 2.6 `monthly_budget` — PARTIAL (parallel source of truth)

- **Persists in `users.settings.monthly_budget`:** ✓.
- **Backend cost enforcement:** reads from a *different* column —
  `Subscription.monthly_budget_usd` (cost_guard.py:129). The two values
  can drift; the UI toggle changes the JSONB int, the enforcement
  reads the Subscription row.
- **Recommended fix:** **document the dual source-of-truth.** Either
  (a) deprecate `users.settings.monthly_budget` and surface
  `Subscription.monthly_budget_usd` in the SettingsBilling tab, or
  (b) rewrite cost_guard.py to prefer `users.settings.monthly_budget`
  when present and fall back to Subscription. Both are non-trivial.
  No-op for commit-3.

### 2.7 `budget_alert_threshold` — STUB

- **Persists:** ✓.
- **Backend reads:** zero. The 80% default is in the JSON schema
  (settings.py:193) but no code triggers an alert at that threshold.
- **Recommended fix:** future — add an alert emit in
  `cost_tracker.log_usage()` when daily cost crosses
  `budget * threshold / 100`. Requires the notification emitter from
  2.9 to be useful end-to-end.

### 2.8 `over_budget_action` — PARTIAL (BudgetManager hard-codes)

- **Persists in user.settings:** ✓.
- **Backend uses:** `BudgetManager.__init__` constructs a fresh
  `BudgetConfig()` (budget_manager.py:65); the `over_budget_action` it
  consults at decision time (budget_manager.py:95-108) is **always
  the dataclass default `"warn_only"`**, never the user's edit.
- **Pydantic value drift:** the API schema (settings.py:230) accepts
  `"warn|fallback|block"` while BudgetManager's enum is
  `"warn_only|pause_tasks|free_models_only"`. Even if we wired the
  read, the values don't translate.
- **Recommended fix:** **two-step future work.** First, normalise the
  vocabulary (single enum used both at the API surface and inside
  BudgetManager). Then, wire BudgetManager to read from the
  user.settings row (probably at session-init, cached for the
  session's lifetime). No-op for commit-3.

### 2.9 Notification toggles (`notif_*`, 9 keys) — DEAD

- **Persists:** ✓ (settings.py:147-153).
- **Backend reads:** zero.
- **Reason:** the notification emitter doesn't exist yet. There is no
  daemon / task that sends desktop / email / sound notifications.
- **Recommended fix:** **build the emitter as a separate Phase 11
  feature.** Until then the toggles are a UI promise the system
  cannot keep. Either ship a stubbed `NotificationService` that
  reads these flags + warns on use, OR mark the toggles as "Coming
  soon" in the Settings UI. The honesty rule (Rule 17) prefers the
  latter — but that's a UX change, not a backend wire.

### 2.10 Privacy toggles (`memory_generation`, `search_past_conversations`, `improve_from_usage`, `location_metadata`, `storage_local`) — DEAD

- **Persists:** ✓ (settings.py:144-145).
- **Backend reads:** zero.
- **What "privacy" means here is ambiguous in the current code.** None
  of memory_service / chat_orchestrator / cost_tracker / SecurityGate
  inspect any of these flags. The privacy guarantee implied by the
  toggle's label (e.g. "Memory generation: OFF means we never write
  memory rows for this user") is not enforced.
- **Recommended fix:** **highest-priority STUB to wire.** Privacy
  toggles that don't enforce are a trust hazard. Specifically:
  - `memory_generation` should gate `MemoryService.write_memory(...)`.
    A 1-line check on every write site. Tested via "toggle off, send
    a message that would normally produce a T1 entry, verify nothing
    landed."
  - `search_past_conversations` should gate the `MemoryRecall` stage
    (chat_orchestrator.py Stage 7). 1-line check.
  - The other three (`improve_from_usage`, `location_metadata`,
    `storage_local`) need the founder to define the semantic before
    we can wire them. None of those features exist yet.
  - Founder action: confirm the semantic for `memory_generation` and
    `search_past_conversations` and Phase 11 ships a thin
    enforcement PR. Out of scope for commit-3.

---

## 3. Settings outside the focus list, briefly

| Setting | Status | Note |
|---|---|---|
| `dark_mode` | WIRED (UI-only) | persists + hydrates + flips theme; no backend consumer needed. |
| `conversational_mode` | WIRED (UI-only) | hydrates; controls voice TTS auto-play. UI-only. |
| `sidebar_collapsed` | WIRED (UI-only) | layout pref; UI-only. |
| `default_runtime` | UNCLEAR | persists; runtimes.py reads `primary_runtime` (different key). The UI may store one and consult the other — separate audit. |
| `autopilot_active` | UNCLEAR | persists; chat_orchestrator reads autopilot from session/request, not user.settings. |
| `persist_thinking` | UNCLEAR | persists; chat surface may consult; not traced. |
| `auto_read_responses` | WIRED (UI-only) | TTS auto-play flag; UI-only. |
| `debug_mode` | WIRED (UI-only) | in-app debug overlay; no backend consumer. |
| `verbose_logging` | DEAD | persists; no logging-level consumer reads it. |
| `developer_mode` (user-level) | PARTIAL | `users.settings.developer_mode` persists; but the system-level `Settings.developer_mode` (config) is what governs delete vs archive. Two different bits with the same name. |
| `extension_permissions` | WIRED | settings.py + execution_service.py:176 + connections.py:541 — actually consumed. |
| `primary_runtime` | WIRED | settings.py + runtimes.py:131,748 — consumed. |
| `preferred_model` | WIRED | settings.py reads/writes; chat_orchestrator picks it up via session/request. |
| `anti_slop_mode` | UNCLEAR | persists; consumer not traced. |

---

## 4. Other gaps surfaced during this audit

### 4.1 `hydrateUiFromBackend` is incomplete

`uiStore.ts:264-291` only reads 8 of the 47 keys back into the store on
hydrate. The billing / notification / privacy keys round-trip but never
seed the local toggles. So if the user logs in on a fresh device, the
toggles show *defaults*, not the value the user actually saved on
their other device.

This is per-key bug, not a deep one — adding 30 more lines to
`hydrateUiFromBackend` would close it. It also means the Phase 9C-style
question "did this setting persist?" can have surprising answers in the
UI even when the JSONB is correct: the value IS persisted, but the
hydrate function silently dropped it on load.

**Recommended fix:** future — extend hydrate to walk `_UI_PREF_KEYS` and
write each into the store. Out of scope for commit-3 because doing it
right requires per-key Zustand-store wiring and a re-render pass.

### 4.2 Vocabulary mismatch between API and BudgetManager

Mentioned in 2.8. Two different enums for `over_budget_action`:

| Surface | Values |
|---|---|
| `UserPreferencesUpdate` (settings.py:230) | `warn`, `fallback`, `block` |
| `BudgetConfig` dataclass (budget_manager.py:24) | `warn_only`, `pause_tasks`, `free_models_only` |

Wiring one to the other requires a translation table. Risk of subtle
behavior change. Punt to dedicated PR.

### 4.3 `Settings.developer_mode` (system) vs `user.settings.developer_mode` (user)

The system-level `Settings.developer_mode` (config.py) controls the
system-wide archive-vs-hard-delete behavior (per CLAUDE.md rule 2).
The user-level `users.settings.developer_mode` persists but is read
by no one in the backend. Same name, different bit, different scope.

**Recommended fix:** rename the user-level key to
`developer_ui_mode` (it's a UI overlay flag) so the founder UI can't
set a value that *looks* like it should affect the system mode but
doesn't. Light, low-risk; deferred for the Phase 11 sweep.

---

## 5. Section D — high-confidence wires that ship in commit-3

**None.**

Per the Phase 10b brief: "Implement only high-confidence downstream-read
fixes. Do not implement speculative behavior. Only wire settings to
backend services when (a) service already exists, (b) setting meaning
is clear, (c) tests can prove behavior."

Walking each gap:

- **2.1–2.3 governance/routing/chat-mode:** already wired via the
  request body. No-op.
- **2.4 local_first_routing / 2.5 cost_aware_routing:** ModelRouter
  exists, but the routing-policy injection pattern doesn't. Building
  it correctly is a design task, not a one-liner. Risk of regression
  in the live model-routing path. **No-op.**
- **2.6 monthly_budget:** parallel source of truth (Subscription).
  Wiring would require either deprecating one source or writing a
  fall-through. Risk of double-charging or under-charging. **No-op.**
- **2.7 budget_alert_threshold:** consumer doesn't exist. **No-op.**
- **2.8 over_budget_action:** vocabulary mismatch. Wiring without
  translation = silent breakage. **No-op.**
- **2.9 notification toggles:** emitter doesn't exist. **No-op.**
- **2.10 privacy toggles:** highest-priority, but each one needs the
  founder to define the semantic before we can write a meaningful
  test. **No-op until founder-aligned spec.**

This is the audit's headline conclusion: **the gap is real, and
small enough to triage in a single Phase 11 sprint, but big enough
that one-shot wiring in this commit would risk shipping wrong
behavior.**

---

## 6. Phase 11 sprint proposal (out of scope, founder-decision)

If the founder wants to close these gaps, a clean PR sequence:

1. **PR-S1 (privacy enforcement):** wire `memory_generation` to
   gate `MemoryService.write_memory` and `search_past_conversations`
   to gate `MemoryRecall` Stage 7. ~2 hours including tests.
2. **PR-S2 (notification stub + flags):** ship a `NotificationService`
   stub that reads the `notif_*` flags and emits to a single channel
   (in-app toast banner). Marks all "Coming soon" labels as live.
   ~3 hours.
3. **PR-S3 (budget vocabulary):** unify `over_budget_action` enum
   between API + BudgetManager. Wire `BudgetManager` to load
   `over_budget_action` + `monthly_budget` from `user.settings`. Add
   regression test. ~3 hours.
4. **PR-S4 (routing toggles):** add per-request `local_first_routing`
   + `cost_aware_routing` overrides on chat request body, plumbed
   through ModelRouter. ~4 hours, more if regression test reveals
   downstream weight conflicts.
5. **PR-S5 (hydrate completeness):** extend `hydrateUiFromBackend` to
   walk `_UI_PREF_KEYS`. 1 hour.
6. **PR-S6 (dual-name cleanup):** rename
   `users.settings.developer_mode` to `developer_ui_mode` to remove
   the system-vs-user collision. 30 min + migration.

Total: ~14 hours. Should be a single Phase 11 milestone, not five
parallel commits.

---

## 7. Boundaries respected

- No production deploy.
- No `USE_CONNECTION_REGISTRY_V2` flip.
- No `vault --apply`.
- No vault.py / oauth_credentials_store.py touched.
- No secrets read or printed.
- No external scans.
- No backend services modified for Section D — this audit is doc-only.

End of audit.
