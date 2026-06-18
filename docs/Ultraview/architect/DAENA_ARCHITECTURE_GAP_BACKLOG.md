# Daena Architecture Gap Backlog

**Date:** 2026-05-01 (updated 2026-05-02 by PR-DOC-DRIFT-FIX)
**Author:** Claude Code (Opus 4.7) under founder-direction
**Companion docs:** `DAENA_ARCHITECTURE_ATLAS.md`,
`DAENA_SYSTEM_GRAPH.mmd`, `DAENA_EXECUTION_SPINE_PRD.md`,
`DAENA_BACKEND_BLINDSPOT_INVENTORY.md`,
`DAENA_BACKEND_MODULE_GRAPH.mmd`
**Stance:** documentation-only. No code modified.

> **Convention.** P0 = trust/safety (ship blockers). P1 = broken
> execution (real loops not closed). P2 = duplicate / complexity
> (cleanup). P3 = polish. Each gap lists: file/module, evidence,
> fix strategy, estimated effort (founder pace), dependency, blocks
> local demo (Y/N), blocks cloud demo (Y/N).

> **2026-05-02 reconciliation update (PR-DOC-DRIFT-FIX).** Following
> the Backend Blind-Spot Inventory sweep on 2026-05-01, the following
> entries are reclassified or marked closed by PRs that landed
> 2026-05-01 / 2026-05-02:
>
> - **P0-01 (audit chain not validated):** CLOSED by commit `2492b82`
>   (PR-AUDIT-VERIFY PR #1, GET `/audit/verify?deep=true` with
>   structural + content recompute) and commit `07aaede`
>   (PR-AUDIT-VERIFY PR #2, POST `/audit/verify` with rich diagnostic
>   `{first_break_index, row_id, kind, previous_hash, expected_hash,
>   actual_hash}`).
> - **P0-04 (Dream Engine "UNSCHEDULED"):** RECLASSIFIED. Ground-truth
>   inspection found the Dream Engine IS scheduled by APScheduler
>   every 15 minutes via the lifespan deferred-init hook. The actual
>   gap is operator visibility, not scheduling. Downgraded below to
>   P2 (UI-surface gap, not safety blocker).
> - **NEW P0-09 (HeartbeatDaemon not auto-started):** the real Rule 17
>   violation in this neighborhood. UI controls in
>   `SettingsHeartbeat.tsx` and `/heartbeat/start|pause|stop` are
>   live, but `main.py.lifespan` never starts `HeartbeatDaemon` so
>   the controls are decorative until an operator manually invokes
>   them. Inserted below.
> - **Hallucination of Control:** PR-AUDIT-VERIFY PR #2 (commit
>   `07aaede`) closed the Obsidian face of this risk class by
>   gating the "available" badge to a real `Path.glob("**/*.md")`
>   probe pass. Remaining surfaces enumerated in P2-07.

---

## P0 — Trust / Safety (ship blockers)

### ~~P0-01~~ CLOSED Audit hash chain not validated on read

> **CLOSED 2026-05-02 (PR-DOC-DRIFT-FIX).** Resolved by:
>
> - **Commit `2492b82`** (PR-AUDIT-VERIFY PR #1):
>   `GET /api/v1/governance/audit/verify?deep=true` recomputes
>   SHA-256 from each row's payload and compares to the stored
>   `entry_hash`, catching content tamper that the structural walker
>   misses. Returns `{valid, total_entries, first_broken_id,
>   first_corrupt_id}`.
> - **Commit `07aaede`** (PR-AUDIT-VERIFY PR #2):
>   `POST /api/v1/governance/audit/verify` returns rich diagnostic
>   `{verified, total_entries, tenant_id, first_break_index,
>   first_break: {row_id, kind: structural|content, previous_hash,
>   expected_hash, actual_hash}}`. Hard rule pinned by
>   `test_post_verify_does_not_mutate_audit_rows`: verify call is
>   provably read-only.
>
> Outstanding follow-ups (separate PRs, not blocking):
>
> - **PR-AUDIT-VERIFY-CRON.** Nightly cron that auto-verifies and
>   writes an `audit.chain_verified` audit row. Effort ~1h.
> - **PR-AUDIT-DELETE-GATE.** Gate the `DELETE /audit/{id}` route
>   (if it exists) behind founder + reason. Effort ~1h. Verify
>   first whether such a route is actually mounted; the audit table
>   is append-only by design.
>
> Original entry text preserved below for audit trail.

- **File/Module:** `backend/app/services/audit.py:74-80` (verify
  helper exists), `backend/app/api/v1/governance.py` (no verify
  endpoint).
- **Evidence:** `audit.py` computes `entry_hash = sha256(actor_id +
  action_type + result + prev_hash + timestamp)` per row, but no
  read-time verification surface. Operators can `DELETE` audit rows
  via `/governance/audit` UI; chain breaks silently. Hard Law #9
  ("Audit Trail Integrity") is therefore unverified.
- **Fix strategy:** add `POST /api/v1/governance/audit/verify`
  that walks the chain end-to-end per tenant and returns
  `{verified, last_break_at, last_break_index}`. Add a nightly cron
  that runs the verify and writes a `audit.chain_verified` audit
  row. Gate the audit-row delete operation behind founder + reason.
- **Effort:** 2h (PR-AUDIT-VERIFY in Atlas H + PRD §14).
- **Depends on:** none.
- **Blocks local demo?** N. **Blocks cloud demo?** Y (any
  governance claim depends on this).

### P0-02 — RAG advertised but NOT implemented

- **File/Module:** none (no service file). `frontend/src/pages/...
  /Settings/Memory` shows a "RAG status" badge.
  `MEMORY_RAG_OBSIDIAN_SYNC_REPORT.md` confirms `/api/v1/memory/status`
  returned `rag: not configured`.
- **Evidence:** Memory page implies retrieval works for
  Claude/Codex/Gemini context export. No service file exists. UI
  is a Rule 17 violation.
- **Fix strategy:** add `GET /api/v1/memory/retrieval-test` that
  attempts a real retrieval and returns
  `{configured, reachable, last_test_at, document_count, error}`.
  Until first real hit, the UI badge says "Not Configured" + links
  to a docs page that explains what RAG does and why it isn't on
  yet. NEVER advertise "online."
- **Effort:** 1h (PR-RAG-HONEST in PRD §14).
- **Depends on:** none.
- **Blocks local demo?** Y (operator may try it). **Blocks cloud
  demo?** Y.

### P0-03 — `learning_service` patterns wiped on restart (Rule 17)

- **File/Module:** `backend/app/services/learning_service.py`
  (`_active: dict`, `_history: list` IN-MEMORY ONLY).
- **Evidence:** Per data-layer agent: "tracks but does not persist.
  Patterns are wiped on restart. Phases learned but never applied."
  Per CLAUDE.md Rule 17: "no advertised real-time without an SSE
  channel" + "in-memory registries must hydrate from DB on startup."
- **Fix strategy:** new `learned_patterns` table mirroring the
  `LearnedPattern` dataclass. `LearningService.track_outcome()`
  writes synchronously. Hydrate `_active` + `_history` from DB on
  startup (same pattern as `MCPRegistry.hydrate_from_db` from ADR-001
  example).
- **Effort:** 2h (PR-LEARN-01).
- **Depends on:** none.
- **Blocks local demo?** N. **Blocks cloud demo?** Y (any
  self-improvement claim collapses without persistence).

### ~~P0-04~~ -> P2-DREAM-UI Dream Engine scheduled but no UI surface

> **RECLASSIFIED 2026-05-02 (PR-DOC-DRIFT-FIX).** Original entry below
> claimed Dream Engine was unscheduled. Backend Blind-Spot Inventory
> ground-truth inspection (2026-05-01) found this is incorrect:
> `main.py` deferred init schedules `dream_engine` via APScheduler at
> a 15-minute interval (verified by Phase D agent and direct read of
> `main.py` lifespan). The remaining gap is purely UI: there is no
> operator-visible "last Dream cycle: X minutes ago" surface. This is
> a P2 visibility gap, not a P0 safety blocker.

- **File/Module:** `backend/app/services/dream_engine.py` (live),
  scheduled in `backend/app/main.py` lifespan deferred-init.
- **Evidence (corrected):** Dream Engine is scheduled and runs every
  15 minutes. No frontend page renders the last-run-time, total
  cycles, or per-cycle merge/promote/decay summary. Operators have
  no way to confirm it is actually consolidating without reading
  logs. `GET /api/v1/memory/dream/status` exists and returns
  `{last_run, total_cycles, is_running}` but is not surfaced in UI.
- **Fix strategy:** add a Dream Engine card to `SettingsMemory.tsx`
  (or a dedicated "Memory > Dreams" page) reading
  `/memory/dream/status` on mount and on a 60s tick. Show last run
  relative time, total cycles since boot, last DreamReport summary
  (merged/promoted/decayed counts).
- **Effort:** 1.5h (UI-only, no backend change needed).
- **Depends on:** none.
- **Blocks local demo?** N. **Blocks cloud demo?** N (consolidation
  is happening; only operator visibility is missing).

> Original P0-04 entry text preserved for audit trail:
>
> > Dream Engine defined but UNSCHEDULED.
> > File/Module: backend/app/services/dream_engine.py
> > (~200 lines, no scheduler entry, no API endpoint, no startup hook).
> > Evidence: Per data-layer agent: "DEFINED but INACTIVE.
> > Conceptually sound. Zero operational overhead until activated."
> > Highest-leverage intelligence layer that is currently inert.
> > Fix strategy: schedule a nightly Dream cycle (default 02:00
> > local; configurable via user.settings). Add DreamReport +
> > DreamAction tables. Emit per-cycle audit rows. Reuse Skill
> > Refinery circuit breaker.
> > Effort: 3h. Depends on: P0-03. Blocks local: N. Blocks cloud: Y.
>
> The original Phase A audit reported "no scheduler entry" because
> the agent did not trace the deferred-init path in `main.py` to the
> APScheduler binding. The binding is real and active; the
> reclassification reflects ground truth.

### P0-05 — `learning_service` REFLECT writes user-content (PR-S1 conflict)

- **File/Module:** `backend/app/services/cognition/ooda_engine.py`
  REFLECT phase + `backend/app/services/learning_service.py`.
- **Evidence:** PR-S1 §6.1 specified that agent experiences are
  TENANT-scoped and excluded from `users.settings.memory_generation`
  privacy gate. But OODA REFLECT currently calls `MemoryService.store()`
  (user-content path, gated) instead of a dedicated
  `store_experience()` (tenant-scoped, ungated). Result: a user
  who toggles `memory_generation=false` silently kills agent
  learning.
- **Fix strategy:** wire `store_experience()` (already defined per
  PR-S1 audit) into OODA REFLECT and into LearningService persist.
  These writes use the AGENT_DECISION/SKILL_OUTCOME/PATTERN_LEARNED/
  APPROACH_FAILED content types and skip the per-user privacy gate
  per PR-S1 §6.1.
- **Effort:** 1.5h (part of PR-LEARN-01).
- **Depends on:** P0-03.
- **Blocks local demo?** N. **Blocks cloud demo?** Y (privacy +
  learning interact incorrectly).

### P0-06 — Laevateinn knowledge graph NOT tenant-isolated

- **File/Module:** `backend/app/services/laevateinn/knowledge_graph.py`
  (local SQLite, single global instance).
- **Evidence:** Per data-layer agent: "Self-contained aiosqlite DB.
  No cross-tenant sharing." Currently fine because local-first
  single-founder; but it's a critical privacy gap if cloud multi-
  tenant resumes.
- **Fix strategy:** scope KG entries by `tenant_id` column +
  enforce on every insert / read. Add a `purge_tenant(tenant_id)`
  helper for tenant deletion. Block cloud resume until fixed.
- **Effort:** 4h.
- **Depends on:** none.
- **Blocks local demo?** N. **Blocks cloud demo?** **Y — HARD
  BLOCKER for cloud.**

### P0-07 — `tool_augmented.py` web_search stub (fake research evidence)

- **File/Module:** `backend/app/services/laevateinn/tool_augmented.py`
  (multiple `web_search_stub` references per Duplicates report).
- **Evidence:** SecurityGate / scan_workflow can produce strategic
  reports that cite "web search results" which are stub returns.
  Founder-level reports presented to clients could carry stub-
  generated citations.
- **Fix strategy:** label as offline / stub at function level;
  reject any caller that reaches the stub from an in-flight T3+
  scan; OR replace with approved research provider (Perplexity API
  with cited URLs). NEVER ship reports that pass off stub data as
  real research.
- **Effort:** 2h to label + fail-closed; 6h to wire real Perplexity.
- **Depends on:** none.
- **Blocks local demo?** Only if scan flow is demoed.
  **Blocks cloud demo?** Y (any T3+ scan).

### P0-08 — EVILBOB_KEY in plaintext env var

- **File/Module:** `backend/app/services/security/evilbob_mode.py`,
  `.env` files.
- **Evidence:** Per intelligence-layer agent: "EVILBOB_KEY stored
  in environment (plaintext risk if env leaked). Cloud detection
  via env vars may be spoofable."
- **Fix strategy:** rotate EVILBOB_KEY into vault (envelope-
  encrypted via DAENA_KEK). Replace env-var compare with vault
  lookup. Strengthen cloud-detection beyond env-var sniffing
  (e.g. metadata server probe).
- **Effort:** 3h.
- **Depends on:** vault is functional (it is, post-Phase 4a).
- **Blocks local demo?** N (founder-only feature).
  **Blocks cloud demo?** N (cloud already refuses evilbob).

### P0-09 — HeartbeatDaemon implemented but not auto-started (Rule 17 violation)

> **Added 2026-05-02 (PR-DOC-DRIFT-FIX).** Identified by Backend
> Blind-Spot Inventory §13 #2 as the true Rule 17 violation that the
> Atlas previously misattributed to Dream Engine. This is the entry
> the brief asked us to add or confirm.

- **File/Module:** `backend/app/services/heartbeat/heartbeat_daemon.py`
  (~650 LOC, real implementation), `backend/app/api/v1/heartbeat.py`
  (POST `/heartbeat/start|pause|stop` routes mounted),
  `frontend/src/pages/settings/SettingsHeartbeat.tsx` (Pause / Resume
  / Stop controls rendered), `backend/app/main.py` lifespan
  (HeartbeatDaemon NEVER started).
- **Evidence (verified by main thread spot-check 2026-05-01):**
  `grep "heartbeat_daemon|HeartbeatDaemon" backend/app/main.py`
  returns NO matches. Phase D agent classification: VISIBLE_IN_UI_BUT
  _NEVER_STARTED. The cron scheduler and background queue are both
  started in deferred init but the heartbeat daemon is not. Operator
  clicking Pause expects effect but the daemon is not running, so
  the action is a no-op against an absent process.
- **Why this violates Rule 17:** "Honesty + Persistence + Visibility"
  (CLAUDE.md project rule 17, locked 2026-04-29 via ADR-001) requires
  every UI element to advertise a real capability backed by
  persistent state. Pause / Resume / Stop controls advertise daemon
  control but the daemon is not running.
- **Fix strategy (PR-HB-DAEMON-WIRE):** two acceptable shapes,
  founder picks:
  1. **Start it.** Add `await heartbeat_daemon.start()` to
     `main.py._run_deferred_initialization` next to the existing
     cron_scheduler and background_queue starts. Persist daemon
     state to a new `heartbeat_runs` table (mirror `cron_runs`
     pattern from migration 005). Surface last-run-time on the
     SettingsHeartbeat page.
  2. **Remove the controls.** If the daemon is intentionally not
     auto-started (founder runs it manually for cost reasons),
     gate the UI controls behind an explicit "Daemon: stopped
     (start manually)" status banner and label them honestly.
- **Effort:** 30 min for either shape.
- **Depends on:** none. P1-02 (heartbeat config persistence) is
  related but independent; either order works.
- **Blocks local demo?** N (operator can manually start). **Blocks
  cloud demo?** N (the controls are not on the public demo path).
- **Blast radius:** low. Either fix is local to startup + the
  Settings page; no cross-cutting refactor.

---

## P1 — Broken Execution (real loops not closed)

### P1-01 — Agent experiences DEFINED but no writer

- **File/Module:** `backend/app/services/memory.py:45-47`
  (EXPERIENCE_TYPES defined), `backend/app/services/cognition/
  ooda_engine.py` (REFLECT phase).
- **Evidence:** Per data-layer agent: "Content types are defined,
  but no caller explicitly invokes `store_experience()`. The
  LearningService evaluates action outcomes but stores to in-memory
  dataclass only, not NBMF."
- **Fix strategy:** wire OODA REFLECT to call `store_experience`
  with the appropriate content_type. Wire DaenaBot tool-call
  results to `store_experience("SKILL_OUTCOME", ...)`. Wire
  governance rejections to `store_experience("APPROACH_FAILED", ...)`.
- **Effort:** 2h (part of PR-LEARN-01).
- **Depends on:** P0-03 + P0-05.
- **Blocks local demo?** N. **Blocks cloud demo?** Y (learning
  loop never closes).

### P1-02 — Heartbeat config in daemon memory only

- **File/Module:** `backend/app/services/heartbeat/heartbeat_daemon.py`
  + `backend/app/api/v1/heartbeat.py` + `frontend/src/pages/settings/
  SettingsHeartbeat.tsx`.
- **Evidence:** Per Phase 10C-B + frontend agent: "writes daemon-
  process memory only. Restart erases every change."
- **Fix strategy:** PR-H1. Move all 7 heartbeat config fields
  (interval, active hours, per-check toggles, cost guards) to
  `users.settings.heartbeat_config` JSONB. Daemon re-reads on each
  cycle. Settings tab loses the "REDESIGN_FLOW" tooltip.
- **Effort:** 3h.
- **Depends on:** none.
- **Blocks local demo?** N (operator can re-config after restart).
  **Blocks cloud demo?** Y.

### P1-03 — `notif_heartbeat` + `notif_runtime_disconnect` enforce gate but have NO real trigger

- **File/Module:** `backend/app/services/heartbeat/*`,
  `backend/app/services/runtimes/*`, `backend/app/services/
  notification_service.py`.
- **Evidence:** PR-S2.1 report §4: "heartbeat — system-wide daemon,
  no per-user fan-out point. runtime_disconnect — singleton health
  tracker, no tenant_id/user_id in scope." Both are gated by
  `notif_*` flags but no service emits.
- **Fix strategy:** PR-NOTIF-FANOUT. Per-tenant heartbeat schedule
  + provider→tenant mapping for runtime + notification subscriber
  model. Heartbeat finding → fan-out to subscribers; runtime probe
  HEALTHY→DEGRADED transition → fan-out.
- **Effort:** 6h.
- **Depends on:** none.
- **Blocks local demo?** N (operator won't notice).
  **Blocks cloud demo?** N (toggles work but silent).

### P1-04 — VP stage 2.8 feature-flagged off

- **File/Module:** `backend/app/services/chat_orchestrator.py:1002-1194`.
- **Evidence:** Per execution-layer agent: "VP stage (2.8) is
  feature-flagged off; will activate in Phase 12. Complexity gate
  at line 1029 skips trivial queries to avoid 1-2s planning latency."
- **Fix strategy:** turn the flag on for non-trivial intents per
  the Three-Tier Escalation Router output. Wire VP plan output to
  the spawn-subtask materialization (already implemented at lines
  1069-1186).
- **Effort:** 2h (mostly testing).
- **Depends on:** PR-SPINE-03 (S0 CLASSIFY) for clean intent gate.
- **Blocks local demo?** N. **Blocks cloud demo?** N (chat works
  today without VP).

### P1-05 — Two scan launchers (ScanPage + EngagementConsolePage)

- **File/Module:** `frontend/src/pages/ScanPage.tsx`,
  `frontend/src/pages/EngagementConsolePage.tsx`.
- **Evidence:** Frontend agent §F.4: "Both submit a target + tier
  + scope to start a scan. Users confused: 'do I go to /scan or
  /engagements?'"
- **Fix strategy:** consolidate to one launcher routed by tier:
  T1-T2 → quick `/scan` flow; T3+ → governance-gated `/engagements`.
  Link the two surfaces explicitly in nav (no two parallel "start
  scan" buttons).
- **Effort:** 4h.
- **Depends on:** none.
- **Blocks local demo?** Y (founder demo could confuse audience).
  **Blocks cloud demo?** Y.

### P1-06 — `local_first_routing` + `cost_aware_routing` user toggles DEAD

- **File/Module:** `backend/app/services/model_router.py`,
  `backend/app/api/v1/settings.py`, `frontend/src/pages/settings/
  SettingsLLM.tsx`.
- **Evidence:** Phase 10b §2.4-2.5 audit. Per PR-S2.1 + PRD §I.4:
  "Routing prefs never read by ModelRouter."
- **Fix strategy:** PR-S4. Add per-request override to the chat
  request body (`local_first_routing` / `cost_aware_routing`),
  plumbed through `model_router.route()`. ModelRegistry weights
  flip when overrides present.
- **Effort:** 4h.
- **Depends on:** none.
- **Blocks local demo?** N. **Blocks cloud demo?** Y (claim of
  "smart routing" is empty).

### P1-07 — `monthly_budget` parallel source-of-truth

- **File/Module:** `backend/app/services/cost_guard.py:129`,
  `backend/app/services/billing/budget_manager.py:65`,
  `backend/app/api/v1/settings.py` (UserPreferencesUpdate).
- **Evidence:** Phase 10b §2.6: cost-guard reads
  `Subscription.monthly_budget_usd`; UI writes
  `users.settings.monthly_budget`. Vocab mismatch on
  `over_budget_action` (`warn|fallback|block` vs `warn_only|
  pause_tasks|free_models_only`). User edits have no effect.
- **Fix strategy:** PR-S3. Single enum across surface +
  BudgetManager. Cost-guard reads from user.settings. Add
  regression test (5 preflight calls with vs without budget cap).
- **Effort:** 3h.
- **Depends on:** none.
- **Blocks local demo?** N. **Blocks cloud demo?** Y (claim of
  cost control is empty).

### P1-08 — Tasks audit emit gap (8 actions)

- **File/Module:** `backend/app/services/execution_service.py` +
  `backend/app/api/v1/execution.py`.
- **Evidence:** Per Phase 9B §4.1 + Phase 10C-B: tasks `create / run
  / batch_run / retry / cancel / batch_archive / batch_delete` lack
  audit emit. Hard Law #1 violated for these mutations.
- **Fix strategy:** PR-T1. Apply the chat-session pattern (Phase
  10) to each task mutation; add `audit_emit_failed` debug log.
- **Effort:** 2h.
- **Depends on:** none.
- **Blocks local demo?** N. **Blocks cloud demo?** Y (audit gaps).

### P1-09 — Chat audit completeness gap (file_attach + export_session)

- **File/Module:** `backend/app/services/chat_orchestrator.py` +
  `backend/app/api/v1/chat.py` + `backend/app/api/v1/files.py`.
- **Evidence:** Per Phase 9B §4.1: file attach + export-session
  lack audit.
- **Fix strategy:** PR-T2. Same pattern as PR-T1.
- **Effort:** 1h.
- **Depends on:** none.
- **Blocks local demo?** N. **Blocks cloud demo?** Y (audit gaps).

---

## P2 — Duplicate / Complexity (cleanup)

### P2-01 — V1 connections panels still active

- **File/Module:** `frontend/src/pages/connections/McpServersPanel.tsx`
  (V1) coexists with `McpServersV2Panel.tsx`. Same for
  `PluginsCatalogBrowser.tsx` + `PluginsV2Panel.tsx`.
- **Evidence:** Frontend agent §F.1. `USE_CONNECTION_REGISTRY_V2`
  flag still false in prod.
- **Fix strategy:** flip flag to true in dev; hide V1 panels behind
  Founder-gated "Show legacy" toggle. Deprecate V1 endpoints in
  later phase.
- **Effort:** 1h (just the flag flip + tab gating).
- **Depends on:** Connections V2 truth completeness (already shipped
  per Phase 6).
- **Blocks local demo?** Y (operator sees two panels with potential
  contradiction). **Blocks cloud demo?** Y.

### P2-02 — `display_name` editable in two places

- **File/Module:** `frontend/src/pages/settings/SettingsGeneral.tsx`
  + `frontend/src/pages/account/AccountDetails.tsx`.
- **Evidence:** Frontend agent §F.2.
- **Fix strategy:** make `AccountPage` canonical; remove
  `display_name` field from `SettingsGeneral` (or read-only with
  link to `/account`).
- **Effort:** 0.5h.
- **Depends on:** none.
- **Blocks local demo?** N. **Blocks cloud demo?** N.

### P2-03 — API keys editable in two places

- **File/Module:** `frontend/src/pages/settings/SettingsDeveloper.tsx`
  + `frontend/src/pages/account/AccountApiKeys.tsx`.
- **Evidence:** Frontend agent §F.3.
- **Fix strategy:** remove API-key references from
  `SettingsDeveloper`; AccountPage is canonical.
- **Effort:** 0.5h.
- **Depends on:** none.
- **Blocks local demo?** N. **Blocks cloud demo?** N.

### P2-04 — `mcp_bridge.py` stub + `mcp_bridge_runtime_adapter.py` name collision

- **File/Module:** `backend/app/services/runtimes/adapters/mcp_bridge.py`
  (637 B stub) + `mcp_bridge_runtime_adapter.py` (21 KB working).
- **Evidence:** Execution-layer agent §C.4. Ultraview report §M2.
- **Fix strategy:** delete the stub; ensure no caller imports it.
- **Effort:** 0.5h.
- **Depends on:** none.
- **Blocks local demo?** N. **Blocks cloud demo?** N.

### P2-05 — Two background queues (heartbeat + autopilot)

- **File/Module:** `backend/app/services/heartbeat/work_queue.py`
  + `backend/app/services/autopilot/background_queue.py`.
- **Evidence:** Duplicates report. Two task-queue mental models.
- **Fix strategy:** document both with their distinct purposes;
  evaluate unification when PR-NOTIF-FANOUT lands. Defer hard merge
  until then.
- **Effort:** 2h documentation now; unification is later.
- **Depends on:** PR-NOTIF-FANOUT.
- **Blocks local demo?** N. **Blocks cloud demo?** N.

### P2-06 — TasksPage vs WorkstreamsPage taxonomy unclear

- **File/Module:** `frontend/src/pages/TasksPage.tsx` +
  `frontend/src/pages/WorkstreamsPage.tsx`.
- **Evidence:** Frontend agent §F.9.
- **Fix strategy:** add taxonomy tooltip on each page ("Tasks =
  jobs you queued; Workstreams = autonomous units Daena ran for
  you"). Long-term: WorkstreamsPage becomes the canonical "what's
  running" page per PRD §11.3 — TasksPage filtered sub-view.
- **Effort:** 0.5h tooltip; 4h full migration (overlaps with PR-SPINE-06).
- **Depends on:** PR-SPINE-06.
- **Blocks local demo?** N. **Blocks cloud demo?** N.

### P2-07 — Settings: 40 of 47 keys are dead consumers

- **File/Module:** `backend/app/api/v1/settings.py` (UserPreferencesUpdate
  defines 47 fields; 7 enforced post-Phase 11). Each Settings
  sub-tab in `frontend/src/pages/settings/`.
- **Evidence:** Data-layer agent §13. Phase 10b audit. Gemini's
  brutal observation (multi-model review): "Hallucination of
  Control. 40 of 47 settings are placebo. Breach of governed-AI
  brand promise."
- **Fix strategy:** for each of the 40 dead keys, either (a) ship
  a backend consumer (PR-S3, PR-S4, PR-H1 cover several), (b)
  add an honest "Coming Soon — PR-X wires this" badge with the PR
  named, or (c) DELETE the key from the schema + UI. No third path.
- **Effort:** 1h per key triaged; ~40h total to wire / label / delete
  the long tail. Triage in batches of 5-10.
- **Depends on:** none.
- **Blocks local demo?** Partial — RAG, routing, billing toggles
  are demoed and visibly fake. **Blocks cloud demo?** Y.

### P2-08 — Static "demo data" in browse modals

- **File/Module:** various `frontend/src/pages/connections/*` browse
  modals (per Duplicates report).
- **Evidence:** "Static catalog findings: Browse modal entries are
  not fully DB-sourced yet."
- **Fix strategy:** move all browse arrays to backend-served catalog
  endpoints. Hydrate on mount.
- **Effort:** 3h.
- **Depends on:** Connections V2 catalog endpoint (exists per
  ConnectionsRebuild).
- **Blocks local demo?** N. **Blocks cloud demo?** N.

### P2-09 — `developer_mode` user-key vs system-key collision

- **File/Module:** `backend/app/api/v1/settings.py` (defines
  `developer_mode` in user preferences) + `backend/app/core/config.py`
  (system-level `Settings.developer_mode`).
- **Evidence:** Phase 10b §4.3 + Phase 10C-B.
- **Fix strategy:** PR-S6. Rename user-level key to
  `developer_ui_mode` with migration. Frontend label: "Developer
  UI mode" + tooltip "Cosmetic only — system-wide developer mode
  is set at deployment level."
- **Effort:** 0.5h frontend; 1.5h backend with migration.
- **Depends on:** none.
- **Blocks local demo?** N. **Blocks cloud demo?** N.

### P2-10 — eDNA layer: NOT IMPLEMENTED but referenced in patent

- **File/Module:** none. `CLAUDE.md` IDENTITY section + patent doc
  reference.
- **Evidence:** Intelligence-layer agent §I: "No files found
  containing eDNA or enterprise.dna."
- **Fix strategy:** define minimum-viable eDNA: extract repeated
  approval patterns from audit trail → propose Plain-English Policy
  via the compiler → founder approves. This is a P2 because the
  marketing claim exists; if patent prosecution depends on
  embodiment, escalate to P0.
- **Effort:** 8h MVP.
- **Depends on:** P0-04 (Dream needs to be running first to
  produce signals).
- **Blocks local demo?** N. **Blocks cloud demo?** N (unless
  patent embodiment becomes critical).

---

## P3 — Polish

### P3-01 — Mobile / responsive surface

- **Evidence:** ConnectionsRebuild §2 explicitly defers; no other
  responsive design work scheduled.
- **Fix strategy:** out-of-scope per current founder priorities.
  Document the deferred-target version.
- **Effort:** 20h+.
- **Blocks local demo?** N. **Blocks cloud demo?** N.

### P3-02 — Hydrate completeness for `_UI_PREF_KEYS`

- **File/Module:** `frontend/src/stores/uiStore.ts:264-291`
  (`hydrateUiFromBackend` reads only 8 of 47 keys).
- **Evidence:** Phase 10b §4.1.
- **Fix strategy:** PR-S5. Walk all `_UI_PREF_KEYS` per-key.
- **Effort:** 1h.
- **Depends on:** none.
- **Blocks local demo?** N. **Blocks cloud demo?** N.

### P3-03 — Policy hard-delete should be soft-archive

- **File/Module:** `backend/app/api/v1/policies.py` (currently
  `DELETE /policies/{id}` hard-deletes).
- **Evidence:** Phase 10C-B + ADR-001 Rule 17.
- **Fix strategy:** PR-P1. Flip to `archived=true` + add
  `?show_archived=true` query param to GET.
- **Effort:** 1.5h.
- **Depends on:** none.
- **Blocks local demo?** N. **Blocks cloud demo?** N.

### P3-04 — DCP catalogue 30 of 55 missing

- **File/Module:** `backend/app/config/dcps.json`.
- **Evidence:** Intelligence-layer agent §E: "25 of 55 DCPs shipped;
  6 empty domain stubs."
- **Fix strategy:** ship the 30 remaining DCPs. Each is a JSON
  object (id / archetype / prompt_directive / decision_priorities
  / blind_spots / evaluation_criteria). Founder writes the
  archetypes; Claude / Codex draft the directives; founder
  approves.
- **Effort:** 8h founder-curated + 4h scaffolding.
- **Depends on:** none.
- **Blocks local demo?** N. **Blocks cloud demo?** N.

### P3-05 — TOOL_CATALOG hardcoded

- **File/Module:** `backend/app/services/tool_lifecycle/tool_discovery.py`
  (~170 tools hardcoded).
- **Evidence:** Intelligence-layer agent §J.
- **Fix strategy:** move catalog to DB-backed table; add a
  "register tool" admin endpoint; keep TOOL_CATALOG.py as default
  seed.
- **Effort:** 4h.
- **Depends on:** none.
- **Blocks local demo?** N. **Blocks cloud demo?** N.

### P3-06 — DepartmentChatPage may not bias routing

- **File/Module:** `frontend/src/pages/DepartmentChatPage.tsx`
  + `backend/app/services/chat_orchestrator.py`.
- **Evidence:** Frontend agent §E.1: "Verify department_id actually
  biases orchestrator routing (not just cosmetic)."
- **Fix strategy:** trace `department_id` from
  DepartmentChatPage → chat request body → orchestrator → Soul
  Engine overlay. Add a regression test.
- **Effort:** 1h verification + 1-2h to wire if missing.
- **Depends on:** none.
- **Blocks local demo?** N. **Blocks cloud demo?** N.

### P3-07 — Heartbeat + autopilot queue unification

- **See P2-05.**

### P3-08 — Vault sync to Daena-Mind STUB

- **File/Module:** `backend/app/services/nbmf_archive.py` +
  Phase E plan.
- **Evidence:** Data-layer agent §12: "No bidirectional sync from
  D:/Ideas/Daena-Mind/ to DB."
- **Fix strategy:** wire export to write `D:\Ideas\Daena-Mind\
  T{0..4}\<entry>.md` files; wire import to read on startup. This
  closes the founder-private vault loop.
- **Effort:** 6h.
- **Depends on:** none.
- **Blocks local demo?** N. **Blocks cloud demo?** N.

---

## Summary table — totals by priority + demo-blocking

| Priority | Count | Total effort (h) | Blocks local demo | Blocks cloud demo |
|---|---:|---:|---:|---:|
| P0 trust/safety | 8 | 22.5 | 3 | 8 |
| P1 broken execution | 9 | 27.5 | 1 | 8 |
| P2 duplicate/complexity | 10 | ~58 (long-tail Settings dominates) | 2 | 1 |
| P3 polish | 8 | ~32 | 0 | 0 |
| **Total** | **35 gaps** | **~140 h** | **6** | **17** |

---

## Recommended sequencing (first 3 PRs)

In strict priority order to unblock founder demos and ship Phase 12:

### PR #1 — PR-AUDIT-VERIFY + PR-RAG-HONEST (P0-01 + P0-02)
- **Effort:** 3h total.
- **Why first:** both are 1-2h Rule-17 fixes that close two of the
  loudest "we lie about it" surfaces. Audit chain verify endpoint
  + RAG honest-status endpoint. No new infrastructure.
- **Multi-agent suggestion:** Codex on the verify endpoint
  (single-file algorithmic; matches Cross-AI delegation table);
  Claude on the RAG status (cross-file: backend endpoint + frontend
  badge label change).

### PR #2 — PR-LEARN-01 + PR-DREAM-01 (P0-03 + P0-04 + P0-05)
- **Effort:** 7h total.
- **Why second:** closes the self-improvement loop. LearningService
  persists → store_experience writes to NBMF agent-experience
  rows → Dream Engine consolidates them nightly. Three highest-
  leverage intelligence-layer gaps fixed in one logical PR.
- **Multi-agent suggestion:** Claude leads (cross-file architecture);
  Codex generates the new tables' Alembic migrations + tests
  (single-file algorithmic).

### PR #3 — PR-SPINE-01 + PR-SPINE-02 (Workstream + Capability Registry)
- **Effort:** 7h total.
- **Why third:** establishes the foundation for the Execution
  Spine. New `Workstream` model + `CapabilityRegistry.find()` over
  4 sources. Once these land, every subsequent PR (PR-SPINE-03..06)
  composes on top.
- **Multi-agent suggestion:** Claude (multi-file architecture +
  state-machine design); Codex on the capability registry's
  per-source adapter implementations + caching layer; Gemini on
  the operator-facing rationale strings the registry returns.

After these three PRs ship, the next wave (PR-SPINE-03..06,
PR-NOTIF-FANOUT, PR-S3, PR-S4) can run in parallel because the
foundation is in place.

---

End of backlog.
