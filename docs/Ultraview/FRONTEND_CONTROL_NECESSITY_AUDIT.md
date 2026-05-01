# Frontend Control Necessity Audit — Phase 10C-B

**Date:** 2026-05-01
**Operator:** Claude Code (Opus 4.7) under founder-direction Phase 10C-B task
**HEAD:** `d4ea4f3`
**Scope:** Necessity classification of every visible control across 13 priority routes, building on the Phase 9B `UI_ACTION_CONTRACT_MATRIX.md` (158 actions) and the Phase 10b `PHASE_10B_SETTINGS_DOWNSTREAM_READ_AUDIT.md` (14 focus settings).
**Method:** static read of source + cross-reference against the Phase 9B / 10 / 10b reality table; no broad re-audit (Phase 9B already did the field traversal).

> **Headline:** of the **158 actions** Phase 9B catalogued plus the
> **14 focus settings** Phase 10b mapped, Phase 10 + 10b moved
> **17 actions** out of UNSAFE / FAKE / BROKEN / PARTIAL categories
> into KEEP_WORKING. **22 controls remain candidates for Phase 10C-D
> minimal action** (rename / disable+ComingSoon / tooltip / remove);
> the rest are KEEP_WORKING. **Zero new dead surfaces** were found.

---

## 0. TL;DR — what's necessary, what's not

| Final status | Count | Examples |
|---|---:|---|
| **KEEP_WORKING** | ~120 | All chat session CRUD + audit, scan start (now scoped), V2 connections panel, governance approvals, audit chain, project CRUD, file upload/download, NBMF memory ops, dynamic provider provision, all 5 Phase 10b ghost-call fixes, all 3 P0 unsafe gates from Phase 10 |
| **KEEP_BUT_NEEDS_BACKEND_CONSUMER** | 5 | `local_first_routing`, `cost_aware_routing`, `monthly_budget`, `over_budget_action`, `budget_alert_threshold` (per Phase 10b audit §2.4-2.8 — settings persist but no consumer reads them) |
| **DISABLE_AS_COMING_SOON** | 14 | 9 `notif_*` toggles (no emitter), 5 privacy toggles `memory_generation`, `search_past_conversations`, `improve_from_usage`, `location_metadata`, `storage_local` (no enforcer) |
| **KEEP_BUT_RENAME** | 2 | `users.settings.developer_mode` (collides with system-level `Settings.developer_mode`); `RuntimeSwapper.tsx` file-level comment is stale (says "removed in Session 9") |
| **REDESIGN_FLOW** | 2 | Heartbeat config tab (writes daemon-memory only — every save evaporates on restart); Connections V1↔V2 duplication for the 3 panels still co-exists |
| **NEEDS_TEST** | 6 | `/projects` Edit/Delete/Set-Working-Directory; `/workstreams` Pause/Resume; chat session export-JSON has no Playwright test |
| **REMOVE_DEAD_SURFACE** | 0 | Per Header.tsx comment, RuntimeSwapper.tsx is intentionally archived-but-not-deleted ("Mind Control may reuse it"). All other dead surfaces from Phase 9B are similarly intentional. |
| **UNSAFE_BLOCKED** | 0 | Phase 10 closed all 3 P0 UNSAFE rows (U1/U2/U3). No new UNSAFE surfaced. |
| **NEEDS_AUDIT_EMIT** (cross-cutting from matrix §4.1) | 12 | Tasks: create / run / batch-run / retry / cancel / batch-archive / batch-delete; Chat: file attach + file remove + export session; Main Brain change is WARNING-log-only |

The detail tables in §3 cite source file:line and link back to the
matrix entry that originated each finding.

---

## 1. Method + sources

This audit **does not re-traverse** the 158-action matrix. Phase 9B
spent six parallel agents pinning `(component, handler, endpoint,
DB writes, audit event, status)` for every visible control. Phase 10
+ 10b updated specific rows (U1/U2/U3, scan UX, ghost calls,
chat-session audit). This audit **adds the necessity dimension**:
KEEP / RENAME / DISABLE / REMOVE / REDESIGN / NEEDS_TEST.

Sources (in order of authority):

1. `UI_ACTION_CONTRACT_MATRIX.md` — Phase 9B per-action data (158 rows).
2. `PHASE_10_PRODUCT_INTEGRATION_VERIFICATION.md` — what Phase 10 fixed.
3. `PHASE_10B_VERIFICATION_REPORT.md` — what Phase 10b fixed.
4. `PHASE_10B_SETTINGS_DOWNSTREAM_READ_AUDIT.md` — settings consumer
   gaps (the source for the KEEP_BUT_NEEDS_BACKEND_CONSUMER + the
   DISABLE_AS_COMING_SOON classifications below).
5. Live tree state at HEAD `d4ea4f3` (2026-05-01).

---

## 2. Per-cluster summary (matrix update + necessity dimension)

| Cluster | Actions | KEEP_WORKING | NEEDS_CONSUMER | DISABLE_COMING_SOON | RENAME | REDESIGN | NEEDS_TEST | REMOVE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| /chat + /dashboard | 18 | 17 | 0 | 0 | 0 | 0 | 1 (export-session) | 0 |
| /connections (V1+V2) | 19 | 13 | 0 | 0 | 0 | 3 (V1↔V2 dup) | 3 | 0 |
| /settings (13 tabs) | 47 | 13 | 5 | 14 | 1 | 7 (heartbeat) | 0 | 0 |
| /security + /scan + /engagements | 18 | 16 | 0 | 0 | 0 | 0 | 2 (Sec Tools/Shields/Missions HANDS-OFF) | 0 |
| /tasks + workstreams + pipeline + projects + files | 21 | 14 | 0 | 0 | 0 | 0 | 7 | 0 |
| /minds + /departments + /skills + /governance + /policies + /company-mode + /analytics | 35 | 32 | 0 | 0 | 1 | 1 (policies hard-delete) | 0 | 0 |
| Phase 10b ghost-fix routes (NEW) | 5 | 5 | 0 | 0 | 0 | 0 | 0 | 0 |
| **TOTAL** | **163** | **110** | **5** | **14** | **2** | **11** | **13** | **0** |

(Note: 158 from matrix + 5 net-new from Phase 10b = 163. KEEP rows
include both V_W and PARTIAL items that don't need a Phase 10C-D
intervention beyond what already shipped.)

---

## 3. Detail per priority area

> Format: `Cluster ▸ Control ▸ Final status ▸ Why ▸ Phase 10C-D action`

### 3.1 Settings — the cluster Phase 10C-D should mostly touch

#### Routing toggles (downstream-read pending — Phase 10b audit §2.4-2.5)

| Control | File:line | Status | Phase 10C-D action |
|---|---|---|---|
| **Local-First Routing** | `SettingsLLM.tsx:204` | **KEEP_BUT_NEEDS_BACKEND_CONSUMER** | Add `title=` tooltip: "Persists. ModelRouter consumption pending (Phase 11 PR-S4)." |
| **Cost-Aware Routing** | `SettingsLLM.tsx:211` | **KEEP_BUT_NEEDS_BACKEND_CONSUMER** | Same tooltip. |

#### Billing toggles (parallel sources of truth — Phase 10b audit §2.6-2.8)

| Control | File:line | Status | Phase 10C-D action |
|---|---|---|---|
| **Monthly Budget** | `SettingsBilling.tsx:376-385` | **KEEP_BUT_NEEDS_BACKEND_CONSUMER** | Tooltip: "Persists in user.settings. Cost-guard reads `Subscription.monthly_budget_usd` (parallel source of truth). Phase 11 PR-S3 unifies." |
| **Budget Alert Threshold** | `:389-401` | **KEEP_BUT_NEEDS_BACKEND_CONSUMER** | Tooltip: "Persists. Alert emit pending — depends on Phase 11 notification emitter (PR-S2)." |
| **Over-Budget Action** | `:405-417` | **KEEP_BUT_NEEDS_BACKEND_CONSUMER** | Tooltip: "Persists. BudgetManager hardcodes the default; vocab mismatch (warn/fallback/block ↔ warn_only/pause_tasks/free_models_only) blocks wiring. Phase 11 PR-S3." |

The file `SettingsBilling.tsx:370` already has an honest in-code
comment about this state. Phase 10C-D promotes it to user-facing
copy.

#### Notification toggles (no emitter — Phase 10b audit §2.9)

All 9 notification controls in `SettingsNotifications.tsx` should be
**DISABLE_AS_COMING_SOON** because there is no notification emitter
in the backend yet. Per Rule 17 ("Honesty + Persistence + Visibility
... if a feature cannot answer 'where does this persist?' and 'how
does the user see it fail?', it does not ship") — the toggles
currently advertise a capability that the system cannot deliver.

| Control | File:line | Status | Phase 10C-D action |
|---|---|---|---|
| **Desktop master** | `SettingsNotifications.tsx:77` | **DISABLE_AS_COMING_SOON** | Switch `disabled` + "Coming soon" Badge |
| **Task Completion** | `:101` | **DISABLE_AS_COMING_SOON** | same |
| **Budget Alert** | `:105` | **DISABLE_AS_COMING_SOON** | same |
| **Heartbeat** | `:109` | **DISABLE_AS_COMING_SOON** | same |
| **Governance Rejection** | `:113` | **DISABLE_AS_COMING_SOON** | same |
| **Runtime Disconnect** | `:117` | **DISABLE_AS_COMING_SOON** | same |
| **Sound** | `:136` | **DISABLE_AS_COMING_SOON** | same |
| **Email** | `:153-161` | **already DEAD/disabled** in code | leave as-is (already correct shape) |
| **Daily Digest** | `:140`(?) | **DISABLE_AS_COMING_SOON** | same |

#### Privacy toggles (no enforcer — Phase 10b audit §2.10)

These advertise a privacy *guarantee* that the backend doesn't
enforce. **DISABLE_AS_COMING_SOON** is the only honest move; leaving
them on creates a trust hazard.

| Control | File:line | Status | Phase 10C-D action |
|---|---|---|---|
| **Generate Memories from Conversations** | `SettingsPrivacy.tsx:120` | **DISABLE_AS_COMING_SOON** | Switch disabled + "Enforcement coming soon" Badge. **Highest-priority of all the Coming Soon labels** — the toggle implies "OFF means no memory writes" but `MemoryService.write_memory` does not check this flag. |
| **Search Past Conversations** | `:128` | **DISABLE_AS_COMING_SOON** | Same; `MemoryRecall` Stage 7 doesn't check it. |
| **Improve from Usage** | `:161` | **DISABLE_AS_COMING_SOON** | No consumer at all; Phase 11 needs to define the semantic. |
| **Location Metadata** | `:169` | **DISABLE_AS_COMING_SOON** | Same. |
| **Memory Storage (Cloud)** | `:135-143` | **already correctly disabled with "coming soon" copy** | Leave as-is (this is the model for the others). |

#### `developer_mode` user-level vs system-level naming collision (audit §4.3)

| Control | File:line | Status | Phase 10C-D action |
|---|---|---|---|
| User-level `developer_mode` toggle | `SettingsDeveloper.tsx:159` (display only) + `_UI_PREF_KEYS` in `settings.py:151` | **KEEP_BUT_RENAME** | Frontend label change: "Developer UI mode" + tooltip "Cosmetic only — system-wide developer mode (controls archive vs hard-delete) is set at the deployment level." Backend rename to `developer_ui_mode` is Phase 11 PR-S6 (requires migration). For Phase 10C-D, only the frontend label moves. |

#### Heartbeat tab (REDESIGN_FLOW)

7 controls all write daemon-process memory only (matrix §3.4 noted
"Daemon-memory only" for each). Restart erases every change.

| Control | File:line | Status | Phase 10C-D action |
|---|---|---|---|
| Toggle Start/Pause | `SettingsHeartbeat.tsx:318-324` | **REDESIGN_FLOW** | Tooltip: "Persists in daemon memory only — restart resets. Phase 11 will move to a `heartbeat_config` DB row." |
| Set Interval | `:423-436` | **REDESIGN_FLOW** | same |
| Active Hours | `:444-464` | **REDESIGN_FLOW** | same |
| Toggle Checks (13) | `:472-487` | **REDESIGN_FLOW** | same |
| Cost Guard | `:497-515` | **REDESIGN_FLOW** | same |

(Trigger Now is V_W — the daemon runs the cycle; no persistence
needed.)

### 3.2 Connections (V1 ↔ V2 duplication — REDESIGN_FLOW)

Phase 9B §1.3 documented three V1/V2 surface duplicates that Phase 10
+ 10b did NOT touch (founder rule keeps `USE_CONNECTION_REGISTRY_V2 =
false` in production). **Status remains REDESIGN_FLOW pending the
flag flip.**

| Surface | V1 component | V2 component | Phase 10C-D action |
|---|---|---|---|
| Runtime Selection (Main Brain) | `MainBrainPanel.choose()` legacy mode bypass | Same `choose()` with V2 callable gate | **None this phase** — single file already; V1 branch removes when flag flips |
| Plugin Install | `PluginsCatalogBrowser` legacy install dialog | Same dialog reused | **None** — not actually duplicated code, just panel coexistence |
| MCP Servers List | `McpServersPanel` | `McpServersV2Panel` | **None this phase** — hide V1 panel when V2 enabled is the V2-flag-flip work, not Phase 10C-D scope |

#### Phase 6 missing endpoint (matrix `Connections — Plugins (V2): Seed Providers`)

| Control | File:line | Status | Phase 10C-D action |
|---|---|---|---|
| Seed Providers (FOUNDER+) | `PluginsV2Panel.tsx` (button visible) | endpoint `POST /connections/v2/providers/seed` not implemented | **DISABLE_AS_COMING_SOON** if the button is currently clickable; otherwise document only. (Founder verifies UI state.) |

#### Connections V2 verbs (all KEEP_WORKING)

`Probe`, `Enable`, `Disable`, `Archive`, `Refresh`, filter, search,
drawer — all V_W per matrix §3.3. No action.

### 3.3 Security / Scan / Engagements

Phase 10 + 10b closed every UNSAFE + BROKEN row in this cluster.
**All KEEP_WORKING:**

| Control | Phase 10/10b status |
|---|---|
| Start Scan | **KEEP_WORKING** — auth required + scope-gate enforced (Phase 10 U2) |
| View Report | **KEEP_WORKING** — unchanged from matrix V_W |
| Download Report | **KEEP_WORKING** |
| Archive Scan (single + bulk) | **KEEP_WORKING** — Phase 10b added "Show archived" toggle for recovery |
| Show Archived (Phase 10b NEW) | **KEEP_WORKING** |
| Re-run Scan (Phase 10b NEW button on Active list) | **KEEP_WORKING** |
| Report Ready Badge (Phase 10b NEW) | **KEEP_WORKING** |
| Scan Walkthrough (SSE) | **KEEP_WORKING** |
| Engagement Start (Phase 10 U3 closed) | **KEEP_WORKING** — scope-gate at REST boundary |
| Engagement List / Open Report | **KEEP_WORKING** |
| Authorized-Scope CRUD | **KEEP_WORKING** |

**HANDS-OFF reminder:** `pages/security/{SecurityTools, SecurityShields, SecurityMissions}.tsx` are on the v3.7.0 Security Supercharge HANDS-OFF list. Status remains UNKNOWN/NEEDS_TEST per matrix §3.5; Phase 10C-D respects the hands-off label.

### 3.4 Company Mode

Phase 10 + 10b closed both Company Mode gaps:

| Control | Status |
|---|---|
| Activate Daena | **KEEP_WORKING** — auto_send/approval contradiction blocked at REST + UI (Phase 10 U1) |
| Save Seed Brief | **KEEP_WORKING** |
| **Delete Seed Brief** (Phase 10b NEW soft-archive) | **KEEP_WORKING** — was 405 ghost; now archives to `company_seed.archived-<UTC>.md` |
| Send Draft (Mission) | **KEEP_WORKING** |
| List Activations | **KEEP_WORKING** |
| Process Reply | **KEEP_WORKING** |

### 3.5 Chat / Files

Phase 10 closed the chat audit gap; Phase 10b closed the project sub-resource ghosts. Chat-side action statuses post-Phase-10/10b:

| Control | Status | Phase 10C-D action |
|---|---|---|
| New Chat | **KEEP_WORKING** | none |
| Send Message (SSE) | **KEEP_WORKING** | none |
| Cancel Stream | **KEEP_WORKING** | none |
| Rename Session | **KEEP_WORKING** — Phase 10 audit emit added | none |
| Archive Session | **KEEP_WORKING** — Phase 10 audit emit | none |
| Un-archive Session | **KEEP_WORKING** — Phase 10 audit emit | none |
| Batch Archive | **KEEP_WORKING** — emits per-session audit (matrix v_w) | none |
| Export Session JSON | **KEEP_WORKING** | NEEDS_TEST (no Playwright cover) |
| Approve / Reject Inline | **KEEP_WORKING** | none |
| Attach File | **KEEP_WORKING** | (audit emit gap noted in matrix §4.1; not Phase 10C-D scope) |
| **Remove Attached File** (X on chip) | **KEEP_WORKING** — Phase 10 tooltip clarifies "removes from this draft only; file remains in /files" | none — the honest-tooltip ship was the right move; converting to true file-delete is Phase 11+ |
| Slash commands (10) | **KEEP_WORKING** ×10 | none |
| Dismiss Autopilot Banner | **KEEP_WORKING** | none |

Files page: upload, single delete (with explicit "permanently removes" copy), batch delete, download — all V_W per matrix §3.6. No action.

### 3.6 Tasks / Workstreams / Pipeline / Projects

| Control | Status | Phase 10C-D action |
|---|---|---|
| Tasks: Run / Batch Run / Retry / Cancel / Batch Archive / Batch Delete | **KEEP_WORKING** | NEEDS_AUDIT_EMIT cross-cutting (matrix §4.1) — not Phase 10C-D scope (would touch backend) |
| Workstreams: Redirect | **KEEP_WORKING** | none |
| Workstreams: Pause / Resume | **NEEDS_TEST** (matrix §3.6 marked endpoint impl as UNKNOWN line) | none — confirm impl + add test in Phase 11 |
| Pipeline: Create / Advance / Mark Lost | **KEEP_WORKING** | none |
| Projects: Create | **KEEP_WORKING** | none |
| Projects: Edit / Delete / Set Working Directory | **NEEDS_TEST** (matrix marked UNKNOWN) | confirm impls work; add tests in Phase 11 |
| **Projects: Tasks tab** (Phase 10b NEW) | **KEEP_WORKING** | none — empty list with honest meta |
| **Projects: Files tab** (Phase 10b NEW) | **KEEP_WORKING** | none — same shape |

### 3.7 Governance / Audit / Skills / Policies / Departments / Minds / Analytics

All V_W per matrix §3.7 except:

| Control | Status | Phase 10C-D action |
|---|---|---|
| Policies: Delete | **REDESIGN_FLOW** — currently hard-delete; matrix §6 item 9 calls for soft-archive | document; full implementation is Phase 11 PR (touches backend route + schema flag) |
| All other governance/skills/minds/analytics actions | **KEEP_WORKING** | none |

### 3.8 Phase 10b ghost-fix routes (NEW since matrix)

| Route | Status | Phase 10C-D action |
|---|---|---|
| `DELETE /company-mode/seed-brief` | **KEEP_WORKING** | none |
| `GET /projects/{id}/tasks` | **KEEP_WORKING** (honest empty + meta) | none |
| `GET /projects/{id}/files` | **KEEP_WORKING** (honest empty + meta) | none |
| `GET /runtimes/subscriptions` | **KEEP_WORKING** | none |
| `GET /security/scans?archived=true` | **KEEP_WORKING** | none |

---

## 4. Special-focus answer matrix (per brief §10C-B "Special focus")

### 4.1 Settings keys

Per Phase 10b audit `§1`:

| Key | WIRED? | Phase 10C-D action |
|---|---|---|
| `local_first_routing` | STUB (no consumer) | KEEP + tooltip |
| `cost_aware_routing` | STUB | KEEP + tooltip |
| `monthly_budget` | PARTIAL (parallel source of truth) | KEEP + tooltip |
| `budget_alert_threshold` | STUB | KEEP + tooltip |
| `over_budget_action` | PARTIAL (vocab mismatch) | KEEP + tooltip |
| All `notif_*` (9 toggles) | DEAD (no emitter) | DISABLE + Coming Soon |
| `memory_generation` | DEAD (no enforcer) | DISABLE + Coming Soon |
| `search_past_conversations` | DEAD | DISABLE + Coming Soon |
| `improve_from_usage` | DEAD | DISABLE + Coming Soon |
| `location_metadata` | DEAD | DISABLE + Coming Soon |
| `storage_local` | DEAD (cloud option already disabled — local default) | leave as-is |
| `developer_mode` (user) | naming collision with system | RENAME label to "Developer UI mode" |

### 4.2 Connection buttons

| Verb | Status | Phase 10C-D action |
|---|---|---|
| install (Plugin Install dialog) | KEEP_WORKING | none |
| import (V2 import flow) | KEEP_WORKING | none |
| connect (OAuth callback) | KEEP_WORKING | none |
| disconnect (`POST /runtimes/{id}/disconnect`) | KEEP_WORKING | none |
| configure | KEEP_WORKING | none |
| test (`POST /runtimes/{id}/test` two-stage probe) | KEEP_WORKING | none |
| probe (V2 `POST /connections/v2/{id}/probe`) | KEEP_WORKING | none |
| enable / disable (V2) | KEEP_WORKING | none |
| archive (V2 soft-archive) | KEEP_WORKING | none |
| **Plugins V2 Seed Providers** (FOUNDER+) | endpoint missing | DISABLE if button is currently clickable |

### 4.3 Security / scan buttons

All KEEP_WORKING post-Phase-10b. See §3.3.

### 4.4 Company-mode buttons

All KEEP_WORKING post-Phase-10/10b. See §3.4.

### 4.5 Chat / files buttons

All KEEP_WORKING. See §3.5.

---

## 5. What Phase 10C-D should ship (minimal-fix shortlist)

In strict priority order (highest founder-trust impact first):

1. **DISABLE + "Coming soon" Badge on the 4 privacy toggles** at `SettingsPrivacy.tsx`. (1 file, ~30 lines.) — closes the *privacy guarantee* trust hazard.
2. **DISABLE + "Coming soon" Badge on the 8 notification toggles** at `SettingsNotifications.tsx` (excluding the already-disabled Email which is correct). (1 file, ~40 lines.)
3. **Tooltip ("Persists; backend consumption pending — Phase 11") on the 5 routing/billing toggles** at `SettingsLLM.tsx` + `SettingsBilling.tsx`. (2 files, ~10 lines.)
4. **Rename label "Developer Mode" → "Developer UI mode" + tooltip** at `SettingsDeveloper.tsx`. Frontend-only — no backend rename in Phase 10C-D (PR-S6 in Phase 11 handles the JSONB key rename + migration).
5. **Tooltip on 5 Heartbeat config controls** clarifying daemon-memory-only persistence. (1 file, ~10 lines.)
6. **Verify the Plugins V2 Seed Providers button** state — if currently clickable, disable + Coming Soon badge.

**Out of scope for Phase 10C-D (deferred to Phase 11):**

- Wiring the 5 routing/billing settings to consumers (audit §6 PR-S3, PR-S4).
- Building the notification emitter (PR-S2).
- Wiring privacy enforcement into MemoryService + MemoryRecall (PR-S1).
- Renaming `developer_mode` JSONB key (PR-S6 — touches schema).
- Soft-archive on policy delete.
- Heartbeat config moving to DB (touches daemon init order).
- Audit emit on tasks + chat-attach + chat-export.
- V1↔V2 connection panel collapse (depends on V2 flag flip).

---

## 6. Top 10 Phase 11 fixes (extracted for the founder's roadmap)

1. **PR-S1: Privacy enforcement** — wire `memory_generation` to `MemoryService.write_memory`; wire `search_past_conversations` to `MemoryRecall` Stage 7. ~2h.
2. **PR-S2: Notification emitter stub** — ship a minimal `NotificationService` that reads `notif_*` flags and emits to in-app toast banner. Removes the Coming-Soon labels Phase 10C-D added. ~3h.
3. **PR-S3: Budget vocab unification + wire** — single enum across API + BudgetManager; wire `BudgetManager` to read `monthly_budget` + `over_budget_action` from `user.settings`. ~3h.
4. **PR-S4: Routing toggle wire** — add per-request `local_first_routing` + `cost_aware_routing` overrides on chat request body, plumbed through ModelRouter. ~4h.
5. **PR-S5: Hydrate completeness** — extend `uiStore.hydrateUiFromBackend` to walk `_UI_PREF_KEYS` and seed every key, not just the 8 it currently handles. ~1h.
6. **PR-S6: developer_mode key rename** — rename `users.settings.developer_mode` to `developer_ui_mode` (migration + read-side fall-through). ~30m.
7. **PR-T1: Tasks audit emit** — extend the chat-session `audit_emit_failed` pattern from Phase 10 to `tasks.run / batch_run / retry / cancel / batch_archive / batch_delete`. ~2h.
8. **PR-T2: Chat audit emit completeness** — same pattern for `file_attach` and `export_session`. ~1h.
9. **PR-P1: Policy soft-archive** — flip `DELETE /policies/{id}` to set `archived=true` + add `?show_archived` query param to GET. Mirror the scan-archive pattern. ~1.5h.
10. **PR-H1: Heartbeat config persistence** — move daemon config from in-memory to `heartbeat_config` table; daemon reads on init + each PATCH writes. Removes the "REDESIGN_FLOW" tooltip from Phase 10C-D. ~3h.

(Items 11+ from Phase 9B repair pre-notes — Re-run scan completion notification, V1↔V2 collapse — already shipped in Phase 10b or out-of-scope per V2-flag rule.)

**Total Phase 11 sprint estimate:** ~21 hours = ~3 working days. Should be a single milestone.

---

## 7. Hard rules respected

- No production deploy.
- No `USE_CONNECTION_REGISTRY_V2=true` flip.
- No `vault --apply`.
- `vault.py` / `oauth_credentials_store.py` not touched.
- No secrets read or printed.
- No external scans.
- No external messages / emails sent.
- No Phase 11 work begun.
- No broad redesign — every "REDESIGN_FLOW" marker defers actual work to Phase 11.

End of audit.
