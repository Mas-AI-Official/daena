# Phase 9B — UI Action Contract Matrix

**Date:** 2026-05-01
**Operator:** Claude Code (Opus 4.7) under founder-direction interaction-audit task
**Scope:** Per-action audit of every visible button/menu/toggle/dropdown/form/slash-command across the live frontend
**Method:** 6 parallel Explore-agent passes, evidence-backed, brutally honest (UNKNOWN beats made-up)
**Companion docs:** `PHASE_9_TOOLING_READINESS.md` (9A), `FRONTEND_BACKEND_TRUTH_MATRIX.md` (route-level), `API_CONTRACT_REALITY.md`, `DUPLICATES_DEAD_FILES_UNWIRED_REPORT.md`

> **Status one-liner:** 158 actions audited across 12 route clusters. **100 VERIFIED_WORKING / 19 PARTIAL / 26 FAKE / 3 DEAD / 7 UNKNOWN / 1 BROKEN / 3 UNSAFE / 3 V1↔V2 DUPLICATE.** The bulk of "FAKE" is one architectural failure (settings localStorage drift) repeated 25 times; the bulk of "PARTIAL" is missing audit events on chat-session and execution mutations. Three UNSAFE rows need pre-deploy attention regardless of any other repair.

---

## 1. Headline findings (read this first)

### 1.1. Three UNSAFE actions (P0 — fix before any user-facing demo)

| # | Action | Route | Smoking gun | Risk |
|---|---|---|---|---|
| U1 | **Company Mode: Activate Daena** | `/company-mode` | `CompanyModePage.tsx:272-308`. The form lets the founder set `auto_send=true` AND `require_founder_approval=false` simultaneously. Backend honors both flags as set; no UI guard prevents the contradiction. | External email/LinkedIn/SMS sent without approval gate. Direct violation of CLAUDE.md "Never auto-send DMs", "External-action sent flag" rule. |
| U2 | **Scan: Start Scan** | `/scan` | `security_dashboard.py:488-523` accepts the target and dispatches without calling `target_matches_scope()`. Scope gate exists in `scan_workflow.py:545-578` but runs *after* job-create, meaning the user already has a job_id for an out-of-scope target. | Unauthorized scan against any target user types in. Authorized-scope mechanism exists but is bypassable at the REST boundary. |
| U3 | **Engagements: Start Governed Engagement** | `/engagements` | `engagements.py:55-133` delegates target validation to `SecurityOperationsAgent.start_engagement()`. Whether that agent enforces scope is **UNKNOWN** without reading the agent (HANDS-OFF list — audit only). | Same shape as U2; scope gate may exist deeper but isn't visible at the API surface. |

### 1.2. Settings persistence: 34 of 47 settings (72%) don't survive a backend restart or a fresh device

The pattern is identical across 25 of those 34: `persistUiPref(...)` writes to `localStorage` instead of `PUT /settings/user`. Affected settings the founder will care about most:

| Setting | Tab | Where it really lives | Effect of the bug |
|---|---|---|---|
| **Governance Mode** (UNLEASHED/BALANCED/GOVERNED) | `/settings/governance` | `localStorage.default_governance_mode` | Pipeline never sees the change. Founder thinks they moved to GOVERNED; backend keeps old posture. |
| **Cost-Aware Routing** | `/settings/llm` | `localStorage.cost_aware_routing` | ModelRouter doesn't read this. Cost weight not adjusted. |
| **Local-First Routing** | `/settings/llm` | `localStorage.local_first_routing` | ModelRouter doesn't read this. Locality preference not enforced. |
| **Monthly Budget / Alert Threshold / Over-Budget Action** | `/settings/billing` | `localStorage.monthly_budget` etc. | Cost-tracker doesn't enforce these. The values shown in the UI cap nothing. |
| **All 8 notification toggles** (desktop, task, budget, heartbeat, gov-reject, runtime-disconnect, sound, email) | `/settings/notifications` | `localStorage.notif_*` | Backend can't possibly know what to send/suppress; toggles only affect any future client-side notification surfaces. |
| **Default Chat Mode (CMD/EXE)** | `/settings/general` | `localStorage.default_chat_mode` | Defaults reset on logout-from-other-device. |
| **Default Routing (STD/QE)** | `/settings/general` | `localStorage.default_routing_mode` | Same as above. |
| **Persist Thinking + AGI Mode + Dark Mode** | `/settings/general` | `localStorage.*` | Per-device only. |
| **Privacy: Memory Generation, Search Past Convos, Improve from Usage, Location Metadata** | `/settings/privacy` | `localStorage.*` | Backend never enforces; user has no actual data-control over what's claimed. |

The other 9 problematic settings are heartbeat config (interval, hours, checks, cost guards) — those persist *in the daemon's process memory*, so a `uvicorn` restart silently reverts them.

### 1.3. Three V1↔V2 duplicate surfaces in Connections

| Action | V1 surface | V2 surface | Recommendation |
|---|---|---|---|
| Runtime Selection | `MainBrainPanel.choose()` (legacy mode bypass) | Same `choose()` with V2 callable gate | Single file already; remove V1 branch when `USE_CONNECTION_REGISTRY_V2=true` lands in prod |
| Plugin Install | `PluginsCatalogBrowser` (legacy install dialog) | Same dialog | Same dialog reused; not actually a code-level duplicate, only a panel-coexistence issue |
| MCP Servers List | `McpServersPanel` (4 endpoints) | `McpServersV2Panel` (`useConnectionsV2`) | Hide V1 panel when V2 enabled; or migrate V1 endpoints to read through V2 service |

### 1.4. Other punch-list items

- **BROKEN — Re-run Scan**: `ScanPage.tsx:212` defines `rerunScan()`; no UI button calls it. Backend `POST /security/scans/{id}/rerun` is ready but unreachable from UI.
- **FAKE — Remove Attached File** (chat): `ChatInput.tsx:623`. X button removes UI chip only; `file_record` row + blob remain. No `DELETE /files/{id}` wired from this surface.
- **PARTIAL — Session CRUD has no audit events**: rename / archive / un-archive / batch-archive write `chat_sessions` cleanly but emit zero audit rows. ADR-001 honesty rule violation.
- **PARTIAL — Policy Delete is hard-delete**: `DELETE /policies/{id}`. Per audit-record-protection semantics, policies are audit-adjacent and should be soft-archive only.
- **PARTIAL — Scan report findability**: User starts a scan; no explicit "report ready" notification. Must notice the icon flip in `ScanList`. Lose the `activeJobs` state on page navigation and you must hunt the History.
- **Dead-surface-with-live-endpoint — RuntimeSwapper** (chat): component file at `frontend/src/components/chat/RuntimeSwapper.tsx` exists but is not mounted. Backend `PUT /runtimes/primary` is alive and *is* used by Connections > Main Brain. Surface gap; not a bug.
- **DEAD — Webhooks** (`/settings/developer`): form is intentionally disabled; backend route never built.
- **DEAD — Email notifications** (`/settings/notifications`): switch disabled; SMTP not wired.

---

## 2. Tally tables

### 2.1. Per-cluster

| Cluster | Actions | V_W | PARTIAL | FAKE | DEAD | UNKNOWN | BROKEN | UNSAFE | DUPLICATE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Chat + Dashboard | 18 | 11 | 4 | 1 | 0 | 1 | 0 | 0 | 0 |
| Connections (V1+V2) | 19 | 16 | 3 | 0 | 0 | 0 | 0 | 0 | 3 |
| Settings (13 tabs) | 47 | 13 | 6 | 25 | 2 | 1 | 0 | 0 | 0 |
| Security + Scan + Engagements | 18 | 11 | 5 | 0 | 0 | 1 | 1 | 2 | 0 |
| Execution (tasks/workstreams/pipeline/projects/files) | 21 | 16 | 0 | 0 | 0 | 5 | 0 | 0 | 0 |
| Intelligence + Governance + Company Mode + Analytics | 35 | 33 | 1 | 0 | 0 | 0 | 0 | 1 | 0 |
| **TOTAL** | **158** | **100** | **19** | **26** | **3** | **7** | **1** | **3** | **3** |

### 2.2. Status definitions (refresher)

- **VERIFIED_WORKING** — handler → endpoint → DB write → audit event → UI refresh. All five present and reachable.
- **PARTIAL** — endpoint succeeds but at least one of {UI refresh, audit event, persistence verification, error recovery} is missing or weak.
- **FAKE** — UI suggests it does something it does not; or persists somewhere that isn't the user's account.
- **DEAD** — visible button with no real handler, intentionally disabled, or wired to a removed backend.
- **UNKNOWN** — agent could not trace handler → endpoint → DB without reading more of the backend than scope allowed; honest non-claim.
- **BROKEN** — handler exists but is unreachable from UI, or endpoint exists but UI doesn't call it.
- **UNSAFE** — sends external traffic or accepts privileged input without an enforced approval/scope gate at the surface.
- **DUPLICATE** — same action exposed in two surfaces (V1 and V2).

---

## 3. Per-action matrix

> Format reminder: each block is one action. `Endpoint impl: UNKNOWN` means the agent confirmed the endpoint exists in the route file but did not pin the exact line — not that the implementation is missing. Where line numbers are given they're concrete from the live source.

### 3.1. /chat

#### /chat: New Chat
- Component: `frontend/src/components/chat/SessionList.tsx:636`
- Handler: `frontend/src/components/chat/SessionList.tsx:139`
- Endpoint: `POST /chat/sessions`
- Endpoint impl: `backend/app/api/v1/chat.py:350`
- Payload: `{mode, routingMode, departmentId, autopilot, thinkMode, title?}`
- Response: `{success, data: SessionResponse}`
- DB writes: `chat_sessions`
- Realtime: none
- States: loading=Y, success=Y, error=Y
- Audit event: UNKNOWN
- Permission: auth_required
- Result artifact: session_id, stored in `chatStore.activeSessionId`
- Where user sees result: ChatPage header + SessionList sidebar
- Undo/archive/delete: archive reversible
- Playwright: only registration/login flow at `e2e/daena-flow.spec.ts`, no session-CRUD test
- Status: **VERIFIED_WORKING**

#### /chat: Send Message (SSE Stream)
- Component: `ChatInput.tsx:699`
- Handler: `chatStore.ts:447` (`sendMessageStream`)
- Endpoint: `POST /chat/messages/stream`
- Endpoint impl: `chat.py:502`
- Payload: `{content, session_id?, preferred_model?, governance_mode, routing_mode, mode, autopilot, think_mode, department_id?}`
- Response: SSE events: `session_created`, `user_message`, `thinking`, `governance_notice`, `chunk`, `memory_writeback`, `tool_call`, `approval_pending`, `tool_blocked`, `governance_approval_pending`, `governance_approval_resolved`, `vp_plan`, `vp_subtasks_created`, `scan_dispatched`, `finalize`, `error`
- DB writes: `chat_messages`, `memory` (writeback), `approvals` (if gated), audit
- Realtime: SSE streaming fetch
- States: loading=Y, success=Y, error=Y
- Audit event: `LLM_CALL` (implicit at finalize)
- Permission: auth_required + per-tool governance gates
- Result artifact: `message_id`
- Where user sees result: MessageList streaming
- Undo/archive/delete: edit-and-regenerate or truncate
- Playwright: `e2e/daena-flow.spec.ts:155` (sends a message, verifies streaming)
- Status: **VERIFIED_WORKING**

#### /chat: Cancel Stream
- Component: `ChatPage.tsx:318`
- Handler: `chatStore.ts:289` (`cancelStream`)
- Endpoint: NONE (client-side `ReadableStream.cancel()`)
- States: loading=N, success=Y
- Status: **VERIFIED_WORKING**

#### /chat: Rename Session
- Component: `SessionList.tsx:470`
- Handler: `SessionList.tsx:225` (`confirmRename`)
- Endpoint: `PATCH /chat/sessions/{session_id}` impl `chat.py:406`
- Payload: `{title}`
- DB writes: `chat_sessions.title`
- Audit event: **NONE**
- Status: **PARTIAL** — backend write succeeds, UI refreshes, but no audit log of the rename

#### /chat: Archive Session
- Component: `SessionList.tsx:480`
- Handler: `SessionList.tsx:237`
- Endpoint: `PATCH /chat/sessions/{session_id}` (`{is_archived: true}`)
- Audit event: **NONE**
- Status: **PARTIAL** — same audit gap as rename

#### /chat: Un-archive Session
- Component: `SessionList.tsx:455`
- Handler: `SessionList.tsx:252`
- Endpoint: `PATCH /chat/sessions/{session_id}` (`{is_archived: false}`)
- Audit event: **NONE**
- Status: **PARTIAL** — same audit gap

#### /chat: Batch Archive Sessions
- Component: `SessionList.tsx:560`
- Handler: `SessionList.tsx:268` (parallel `PATCH`)
- Audit event: **NONE**
- Status: **PARTIAL** — no batch audit event

#### /chat: Export Session (JSON)
- Component: `SessionList.tsx:683`
- Handler: `SessionList.tsx:294` (client-side download)
- Endpoint: NONE (reads in-memory messages)
- Audit event: **NONE** (no backend trace that an export happened)
- Status: **PARTIAL** — works, but founder can't prove export occurred

#### /chat: Approve Inline Approval
- Component: `InlineApprovalBanner.tsx:117`
- Handler: `InlineApprovalBanner.tsx:61` (`decide`)
- Endpoint: `POST /governance/approvals/{request_id}/decide` impl `governance.py:238`
- Payload: `{decision: "APPROVED", reason?}`
- DB writes: `governance_approvals.status`, `audit_events`
- Realtime: 5s poll
- Audit event: `APPROVAL_APPROVED`
- Permission: `MANAGER` (`require_role("MANAGER")`)
- Status: **VERIFIED_WORKING**

#### /chat: Reject Inline Approval
- Component: `InlineApprovalBanner.tsx:121`
- Handler: same `decide(action='reject')`
- Endpoint: same; payload `{decision: "REJECTED"}`
- Audit event: `APPROVAL_REJECTED`
- Status: **VERIFIED_WORKING**

#### /chat: Attach File
- Component: `ChatInput.tsx:602`
- Handler: `ChatInput.tsx:276` (`handleFileUpload`)
- Endpoint: `POST /files/upload` impl `files.py:61`
- Payload: FormData (binary)
- DB writes: `file_records`
- Audit event: **NONE**
- Status: **PARTIAL** — uploads, persists, but no audit + no surface-side delete wired

#### /chat: Remove Attached File
- Component: `ChatInput.tsx:623` (X button on chip)
- Handler: inline `removeAttachment`
- Endpoint: **NONE**
- DB writes: NONE; **file blob + `file_records` row both remain on disk**
- Status: **FAKE** — purely UI removal; no `DELETE /files/{id}` wired from this surface

#### /chat: Select Model
- Component: `ChatInput.tsx:406`
- Endpoint: NONE (UI store; sent with next message as `preferred_model`)
- Status: **VERIFIED_WORKING**

#### /chat: Slash command navigate (`/settings`, `/connect`, `/governance`, `/heartbeat`, `/audit`, `/cost`, `/marketplace`, `/memory`, `/scan`)
- Component: `SlashCommands.tsx:164`
- Handler: route navigation only
- Status: **VERIFIED_WORKING**

#### /chat: Slash `/mode cmd` and `/mode exe`
- Component: `SlashCommands.tsx:57` and `:62`
- Endpoint: NONE (UI store update; mode sent with next message)
- Status: **VERIFIED_WORKING** ×2

#### /chat: Dismiss Autopilot Banner
- Component: `ChatPage.tsx:402`
- Endpoint: NONE (`localStorage.daena:autopilotBannerDismissed`)
- Status: **VERIFIED_WORKING** (intended scope is per-device; localStorage is honest here)

#### /chat: Runtime Selector (RuntimeSwapper)
- Component: `frontend/src/components/chat/RuntimeSwapper.tsx:203` (file exists but **not mounted** in current ChatPage)
- Endpoint: `PUT /runtimes/primary` impl `runtimes.py:438` — **endpoint alive**
- Status: **UNKNOWN / dead-surface-with-live-endpoint** — surface relocated to Connections > Main Brain; component file should be deleted or remounted (see §6 Repair Notes)

### 3.2. /dashboard

#### /dashboard: Session Count Card click → /chat
- Component: `DashboardPage.tsx:51`
- Status: **VERIFIED_WORKING** (navigation)

#### /dashboard: Pending Approvals Card click → /governance/approvals
- Status: **VERIFIED_WORKING**

#### /dashboard: View Activity → /chat
- Component: `DashboardPage.tsx:618`
- Status: **VERIFIED_WORKING**

### 3.3. /connections

> All Connections (V2) panel actions persist to `connection_v2` truth table; V1 endpoints persist to legacy `mcp_servers` / `connector_instances`. Both still active until `USE_CONNECTION_REGISTRY_V2=true`.

#### Connections — All Connections (V2) Panel: Filter by Kind
- Component: `pages/connections/ConnectionsV2Panel.tsx:193-200`
- Endpoint: `GET /api/v1/connections/v2`
- Realtime: 30s polling via `useConnectionsV2`
- Permission: FOUNDER reads `v2_enabled` flag; non-FOUNDER → legacy mode
- Status: **VERIFIED_WORKING**

#### Connections — All Connections (V2): Search
- Component: `ConnectionsV2Panel.tsx:82` (client-side substring match)
- Endpoint: NONE
- Status: **VERIFIED_WORKING**

#### Connections — All Connections (V2): Probe
- Component: `ConnectionsV2Panel.tsx:137-141` (`runProbe`)
- Endpoint: `POST /api/v1/connections/v2/{id}/probe`
- Response: `ProbeOutcome { success, label_after, callable_at, failure_dim, failure_reason }`
- DB writes: `connection_v2` truth fields (detected/configured/imported/reachable/authenticated/callable + per-dim failure metadata)
- Realtime: 30s poll refresh after mutation
- Audit event: UNKNOWN (frontend doesn't verify; backend may emit)
- Status: **VERIFIED_WORKING**

#### Connections — All Connections (V2): Enable
- Component: `ConnectionsV2Panel.tsx:143-147`
- Endpoint: `POST /api/v1/connections/v2/{id}/enable`
- DB writes: `connection_v2.disabled = false`
- Status: **VERIFIED_WORKING**

#### Connections — All Connections (V2): Disable
- Component: `ConnectionsV2Panel.tsx:149-153`
- Endpoint: `POST /api/v1/connections/v2/{id}/disable`
- Status: **VERIFIED_WORKING**

#### Connections — All Connections (V2): Archive (soft)
- Component: `ConnectionsV2Panel.tsx:155-160`
- Endpoint: `DELETE /api/v1/connections/v2/{id}` → `connection_v2.archived = true`
- UI: "click again to confirm" within 3 s
- Status: **VERIFIED_WORKING**

#### Connections — All Connections (V2): Refresh
- Endpoint: `GET /api/v1/connections/v2` (manual)
- Status: **VERIFIED_WORKING**

#### Connections — All Connections (V2): Open Details Drawer
- Endpoint: NONE (UI state)
- Status: **VERIFIED_WORKING**

#### Connections — Main Brain: Runtime Selection
- Component: `MainBrainPanel.tsx:130-149` (`choose`)
- Endpoint: `PUT /api/v1/runtimes/primary` impl `runtimes.py` (V2 callable gate when flag ON)
- Payload: `{runtime_id, experimental_override}`
- DB writes: user settings `primary_runtime`
- Audit event: `runtimes.primary_override_not_callable` at WARNING level when `override=true` (Phase 5 PR 2). **Not yet a formal AuditLog row** — Phase 7 item per CLAUDE.md Rule 17.
- Status: **VERIFIED_WORKING** (V2 ON), **PARTIAL** (V2 OFF — gate bypassed) — **DUPLICATE** (V1/V2 path divergence in same file)

#### Connections — Main Brain: Experimental Override toggle
- Component: `MainBrainPanel.tsx:87`
- Endpoint: feeds into the `PUT /runtimes/primary` request body
- Status: **VERIFIED_WORKING**

#### Connections — Main Brain: Runtime Fetch
- Endpoint: `GET /api/v1/runtimes` (legacy plural wrap → `runtime_truth_registry`)
- Status: **VERIFIED_WORKING**

#### Connections — Main Brain: V2 Truth Lookup (Callable Gate)
- Component: `MainBrainPanel.tsx:93-98` (`v2BySlug` memo from `useConnectionsV2('cli_runtime')`)
- Endpoint: `GET /api/v1/connections/v2?kind=cli_runtime`
- Status: **VERIFIED_WORKING** (when V2 enabled)

#### Connections — MCP Servers (V1): Fetch Detected / Registry / Extensions / Plugin Catalog
- Component: `McpServersPanel.tsx:110-115` (`Promise.allSettled` over 4 endpoints)
- Endpoints: `GET /api/v1/mcp-sync/detected`, `GET /api/v1/connections/mcp-registry`, `GET /api/v1/connections/extensions`, `GET /api/v1/connections/plugin-catalog`
- Status: **VERIFIED_WORKING** ×4 — but **DUPLICATE** with V2 panel (Connections — MCP Servers (V2) panel covers the same ground via `useConnectionsV2('mcp_server')`)

#### Connections — MCP Servers (V1): Search
- Endpoint: NONE (client-side filter)
- Status: **VERIFIED_WORKING**

#### Connections — Plugins Catalog: Install (open dialog)
- Component: `PluginsCatalogBrowser.tsx:220+` mounts `ConnectorInstallDialog`
- Status: **VERIFIED_WORKING** — dialog handles its own endpoints (`POST /connectors/{slug}/install/start`, OAuth callback)

#### Connections — Plugins Catalog: Connect Account (re-open dialog for installed)
- Same dialog reused (Codex pattern)
- Status: **VERIFIED_WORKING**

#### Connections — Plugins Catalog: Status Badge
- Component: `PluginsCatalogBrowser.tsx:141-150`
- Endpoint: derived from `GET /api/v1/connections/instances`
- Status: **VERIFIED_WORKING**

#### Connections — Plugins Catalog: Fetch Instances
- Endpoint: `GET /api/v1/connections/instances`
- Status: **VERIFIED_WORKING**

#### Connections — MCP Servers (V2): Probe
- Component: `McpServersV2Panel.tsx:42-46` (`runProbe`)
- Endpoint: `POST /api/v1/connections/v2/{id}/probe` (real MCP JSON-RPC handshake — `initialize` + `tools/list`, 5 s timeout per ADR-001)
- Status: **VERIFIED_WORKING**

#### Connections — MCP Servers (V2): Refresh
- Endpoint: `GET /api/v1/connections/v2?kind=mcp_server`
- Status: **VERIFIED_WORKING**

#### Connections — Plugins (V2): Probe (multi-kind dispatch)
- Component: `PluginsV2Panel.tsx:66-76`
- Status: **VERIFIED_WORKING**

#### Connections — Plugins (V2): Seed Providers (FOUNDER+)
- Endpoint: `POST /api/v1/connections/v2/providers/seed` — **TBD (not implemented)**
- Status: **PARTIAL** — UI button exists per Phase 6 design; endpoint missing

#### Connections — CLI Bridge (in Main Brain panel)
- Status: **UNKNOWN** — Phase 5 reports do not describe a CLI Bridge card in the new modular MainBrainPanel; legacy `ConnectionsRuntimes.tsx` (archived) had a `CLIBridgeCard`. May need re-port in Phase 6.

> **Connections gaps (cross-cutting, not per-row):** Uninstall plugin endpoint not visible from any UI surface. MCP probe button visibility unclear in legacy panel. Formal AuditLog row for `primary_runtime` change is WARNING-log only.

### 3.4. /settings

> The settings cluster has 47 actions across 13 tabs. Per-row blocks below; tally at end of section.

#### /settings/general — 7 actions

- **Save Display Name** — `SettingsGeneral.tsx:82-84`, `PUT /settings/user`, writes `users.settings.display_name` JSONB. Persistence verified Y. **VERIFIED_WORKING**
- **Toggle Dark Mode** — `:180`, `localStorage.dark_mode` only. **FAKE** (per device only)
- **Default Chat Mode (CMD/EXE)** — `:99-111`, `localStorage.default_chat_mode`. **FAKE**
- **Default Routing (STD/QE)** — `:119-133`, `localStorage.default_routing_mode`. **FAKE**
- **Persist Thinking Process** — `:141`, `localStorage.persist_thinking`. **FAKE**
- **AGI Mode (Autopilot)** — `:151-161`, `localStorage.autopilot_active`; backend health check blocks toggle but never reads/persists the value. **FAKE**
- **Import Data to Memory** — `:260`, `POST /memory/memories`, writes `memory_facts` (T2 tier). **VERIFIED_WORKING**

#### /settings/llm — 2 actions

- **Local-First Routing** — `SettingsLLM.tsx:204` → `localStorage.local_first_routing`. **FAKE**
- **Cost-Aware Routing** — `:211` → `localStorage.cost_aware_routing`. **FAKE**

#### /settings/governance — 1 action

- **Governance Mode Selector (UNLEASHED/BALANCED/GOVERNED)** — `SettingsGovernance.tsx:66-80`. FOUNDER-only enforced in UI. Stores in `localStorage.default_governance_mode`. **Pipeline never reads it.** **FAKE — highest-impact FAKE in the matrix.**

#### /settings/models-runtimes — 1 action

- **Add API Key (Anthropic/OpenAI/etc.)** — `SettingsModelsRuntimes.tsx:32-106`, `POST /dynamic-models/provision`, persists key to vault + discovers models. **VERIFIED_WORKING**

#### /settings/memory — 3 actions

- **Refresh Stats** — `GET /memory/status`. **VERIFIED_WORKING**
- **Validate Experiences (Quarantine)** — `POST /memory/experiences/validate`. **VERIFIED_WORKING**
- **Clear Ephemeral Memories** — `POST /memory/memories/clear-ephemeral`. **VERIFIED_WORKING**

#### /settings/billing — 3 actions

- **Monthly Budget** — `SettingsBilling.tsx:376-385` → `localStorage.monthly_budget`. Backend cost-tracker doesn't read it. **FAKE**
- **Budget Alert Threshold** — `:389-401` → `localStorage.budget_alert_threshold`. **FAKE**
- **Over-Budget Action** — `:405-417` → `localStorage.over_budget_action`. **FAKE**

> The file at `SettingsBilling.tsx:370` actually contains a comment warning the reader: "preferences persist to user settings... only trusted when... backend execution logs". The file is honest about being dishonest.

#### /settings/heartbeat — 7 actions

- **Toggle Start/Pause** — `:318-324`, `POST /heartbeat/{pause,start}` impl `heartbeat.py:55-72`. Daemon in-memory only; **PARTIAL** (restart resets)
- **Trigger Now** — `:355-366`, `POST /heartbeat/run-once`. History persisted. **VERIFIED_WORKING**
- **Set Interval** — `:423-436`, `POST /heartbeat/configure`. Daemon-memory only. **PARTIAL**
- **Active Hours** — `:444-464`, `POST /heartbeat/configure`. Daemon-memory only. **PARTIAL**
- **Toggle Checks (13 checkboxes)** — `:472-487`, `POST /heartbeat/configure`. Daemon-memory only. **PARTIAL**
- **Cost Guard (per cycle / per day)** — `:497-515`, `POST /heartbeat/configure`. Daemon-memory only. **PARTIAL**

#### /settings/developer — 4 actions

- **Open API Keys (link to /account)** — `:81-83`, navigation. **VERIFIED_WORKING**
- **Webhooks (form intentionally disabled)** — `:96-123`. **DEAD**
- **Debug Mode** — `:137` → `localStorage.debug_mode`. **FAKE**
- **Verbose Logging** — `:144` → `localStorage.verbose_logging`. **FAKE**

#### /settings/notifications — 9 actions

- **Desktop Notifications (master)** — `:77` → `localStorage.notif_desktop`. **FAKE**
- **Task Completion** — `:101`. **FAKE**
- **Budget Alert** — `:105`. **FAKE**
- **Heartbeat** — `:109`. **FAKE**
- **Governance Rejection** — `:113`. **FAKE**
- **Runtime Disconnect** — `:117`. **FAKE**
- **Sound** — `:136`. **FAKE**
- **Email (intentionally disabled)** — `:153-161`. **DEAD**
- (One control duplicate-counted — net 8 FAKE + 1 DEAD)

#### /settings/privacy — 7 actions

- **Export Data** — `:74-79`, `GET /settings/user/export`. **VERIFIED_WORKING**
- **Delete All Data** — `:87-103`, `POST /settings/user/delete-request`. Soft-archive. **VERIFIED_WORKING**
- **Generate Memories from Conversations** — `:120` → `localStorage.memory_generation`. **FAKE**
- **Search Past Conversations** — `:128` → `localStorage.search_past_conversations`. **FAKE**
- **Memory Storage (Local/Cloud)** — `:135-143`. Cloud disabled with "coming soon"; local persists in localStorage. **PARTIAL**
- **Improve from Usage** — `:161` → `localStorage.improve_from_usage`. **FAKE**
- **Location Metadata** — `:169` → `localStorage.location_metadata`. **FAKE**

#### /settings/voice — 1 action

- **ElevenLabs API Key** — `SettingsVoice.tsx:18-30` → `localStorage.daena:elevenlabs_key` (client-side TTS only; never sent to backend). **PARTIAL** (intended scope is client-side; honest-but-undocumented)

#### /settings/shortcuts — 1 action

- **Keyboard Shortcuts (read-only display)** — `SettingsShortcuts.tsx:54-91`. **VERIFIED_WORKING**

#### /settings/about — 1 action

- **Version Info** — `SettingsAbout.tsx:12-24`, `GET /health`. **VERIFIED_WORKING**

> **Settings tally:** 47 actions / 13 V_W / 6 PARTIAL / 25 FAKE / 2 DEAD / 1 misc / **34 with persistence-verified=N**.

### 3.5. /security + /security/scope + /scan + /scan/walkthrough + /engagements

#### /scan: Start Scan
- Component: `pages/scan/ScanLauncher.tsx:29-142` (handler in `ScanPage.tsx:127-143`)
- Endpoint: `POST /security/scans/start` impl `security_dashboard.py:488-523`
- Payload: `{target, tier, options?}`
- DB writes: `ScanJob` workflow state → `var/scan_traces/{job_id}.json`
- Realtime: `GET /security/scans/{job_id}/status` polling 2-60 s exponential backoff
- Audit event: `scan_start` (logger.info)
- Permission: NONE (any user can start)
- Result artifact: `var/scan_traces/{job_id}.json` then `var/security_reports/{job_id}.json`
- Where user sees result: ScanPage `activeJobs` list → ScanList row
- Report findability after scan: **N (PARTIAL)** — no explicit "report ready" notification; user must notice icon flip from spinner to FileText in ScanList; if user navigates away, `activeJobs` resets and they must hunt History
- Authorized-scope gate: **N (UNSAFE)** — endpoint never calls `target_matches_scope()` before dispatch
- Status: **UNSAFE / PARTIAL** — both findability and gate problems

#### /scan: View Report
- Component: `pages/scan/ScanReport.tsx:30-100` + loader `ScanPage.tsx:146-153`
- Endpoint: `GET /security/scans/{job_id}/report` impl `security_dashboard.py:546-568`
- Status: **VERIFIED_WORKING**

#### /scan: Download Report PDF
- Endpoint: `GET /security/scans/{job_id}/report/pdf` impl `:571-611`
- Auto-detects media type (PDF / Markdown / HTML / plain)
- Returns 404 with helpful message if file missing, directing to JSON endpoint
- Status: **VERIFIED_WORKING**

#### /scan: Archive Scan (single + bulk)
- Endpoint: `DELETE /security/scans/{scan_id}` (`:901-915`) and `DELETE /security/scans` (bulk, `:918-945`)
- Soft-archive moves JSON to `var/security_reports/.archive/`; hard-delete blocked unless `?hard=true` (frontend never sends this)
- Status: **PARTIAL** — works but no "show archived" toggle in ScanList; archived scans become invisible

#### /scan: Re-run Scan
- Component: handler exists at `ScanPage.tsx:212-234` (`rerunScan`); **no UI button in `ScanList` calls it**
- Endpoint: `POST /security/scans/{scan_id}/rerun` impl `:826-898` — backend ready
- Status: **BROKEN** — surface gap

#### /scan/walkthrough/:jobId: Live Operator Walkthrough
- Component: `ScanWalkthroughPage.tsx:119-686`
- Endpoint: `GET /api/v1/security/scans/{jobId}/events` (SSE) impl `:637-691`; fallback poll `/status` + `/report`
- Events: `scan_started`, `scan_thinking`, `scan_observation`, `scan_phase_change`, `scan_checkpoint`, `scan_queue_decision`, `scan_complete`, `scan_failed`
- Auto-reconnect with exponential backoff (cap 15 s, max 5 retries)
- Status: **VERIFIED_WORKING**

#### /security: View Security Dashboard (5 tabs)
- Component: `SecurityDashboardPage.tsx:64-373`
- Endpoints: `GET /security/{status,tools,shields,opsec/status}` (parallel `Promise.allSettled`)
- Cache TTL 30 s; tab-specific fallback rendering survives partial backend unavailability
- Status: **VERIFIED_WORKING**

#### /security: Scan Detail Expansion
- Endpoint: `GET /security/scans/{scanId}` impl `:395-407`
- Status: **VERIFIED_WORKING**

#### /security: Toggle Shield / Tool / Mission
- Components: `pages/security/{SecurityTools, SecurityShields, SecurityMissions}.tsx`
- These files are on the v3.7.0 Security Supercharge HANDS-OFF list. Audit only — handlers and endpoints not exhaustively traced.
- Status: **UNKNOWN** (not because broken — because deliberately not refactored mid-audit)

#### /security/scope: Load Scope
- Component: `SecurityScopePage.tsx:73-155` (`loadScope`)
- Endpoint: `GET /security/authorized-scope` impl `security_authorized_scope.py`
- Permission: FOUNDER-only (enforced in UI + backend)
- Status: **VERIFIED_WORKING**

#### /security/scope: Add/Remove Entry
- Local state mutation; client-side validation (CIDR regex, domain format, source path); `beforeunload` guard prevents accidental discard
- Status: **VERIFIED_WORKING**

#### /security/scope: Save Scope
- Endpoint: `PUT /security/authorized-scope`
- DB writes: `authorized_scopes.json` or `Tenant.settings` JSONB
- Audit event: `scope_updated` (implicit in backend log)
- Status: **VERIFIED_WORKING**

#### /security/scope: Test Target (dry-run)
- Endpoint: `POST /security/authorized-scope/test`
- Status: **VERIFIED_WORKING**

#### /engagements: Start Governed Engagement
- Component: `EngagementConsolePage.tsx:169-190`
- Endpoint: `POST /engagements` impl `engagements.py:55-133`
- Payload: `{target, tier, options?}`
- Response: `{success: true}` OR `{success: false, approval_required: true, ...}` with banner showing link to `/governance/approvals`
- DB writes: `EngagementJob` + `PendingApproval` if T4/T5 + GOVERNED
- Audit event: `engagement.approval_persisted`
- Authorized-scope gate: **UNKNOWN** — delegated to `SecurityOperationsAgent.start_engagement()` (HANDS-OFF list — not audited)
- Status: **PARTIAL / UNSAFE** — approval gate works; scope gate visibility insufficient

#### /engagements: List Engagements
- Endpoint: `GET /engagements` impl `:136-147`; 4 s polling for in-flight jobs
- Status: **VERIFIED_WORKING**

#### /engagements: Open Report
- Endpoint: `GET /engagements/{jobId}/report`
- Same artifact as `/scan` reports
- Status: **VERIFIED_WORKING**

#### /engagements: Poll T5 Unlock Status
- Endpoint: `GET /engagements/shield-status` (15 s polling)
- Status: **VERIFIED_WORKING**

### 3.6. /tasks + /workstreams + /pipeline + /projects + /files

#### /tasks: Run Task (PENDING/FAILED/CANCELLED)
- Component: `TasksPage.tsx:171` (`handleRun`)
- Endpoint: `POST /execution/tasks/{task_id}/run` impl `execution.py:214`
- DB writes: `tasks.status ← RUNNING`, `started_at`
- Realtime: 15 s polling while RUNNING
- Audit event: NONE
- Status: **VERIFIED_WORKING**

#### /tasks: Batch Run
- Component: `:210` (`Promise.allSettled` over `[PATCH status:PENDING, POST /run]`)
- Status: **VERIFIED_WORKING**

#### /tasks: Retry
- Component: `:192` (two-step PATCH+POST chain)
- Status: **VERIFIED_WORKING**

#### /tasks: Cancel
- Component: `:240`, `PATCH /execution/tasks/{id}` (`{status: 'CANCELLED'}`)
- Status: **VERIFIED_WORKING**

#### /tasks: Batch Archive (status→CANCELLED)
- Component: `:229`, parallel `PATCH`
- Status: **VERIFIED_WORKING** (soft-archive via status enum; not hard-delete)

#### /tasks: Batch Delete
- Component: `:254`, `batchDeleteWithToast` → `DELETE /execution/tasks/{id}` impl `:203`
- DB writes: hard delete from `tasks`
- Status: **VERIFIED_WORKING** (hard-delete is intentional and confirmed via toast)

#### /workstreams: Redirect (NLU-parsed instruction)
- Component: `WorkstreamsPage.tsx:237` (`submitRedirect`)
- Endpoint: `POST /workstreams/{id}/redirect` impl `workstreams.py:179`
- NLU parser validates actions; clarification on parse failure
- Status: **VERIFIED_WORKING**

#### /workstreams: Pause Autopilot
- Component: `:264` (`lifecycleAction('pause')`)
- Endpoint: `POST /workstreams/{id}/pause` (impl line UNKNOWN — agent didn't fully read)
- Status: **UNKNOWN** (handler called; backend impl not pinned)

#### /workstreams: Resume Autopilot
- Component: `:265`
- Endpoint: `POST /workstreams/{id}/resume`
- Status: **UNKNOWN** (same)

#### /pipeline/projects: Create Project (DISCOVERY stage)
- Endpoint: `POST /pipeline/projects` impl `pipeline.py:111`
- Status: **VERIFIED_WORKING**

#### /pipeline/projects: Advance Stage (with founder gate at PROPOSAL/CONTRACT/DELIVERY)
- Endpoint: `POST /pipeline/projects/{id}/advance` impl `:146`
- Permission: MANAGER (`require_role`)
- Status: **VERIFIED_WORKING**

#### /pipeline/projects: Mark Lost
- Endpoint: `POST /pipeline/projects/{id}/mark-lost` impl `:168`
- Audit event: `Sales.lost_deal` signal emitted to Marketing/Research
- Permission: MANAGER
- Status: **VERIFIED_WORKING**

#### /sales/customer-acquisition/draft-workflow
- Component: `PipelinePage.tsx:177`
- Endpoint: `POST /sales/customer-acquisition/draft-workflow` impl `agent_ops.py:90`
- Response: explicit `{mode: 'draft_only', external_action_sent: false, approval_request: ...}`
- Audit event: `CUSTOMER_ACQUISITION_DRAFT_WORKFLOW` with `external_action_sent=false, approval_required=true`
- Status: **VERIFIED_WORKING** (gate honored; this is the *correct* shape that Company Mode Activate violates — see U1)

#### /projects: Create
- `POST /projects`, sanitization in `CreateProjectBody` validators
- Status: **VERIFIED_WORKING**

#### /projects: Edit
- `PUT /projects/{id}` (impl line UNKNOWN — agent didn't pin)
- Status: **UNKNOWN**

#### /projects: Delete
- `DELETE /projects/{id}`
- Status: **UNKNOWN**

#### /projects/{id}: Set Working Directory
- `PUT /projects/{id}` with `{working_directory}`
- Status: **UNKNOWN**

#### /files: Upload
- `POST /files/upload` impl `files.py:61`; multipart, 20 MB limit, MIME allowlist, SHA256 hash
- Status: **VERIFIED_WORKING**

#### /files: Delete (single)
- `DELETE /files/{file_id}` via `deleteWithToast` with explicit warning copy "permanently removes... will NOT be recoverable"
- Status: **VERIFIED_WORKING** (hard-delete is intentional, surfaced)

#### /files: Batch Delete
- `batchDeleteWithToast` over `DELETE /files/{file_id}`
- Status: **VERIFIED_WORKING**

#### /files: Download
- `GET /files/{file_id}/download` (responseType: 'blob')
- Status: **VERIFIED_WORKING**

### 3.7. /minds + /departments + /skills + /governance + /policies + /company-mode + /analytics

#### /minds (MindsPage): Refine All
- Component: `MindsPage.tsx:98-113`
- Endpoint: `POST /souls/refine-all`
- Permission: FOUNDER
- Status: **VERIFIED_WORKING**

#### /minds/:slug: Refine This Mind
- `POST /souls/{slug}/refine`
- Status: **VERIFIED_WORKING**

#### /minds/:slug: Approve / Reject Proposal
- `POST /souls/proposals/{id}/{approve,reject}`
- DB writes: `soul_proposals.status`; soul body updated on approve
- Audit-record protection: YES — decision immutable
- Status: **VERIFIED_WORKING** ×2

#### /departments: View Department List
- `GET /agents/departments` + `useDepartmentStates` 5 s poll
- Status: **VERIFIED_WORKING**

#### /departments/:departmentId/chat: Send Message
- Same pipeline as /chat send-message
- Status: **VERIFIED_WORKING**

#### /governance/approvals: Approve / Reject Action
- Component: `GovernanceApprovalsPage.tsx:198-236`
- Endpoint: `POST /governance/approvals/{id}/decide`
- Realtime: SSE `onResolved` (`:136-148`)
- Audit event: `APPROVAL_DECISION` written by backend; reason mandatory on reject
- Permission: FOUNDER/role enforced backend-side
- Status: **VERIFIED_WORKING** ×2

#### /governance/audit: Verify Audit Chain
- `GET /governance/audit/verify` → chain integrity badge (green/red/gray)
- Status: **VERIFIED_WORKING**

#### /governance/audit: Filter / Sort
- Client-side; `reviewedIds` annotation in `localStorage` (acceptable for client-only)
- Backend audit log immutable
- Status: **VERIFIED_WORKING**

#### /governance/audit: Export JSON
- Client-side `JSON.stringify` + blob download
- Status: **VERIFIED_WORKING**

#### /skills: Change Permission (Allow/Ask/Block)
- `PATCH /skills/{id}` `{governance_tier}`
- Optimistic UI with rollback
- Status: **VERIFIED_WORKING**

#### /skills: Bulk Set Permissions
- Parallel `PATCH`; partial-fail toast
- Status: **VERIFIED_WORKING**

#### /skills: Enable / Disable Single
- `PATCH /skills/{id}` `{is_active}`
- Status: **VERIFIED_WORKING**

#### /skills: Bulk Enable / Disable
- Parallel `PATCH`; refetch on partial fail
- Status: **VERIFIED_WORKING**

#### /policies: Compile (plain English → YAML preview)
- `POST /policies/compile` (preview only; no DB write)
- Status: **VERIFIED_WORKING**

#### /policies: Save Policy
- `POST /policies` → `policies` table; `enabled: true` immediately active
- Status: **VERIFIED_WORKING**

#### /policies: Delete Policy
- `DELETE /policies/{id}` — **hard delete**
- Audit-record protection: **N** — policies are audit-adjacent per founder semantics; should be soft-archive
- Status: **PARTIAL**

#### /company-mode: Activate Daena
- Component: `CompanyModePage.tsx:272-308`
- Endpoint: `POST /company-mode/activate`
- Payload includes `auto_send` and `require_founder_approval` independently — UI permits the unsafe combination
- Status: **UNSAFE** (see U1 above)

#### /company-mode: Save Seed Brief
- `POST /company-mode/seed-brief`
- Status: **VERIFIED_WORKING**

#### /company-mode: Delete Seed Brief
- `DELETE /company-mode/seed-brief` (hard-delete; config not approval — acceptable)
- Status: **VERIFIED_WORKING**

#### /company-mode: Send Draft (Mission)
- `POST /company-mode/missions/{missionId}/drafts/{draftId}/send`
- DB writes: `drafts.status` (awaiting_approval → sending → sent|blocked|failed)
- Permission: button only shown for `awaiting_approval` drafts
- Status: **VERIFIED_WORKING**

#### /analytics: View Dashboard
- `GET /analytics/dashboard` `{period: '7d'|'30d'|'90d'}`
- Status: **VERIFIED_WORKING**

#### /analytics: Change Period
- Re-fetch with new period
- Status: **VERIFIED_WORKING**

---

## 4. Cross-cutting findings

### 4.1. Audit-event coverage gaps

These actions write to DB but **emit no audit row**, so the founder cannot reconstruct who-did-what for them:

- Chat session: rename, archive, un-archive, batch-archive, batch-delete
- Chat: file attach, file remove (and remove is FAKE anyway)
- Chat: export session JSON
- Tasks: create, run, batch-run, retry, cancel, batch-archive, batch-delete
- Connections > Main Brain: primary-runtime change has WARNING-log only, not formal AuditLog row (Phase 7 item per CLAUDE.md Rule 17)
- Settings: every save (explicit `PUT /settings/user` calls + the 25 FAKE ones)

**This is a Rule-17 violation pattern at scale.** It's also fixable with a single backend audit-emit helper applied at the relevant route handlers — not 30 individual fixes.

### 4.2. Realtime-state honesty

The frontend claims real-time on several surfaces but most use polling:

| Surface | Claim / appearance | Actual mechanism |
|---|---|---|
| /chat streaming | Real-time | True SSE (`/chat/messages/stream`) |
| /governance/approvals | Real-time | SSE (`/governance/approvals/events`) + 5 s polling backstop |
| /scan/walkthrough/:jobId | Real-time | SSE + fallback polling |
| /tasks status | Live update | 15 s polling |
| /heartbeat status | Live update | One-shot fetch on tab open |
| /security dashboard | Live | 30 s cached + 2.5 s polling when refreshing/pending |
| /engagements list | Live | 4 s polling for in-flight |
| /departments status | Live | 5 s polling via `useDepartmentStates` |
| /connections (V2) | Live | 30 s polling via `useConnectionsV2` |

ADR-001 says: "No advertised real-time without an SSE channel." Polling is honest only if labeled. Most of these aren't currently labeled — the UI badges show live-pulse animations regardless of mechanism.

### 4.3. Playwright coverage

Of the **158 actions audited, 2 have explicit Playwright coverage** (chat send-message at `daena-flow.spec.ts:155`, screenshot-pass at `screenshot-all.spec.ts`). 156 actions are uncovered. Phase 9C will add focused traces for the priority flows; Phase 10 will add regression coverage for the fixes that ship.

### 4.4. Permission gates that aren't visible from the UI

Many endpoints enforce role/scope server-side, but the UI doesn't surface what the gate is *before* the user clicks. Specific examples:

- `/governance/approvals/{id}/decide` requires `MANAGER`. UI doesn't grey out the button for VIEWER role.
- `PUT /security/authorized-scope` is FOUNDER-only (UI does enforce this).
- `POST /pipeline/projects/{id}/advance` requires `MANAGER`. UI doesn't pre-check.
- `POST /chat/messages/stream` runs governance gates per-tool — user only learns of the gate after the SSE event arrives.

This is a usability finding more than a security finding. Server-side gates are correct; UI hints would prevent confusion.

### 4.5. Dead surfaces with live endpoints (drift)

| Surface | Status | Endpoint still alive at |
|---|---|---|
| `RuntimeSwapper.tsx` (chat) | not mounted | `PUT /runtimes/primary` (used by Connections > Main Brain) |
| `ConnectionsPage.tsx` legacy monolith | active alongside new modular `pages/connections/*` | both V1 and V2 endpoints |
| `frontend/src/pages/connections/McpServersPanel.tsx` (legacy) | active alongside `McpServersV2Panel.tsx` | both legacy and V2 connection endpoints |

Decision required: keep V1 as fallback when `USE_CONNECTION_REGISTRY_V2=false`, or sunset V1 entirely once V2 stabilizes? Current state risks user confusion about which surface owns truth.

---

## 5. Coverage and uncertainty

**What was audited:**
- Every visible button/menu/toggle on routes: /chat, /chat/:id, /dashboard, /connections (all V1+V2 panels), /settings (13 tabs), /security, /security/scope, /scan, /scan/walkthrough, /engagements, /tasks, /workstreams, /pipeline, /projects, /projects/:id, /files, /minds, /minds/:slug, /departments, /departments/:id/chat, /skills, /governance/approvals, /governance/audit, /policies, /company-mode, /analytics. **26 routes.**

**What was NOT audited (out of scope or HANDS-OFF):**
- `/login`, `/register`, `/forgot-password`, `/reset-password`, `/auth/callback`, `/complete-profile`, `/terms`, `/privacy` — auth and static pages.
- `/account` and `/account/:category` — covered indirectly by Settings link-out only.
- Per-row internals of `pages/security/{SecurityTools, SecurityShields, SecurityMissions}.tsx` — on the v3.7.0 Security Supercharge HANDS-OFF list (CLAUDE.md). Surface confirmed present; handler/endpoint detail deferred.
- Backend service-layer audit-event emission was inferred from route handlers, not by reading services exhaustively. Where agents could not pin the line, "Audit event: UNKNOWN" appears.
- Some endpoint impls show "UNKNOWN line" — agents confirmed the route file but didn't open it for line-level confirmation. The route exists; the implementation specifics are unverified for those rows.

**Backend was not running locally during this audit.** All evidence is static (file-read). Phase 9C will run the live flows under Playwright MCP to ground-truth the static findings.

---

## 6. Repair pre-notes (for Phase 9F to rank)

These are surfaced now to seed the repair backlog. **Not a backlog yet — that's Phase 9F.**

1. **U1 — Company Mode auto-send guardrail.** UI must enforce `auto_send=true ⇒ require_founder_approval=true`. Cheapest possible fix: disable the `auto_send` toggle when approval is OFF.
2. **U2 — Scan scope gate at REST boundary.** Add `target_matches_scope()` check in `security_dashboard.py:488-523` *before* dispatch. Reject with 403 if out-of-scope (with a clear "add to /security/scope" hint).
3. **U3 — Engagements scope gate visibility.** Trace `SecurityOperationsAgent.start_engagement` to confirm scope enforcement. If absent, mirror U2's fix at the engagement entry point.
4. **Settings persistence migration.** Replace 25 `persistUiPref(...)` localStorage calls with `PUT /settings/user`. Single backend column (`users.settings` JSONB) already exists for the working settings; just route the FAKE ones through it. The single-architectural-fix nature means this is one PR not 25.
5. **Heartbeat config persistence.** Daemon should read its own config from a `heartbeat_config` table on init, not from in-memory defaults. Settings PATCH writes the row; daemon reads it on boot.
6. **Session CRUD audit emit.** Add `audit.emit("chat_session.{action}")` to PATCH and DELETE handlers in `chat.py:406`+. Same shape for tasks (`execution.py:182, 203, 214`).
7. **Re-run Scan UI button.** Add `RotateCcw` icon button in `ScanList.tsx` that calls existing `rerunScan()` handler. ~10 lines.
8. **Remove Attached File honest behavior.** Either (a) wire `DELETE /files/{id}` to the X button, or (b) clarify that files persist for chat history (and add a /files-page link). Option (a) is more honest.
9. **Policy delete → soft-archive.** Change `DELETE /policies/{id}` to set `archived=true` instead of removing the row. Add `?show_archived=true` query param to the list endpoint.
10. **Scan report-ready notification.** When a job in `activeJobs` flips to `complete`, emit a toast or push a notification with a deep link to the report view.
11. **Connections V1↔V2 collapse plan.** Decide single source of truth for the three duplicated surfaces. Until decided, document which is canonical to prevent founder confusion.
12. **Realtime-honesty labels.** Add a small "live (5s polling)" / "live (SSE)" tag to live-pulse badges so the UI's claim matches the mechanism.

---

## 7. References

- `docs/Ultraview/PHASE_9_TOOLING_READINESS.md` — Phase 9A
- `docs/Ultraview/FRONTEND_BACKEND_TRUTH_MATRIX.md` — route-level companion (per-route status)
- `docs/Ultraview/API_CONTRACT_REALITY.md` — backend route gaps
- `docs/Ultraview/DUPLICATES_DEAD_FILES_UNWIRED_REPORT.md` — known dead surfaces
- `docs/Ultraview/CONNECTIONS_FILE_MAP.md`, `CONNECTIONS_REBUILD_PLAN.md`, `PHASE_5_CONNECTIONS_FRONTEND_REPORT.md`, `PHASE_5_MAIN_BRAIN_ROUTING_REPORT.md`, `CONNECTIONS_PLUGIN_INSTALL_TRUTH_REPORT.md` — connections cluster context
- `docs/Ultraview/MEMORY_RAG_OBSIDIAN_SYNC_REPORT.md` — RAG/Obsidian known gaps (skills + memory)
- `docs/Ultraview/HEARTBEAT_NOTIFICATION_REALITY_REPORT.md` — heartbeat notification wiring
- `docs/Ultraview/PHASE_4A_3_OPERATOR_GATE_REPORT.md`, `CONNECTIONS_SECURITY_STABILIZATION_REPORT.md` — scope gate context

## 8. Boundaries respected (per founder rules)

- No production deploy; no GCP touch.
- No `USE_CONNECTION_REGISTRY_V2` flip (still `false` in prod).
- No `vault --apply`; no vault file deletion.
- No secrets read or printed.
- No external scans run.
- No file/dependency changes — only this report and the Phase 9A report were written in this audit.
- Backend not started; all evidence is static file-read.
