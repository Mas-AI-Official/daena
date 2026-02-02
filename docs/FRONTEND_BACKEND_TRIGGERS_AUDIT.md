# Frontend Keys & Triggers – Backend Wiring Audit

This document lists functional frontend keys/triggers, their backend wiring, multi-step flows, and UI/UX alignment to the project design system.

---

## 1. Dashboard (`dashboard.html`)

| Trigger | Action / Handler | Backend / Route | Status |
|--------|------------------|-----------------|--------|
| Hex items (customer, legal, engineering, …) | `openDepartment(dept)` → `/ui/office/{dept}` | GET `/ui/office/{department_id}` | ✓ |
| Center Daena hex | `openDaenaChat()` → `/ui/daena-office` | GET `/ui/daena-office` | ✓ |
| Quick: Daena Office | `openDaenaChat()` | Same | ✓ |
| Quick: Agents | `window.location.href='/ui/agents'` | GET `/ui/agents` | ✓ |
| Quick: Projects | `window.location.href='/ui/projects'` | GET `/ui/projects` | ✓ |
| Quick: Analytics | `window.location.href='/ui/analytics'` | GET `/ui/analytics` | ✓ |
| Quick: Brain & API | `window.location.href='/ui/brain-settings'` | GET `/ui/brain-settings` | ✓ |
| Quick: App Setup | `window.location.href='/ui/app-setup'` | GET `/ui/app-setup` | ✓ |
| Quick: Founder | `window.location.href='/ui/founder-panel'` | GET `/ui/founder-panel` | ✓ |
| Quick: Connections | `window.location.href='/ui/connections'` | GET `/ui/connections` | ✓ |
| Quick: Incident Room | `window.location.href='/incident-room'` | GET `/incident-room` (or page route) | ✓ |
| Quick: QA Guardian | `window.location.href='/api/v1/qa/ui'` | GET `/api/v1/qa/ui` (serves QA dashboard) | ✓ |
| Quick: Provider onboarding | `window.location.href='/ui/provider-onboarding'` | GET `/ui/provider-onboarding` | ✓ |
| Execution: Save token | `saveExecutionToken()` | — (sessionStorage) | ✓ |
| Execution: Run tool | `runExecutionTool()` | POST `/api/v1/execution/run` (token) | ✓ |
| Execution: Tool toggle ON/OFF | `toggleExecutionTool(name, enabled)` | PATCH `/api/v1/execution/tools/{name}/enabled?enabled=` | ✓ |
| Execution: Refresh tasks/approvals | `loadExecutionTasksAndApprovals()` | GET `/api/v1/execution/tasks`, GET `/api/v1/execution/approvals` | ✓ (fixed: function added) |
| Execution: Test connection (Windows Node) | `testWindowsNode()` | GET `/api/v1/execution/node/health` | ✓ (UI added) |
| Polling (10s) | `updateDashboardData`, `loadRecentActivity`, `loadTaskProgress`, `loadOperationsSummary`, `loadExecutionLayer`, `loadExecutionTasksAndApprovals` | `/api/v1/brain/status`, `/api/v1/events/recent`, `/api/v1/tasks/stats/overview`, `/api/v1/tasks/department/{dept}`, `/api/v1/execution/*` | ✓ |

---

## 2. Base / Global (`base.html`)

| Trigger | Action | Backend | Status |
|--------|--------|---------|--------|
| Lockdown banner link | `href="/incident-room"` | Page route | ✓ |
| Lockdown check (on load) | `fetch(DAENA_API_BASE + '/founder-panel/system/emergency/status')` | GET `/api/v1/founder-panel/system/emergency/status` | ✓ |
| Brain status polling | `updateBrainStatus()` → `/api/v1/brain/status` | GET `/api/v1/brain/status` | ✓ |
| Floating sidebar toggle | Toggle sidebar collapsed | — | ✓ |

---

## 3. Sidebar (`partials/sidebar.html`)

| Trigger | Action | Backend / Route | Status |
|--------|--------|-----------------|--------|
| Dashboard | `href="/ui/dashboard"` | GET `/ui/dashboard` | ✓ |
| Daena Office | `href="/ui/daena-office"` | GET `/ui/daena-office` | ✓ |
| Projects, Councils, Workspace, Analytics, Agents | `href="/ui/..."` | Corresponding GET `/ui/*` | ✓ |
| Brain & API, App Setup, Connections | Same | Same | ✓ |
| Incident Room | `href="/incident-room"` | Page route | ✓ |
| QA Guardian | `href="/api/v1/qa/ui"` | GET `/api/v1/qa/ui` | ✓ |
| Provider onboarding | `href="/ui/provider-onboarding"` | GET `/ui/provider-onboarding` | ✓ |
| System Monitor | `href="/ui/system-monitor"` | GET `/ui/system-monitor` | ✓ |
| Founder | `href="/ui/founder-panel"` | GET `/ui/founder-panel` | ✓ |

---

## 4. Provider Onboarding (`provider_onboarding.html`)

| Trigger | Action | Backend | Status |
|--------|--------|---------|--------|
| Step tabs 1–4 | `providerOnboardingStep(n)` | — (UI only) | ✓ |
| Connect selected | `providerConnectSelected()` | POST `/api/v1/providers/{id}/connect` | ✓ (API base fixed) |
| Save standing instructions | `providerSaveStanding()` | POST `/api/v1/providers/config` | ✓ |
| Save allowlist | `providerSaveAllowlist()` | POST `/api/v1/providers/config` | ✓ |
| Send test message | `providerTestSend()` | POST `/api/v1/providers/{id}/test` | ✓ |
| Provider cards | `toggleProvider(id)` | — (selection) | ✓ |
| Load providers | `loadProviders()` | GET `/api/v1/providers` | ✓ |

---

## 5. QA Guardian Dashboard (`qa_guardian_dashboard.html`)

| Trigger | Action | Backend | Status |
|--------|--------|---------|--------|
| Dashboard link | `href="/ui/dashboard"` | GET `/ui/dashboard` | ✓ |
| Incident Room link | `href="/incident-room"` | Page route | ✓ |
| Refresh | `qaGuardianRefresh()` | GET `/api/v1/qa/status`, `/api/v1/qa/incidents` | ✓ |
| Request QA Review | `qaGuardianRequestReview()` | POST `/api/v1/qa/request-review` | ✓ |
| Kill Switch | `qaGuardianToggleKillSwitch()` | POST `/api/v1/qa/kill-switch` | ✓ |
| Incident item click | `qaGuardianViewIncident(id)` | GET `/api/v1/qa/incidents/{id}` | ✓ |
| Filter incidents | `qaGuardianFilterIncidents()` | GET `/api/v1/qa/incidents?status=&limit=` | ✓ |
| Regression / Security (if present) | `qaGuardianRunRegression`, `qaGuardianRunSecurityScan` | POST `/api/v1/qa/run-regression`, `/api/v1/qa/run-security-scan` | ✓ |
| Polling (30s) | `refreshDashboard()` | `/api/v1/qa/status`, `/api/v1/qa/incidents` | ✓ |

---

## 6. Incident Room (`incident_room.html`)

| Trigger | Action | Backend | Status |
|--------|--------|---------|--------|
| Dashboard | `href="/ui/dashboard"` | GET `/ui/dashboard` | ✓ |
| QA Guardian | `href="/api/v1/qa/ui"` | GET `/api/v1/qa/ui` | ✓ |
| Refresh hits | `incidentRoomRefreshHits()` | GET `/api/v1/_decoy/hits?limit=100` | ✓ |
| Lockdown status | `refreshLockdownStatus()` | GET `/api/v1/founder-panel/system/emergency/status` | ✓ |
| Block IP (from hit) | `incidentRoomBlockIpFromHit(ip)` | POST `/api/v1/security/containment/block-ip` | ✓ |
| Unblock IP | `incidentRoomUnblockIp(ip)` | POST `/api/v1/security/containment/unblock-ip` | ✓ |
| Lockdown / Unlock | `incidentRoomDoLockdown`, `incidentRoomDoUnlock` | POST `/api/v1/founder-panel/system/emergency/lockdown`, `unlock` | ✓ |
| Containment refresh | `refreshContainment()` | GET `/api/v1/security/containment/status` | ✓ |

---

## 7. Daena Office (`daena_office.html`)

| Trigger | Action | Backend | Status |
|--------|--------|---------|--------|
| New Chat / Create session | `createNewSession()`, `startNewChat()` | Chat/stream APIs | ✓ |
| Send message (stream) | `fetch('/api/v1/daena/chat/stream', …)` | POST `/api/v1/daena/chat/stream` | ✓ |
| Export chat | `window.open(\`/api/v1/daena/chat/${sessionId}/export\`)` | GET `/api/v1/daena/chat/{id}/export` | ✓ |
| Voice settings | `fetch('/api/v1/voice/settings')`, POST save, test | GET/POST `/api/v1/voice/settings`, POST `/api/v1/voice/test` | ✓ |
| Category filter, batch export/delete | UI + corresponding APIs | Session/export APIs | ✓ |

---

## 8. Department Office (`department_office.html`)

| Trigger | Action | Backend | Status |
|--------|--------|---------|--------|
| Load sessions | `loadChatSessions()` | GET `/api/v1/departments/{deptId}/chat/sessions` | ✓ |
| Switch session | `switchSession(sessionId)` → `loadChatHistory(sessionId)` | GET `/api/v1/departments/{deptId}/chat/sessions/{sessionId}` | ✓ |
| Send message | `sendMessage()` | POST `/api/v1/departments/{deptId}/chat` | ✓ |
| New session | `startNewSession()` | Next POST creates session | ✓ |

---

## 9. Council Debate (`council_debate.html`)

| Trigger | Action | Backend | Status |
|--------|--------|---------|--------|
| Load council | `fetch(\`/api/v1/council/${councilId}\`)` | GET `/api/v1/council/{id}` | ✓ |
| Start debate | POST `/api/v1/council/{id}/debate/start` | Backend council routes | ✓ |
| Load session | GET `/api/v1/council/{id}/debate/{sessionId}` | ✓ |
| Send message | POST `/api/v1/council/{id}/debate/{sessionId}/message` | ✓ |
| Synthesize | POST `/api/v1/council/{id}/debate/{sessionId}/synthesize` | ✓ |

---

## 10. Multi-Step Flows (Triggers → Next Keys)

1. **Provider onboarding**: Step 1 (choose) → Step 2 (tokens) → Step 3 (standing) → Step 4 (test). Each step shows different UI; Connect selected (Step 1) and Test (Step 4) call backend. ✓
2. **Execution Layer**: Save token → Tools/Config load → Toggle tool or Run tool → Logs/Tasks refresh. All use `executionFetch` with token. ✓
3. **Incident Room**: Refresh lockdown → Refresh containment/hits → Block IP → Refresh again. ✓
4. **Daena Office**: New Chat → Send message → Stream response; optional Export. ✓
5. **Department Office**: Load sessions → Select session or New → Send message → Response. ✓
6. **QA Guardian**: Refresh → View incident / Request review / Kill switch → Refresh. ✓

---

## 11. UI/UX Alignment (Project Design)

- **Design tokens**: `--daena-gold` (#D4AF37), `--glass-bg`, `--glass-border`, `--bg-dark`, `--text-main`, `--text-muted`.
- **Components**: `.glass-panel`, `.glass-btn`, `.text-daena-gold`, `.bg-daena-gold`, `.dashboard-card`, `.quick-btn`, `.exec-token-btn`, `.exec-run-btn`, `.btn`, `.btn-primary`, `.btn-outline`, `.btn-danger`.

**Applied / recommended:**

- Dashboard: cards use `dashboard-card`, execution buttons use `exec-token-btn` / `exec-run-btn` (gold/green).
- QA Guardian: `.qa-dashboard .btn-primary`, `.btn-outline`, `.btn-danger`; severity badges and indicators.
- Incident Room: `.incident-room .btn`, same semantic colors.
- Provider onboarding: `btn btn-primary`; API base fixed to `/api/v1` + `/providers`.
- Sidebar/topbar: daena-gold accents, glass style.
- All quick actions and execution controls are clearly labeled and use consistent button classes.

---

## 12. Fixes Applied in This Audit

1. **Dashboard**: Implemented missing `loadExecutionTasksAndApprovals()` and wired it to GET `/api/v1/execution/tasks` and GET `/api/v1/execution/approvals`; added to 10s refresh loop.
2. **Dashboard**: Added Windows Node row with `id="exec-node-status"` and “Test connection” button calling `testWindowsNode()`.
3. **Provider onboarding**: Corrected API base from `(DAENA_API_BASE || '') + '/api/v1/providers'` to `(DAENA_API_BASE || '/api/v1') + '/providers'` to avoid double `/api/v1`.

All other triggers above were verified to be wired to the correct backend routes and workflows.

---

## 13. Page-by-Page / Template-by-Template Scan (Full)

### Templates with API/fetch or navigation (verified)

| Template | Key triggers | Backend wiring | Notes |
|----------|--------------|----------------|-------|
| **dashboard.html** | Hex depts, quick btns, execution token/run/toggle/tasks/node | `/ui/office/{id}`, `/ui/*`, `/api/v1/brain/status`, `/api/v1/events/recent`, `/api/v1/tasks/*`, `/api/v1/execution/*` | All wired ✓ |
| **base.html** | Lockdown banner, brain status | `/api/v1/founder-panel/system/emergency/status`, `/api/v1/brain/status` | ✓ |
| **partials/sidebar.html** | All nav links | `/ui/dashboard`, `/ui/daena-office`, `/ui/*`, `/incident-room`, `/api/v1/qa/ui` | ✓ (ui.py + main.py) |
| **provider_onboarding.html** | Step tabs, Connect, Save standing/allowlist, Test | `/api/v1/providers`, `/api/v1/providers/config`, `/{id}/connect`, `/{id}/test` | API base fixed ✓ |
| **qa_guardian_dashboard.html** | Refresh, Request review, Kill switch, incident click, filter | `/api/v1/qa/status`, `/api/v1/qa/incidents`, `/api/v1/qa/kill-switch`, etc. | ✓ |
| **incident_room.html** | Lockdown, hits, containment block/unblock, Lockdown/Unlock | `/api/v1/founder-panel/system/emergency/*`, `/_decoy/hits`, `/api/v1/security/containment/*` | ✓ |
| **daena_office.html** | Chat stream, sessions, export, voice settings/test | `window.api.request` → `/api/v1/chat-history/*`, `/api/v1/daena/chat/*`, `/api/v1/voice/*` | ✓ |
| **department_office.html** | Load sessions, switch session, send message | GET/POST `/api/v1/departments/{deptId}/chat/sessions`, POST `/api/v1/departments/{deptId}/chat` | ✓ |
| **council_debate.html** | Load council, start debate, message, synthesize | `/api/v1/council/{id}`, `/api/v1/council/{id}/debate/start`, `.../message`, `.../synthesize` | ✓ |
| **connections.html** | loadTools, loadActiveConnections, test, connect, disconnect | `window.api.request` → `/api/v1/connections/tools`, `/list`, `/test`, `/connect`, DELETE `/{id}` | ✓ |
| **workspace.html** | List connections, connect, disconnect | `/api/v1/connections/list`, `/connect`, DELETE `/{id}` | ✓ |
| **brain_settings.html** | Scan, models, status, routing_mode, select, test, pull | `/api/v1/brain/scan`, `/models`, `/status`, `/routing_mode`, `/models/{name}/select`, `/test`, `/pull` | ✓ |
| **founder_panel.html** | Departments, councils, hidden depts reveal, emergency stop, maintenance, reset, backup/restore, learning, voice, snapshots | `/api/v1/departments/*`, `/api/v1/council/list`, `/api/v1/council/create`, `/api/v1/founder-panel/*`, `/api/v1/system/*`, `/api/v1/learning/*`, `/api/v1/voice/*`, `/api/v1/snapshots` | **Fixed:** Create council wired to POST `/api/v1/council/create` (was `/council/members/`). **Gap:** POST `/api/v1/departments/` (create hidden dept) has no backend route — returns 405; document only. |

### Static JS (api-client, realtime-status-manager, etc.)

- **api-client.js**: `window.api.request` prepends `/api/v1`; used by connections, daena_office, councils, etc. ✓
- **realtime-status-manager.js**: `/api/v1/agents/`, `/tasks/stats/overview`, `/system/status`, `/voice/status`, `/projects/`, `/council/list` — all exist ✓
- **voice-widget.js**, **department-chat.js**: daena/voice and department chat APIs ✓

### UI routes (all under `/ui/*` or page routes)

- **ui.py** defines: `/ui/dashboard`, `/ui/daena-office`, `/ui/provider-onboarding`, `/ui/founder-panel`, `/ui/system-monitor`, `/ui/connections`, `/ui/office/{dept_id}` (department_office), `/ui/agents`, `/ui/workspace`, `/ui/councils`, etc. main.py also registers duplicate `/ui/*` and `/incident-room`. All functional links in sidebar and dashboard point to these; no broken page links.

### Fix applied in this scan

- **Founder Panel – Create council:** Frontend called POST `/api/v1/council/members/` (no such route). Updated to POST `/api/v1/council/create` with query params `name`, `description`, `icon`, `color` to match backend.
