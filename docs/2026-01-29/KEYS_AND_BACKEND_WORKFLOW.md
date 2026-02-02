# Keys and Backend Workflow – Real-Time Mapping

All interactive keys and buttons are wired to the correct backend endpoints and refresh UI in real time where applicable.

---

## Daena Office (`/ui/daena-office`)

| Action | Frontend | Backend | Real-time |
|--------|----------|---------|-----------|
| **Send message** (Enter / Send button) | `chat-form` submit → fetch `/api/v1/daena/chat/stream` | `POST /api/v1/daena/chat/stream` (daena router) | Streaming response; UI updates as tokens arrive |
| **Load sessions** | `window.api.getDaenaChatSessions(category)` | `GET /api/v1/chat-history/sessions?...` | On load and after new session from stream |
| **Load history** | `window.api.getChatHistory(sessionId)` | `GET /api/v1/daena/chat/{session_id}` | On session switch |
| **Delete session** | `window.api.deleteChatSession(sessionId)` | `DELETE /api/v1/daena/chat/{session_id}` | List refreshed after delete |
| **Brain status** | `window.api.getBrainStatus()` | `GET /api/v1/brain/status` | Polled by RealtimeStatusManager |
| **Quick tools** | `executeQuickTool(...)` → `window.api.executeDaenaCommand(...)` | Daena/backend command handling | Response shown in tool console |

Chat form submit is guarded: only runs if `chat-form`, `message-input`, and `chat-messages` exist.

---

## Department Office (`/ui/office/{department_id}`)

| Action | Frontend | Backend | Real-time |
|--------|----------|---------|-----------|
| **Send message** (Enter / Send) | `sendMessage()` → fetch `POST /api/v1/departments/${deptId}/chat` | `POST /api/v1/departments/{department_id}/chat` (departments router) | Typing indicator; response appended; session list refreshed if new session |
| **Load sessions** | fetch `GET /api/v1/departments/${deptId}/chat/sessions` | `GET /api/v1/departments/{department_id}/chat/sessions` | On load and after send (if new session) |
| **Load history** | fetch `GET /api/v1/departments/${deptId}/chat/sessions/${sessionId}` | `GET /api/v1/departments/{department_id}/chat/sessions/{session_id}` | On session switch |

On chat error, user sees inline error message and (if available) `window.showToast('Could not send message. Try again.', 'error')`.

---

## QA Guardian (`/api/v1/qa/ui`)

| Action | Frontend | Backend | Real-time |
|--------|----------|---------|-----------|
| **Refresh** | `qaGuardianRefresh()` → `fetchAPI('/status')` + `fetchAPI('/incidents?limit=20')` | `GET /api/v1/qa/status`, `GET /api/v1/qa/incidents` | Dashboard and incident list updated |
| **Kill Switch** | `qaGuardianToggleKillSwitch()` → `fetchAPI('/kill-switch', { method: 'POST', body: JSON.stringify({ enable }) })` | `POST /api/v1/qa/kill-switch` (Body: `{ "enable": true/false }`) | `refreshDashboard()` after toggle |
| **Request QA Review** | `qaGuardianRequestReview()` → `fetchAPI('/request-review', ...)` | `POST /api/v1/qa/request-review` | `refreshDashboard()` after success |
| **Run Smoke / Golden** | `qaGuardianRunRegression(type)` → `fetchAPI('/run-regression', ...)` | `POST /api/v1/qa/run-regression` | `refreshDashboard()` after success |
| **Security Scan** | `qaGuardianRunSecurityScan()` → `fetchAPI('/run-security-scan', ...)` | `POST /api/v1/qa/run-security-scan` | `refreshDashboard()` after success |
| **Start Guardian Loop** | `qaGuardianStart()` → `fetchAPI('/start', { method: 'POST' })` | `POST /api/v1/qa/start` | `refreshDashboard()` after success |
| **Stop Guardian Loop** | `qaGuardianStop()` → `fetchAPI('/stop', { method: 'POST' })` | `POST /api/v1/qa/stop` | `refreshDashboard()` after success |
| **Filter incidents** | `qaGuardianFilterIncidents()` → `fetchAPI('/incidents?status=...')` | `GET /api/v1/qa/incidents?status=...` | Incident list re-rendered |

Auto-refresh: dashboard runs `refreshDashboard()` every 30s.

---

## Incident Room (`/incident-room`)

| Action | Frontend | Backend | Real-time |
|--------|----------|---------|-----------|
| **Lockdown status** | `refreshLockdownStatus()` → `api('/founder-panel/system/emergency/status')` | `GET /api/v1/founder-panel/system/emergency/status` | Badge and bar updated on load and after Lockdown/Unlock |
| **Lockdown** | `incidentRoomDoLockdown()` → `api('/founder-panel/system/emergency/lockdown', POST)` | `POST /api/v1/founder-panel/system/emergency/lockdown` | `refreshLockdownStatus()` after |
| **Unlock** | `incidentRoomDoUnlock()` → `api('/founder-panel/system/emergency/unlock', POST)` | `POST /api/v1/founder-panel/system/emergency/unlock` | `refreshLockdownStatus()` after |
| **Containment list** | `refreshContainment()` → `api('/security/containment/status')` | `GET /api/v1/security/containment/status` | After Block/Unblock |
| **Block IP** | `incidentRoomBlockIpFromHit(ip)` → `api('/security/containment/block-ip', POST)` | `POST /api/v1/security/containment/block-ip` | `refreshContainment()` + `refreshHits()` |
| **Unblock IP** | `incidentRoomUnblockIp(ip)` → `api('/security/containment/unblock-ip', POST)` | `POST /api/v1/security/containment/unblock-ip` | `refreshContainment()` + `refreshHits()` |
| **Decoy hits** | `refreshHits()` → `api('/_decoy/hits?limit=100')` | `GET /api/v1/_decoy/hits?limit=100` | Table updated on load and after Refresh hits |

---

## Council Debate (`/ui/councils/{id}` debate)

| Action | Frontend | Backend | Real-time |
|--------|----------|---------|-----------|
| **Send message** | `sendMessage()` → debate message endpoint | Council debate message API | Optimistic append; then API response |
| **Start debate** | `startDebate()` → `POST /api/v1/council/{id}/debate/start` | Council router | Session and UI updated |
| **Synthesize** | `synthesizeDebate()` → `POST /api/v1/council/{id}/debate/{sessionId}/synthesize` | Council router | Synthesis result shown |

---

## Conference Room

| Action | Frontend | Backend | Real-time |
|--------|----------|---------|-----------|
| **Send message** | `sendMessage()` (local DOM only) | No backend chat in current snippet | UI-only; add backend if meeting chat is required |
| **Mic / Camera / Share / Record / Leave** | `toggleMic()`, `toggleCamera()`, etc. | Depends on WebRTC/meeting backend | N/A here |

---

## Summary

- **Daena Office**: Send uses `/api/v1/daena/chat/stream`; form and DOM guarded; streaming updates UI in real time.
- **Department Office**: Send uses `/api/v1/departments/{id}/chat`; error triggers toast when available; sessions/history refetched as needed.
- **QA Guardian**: All buttons call correct `/api/v1/qa/*` endpoints; Kill Switch body is `{ "enable": true/false }`; every action that changes state calls `refreshDashboard()` for immediate UI update.
- **Incident Room**: Lockdown, Unlock, Block IP, Unblock IP, and Decoy hits call the correct founder/security/deception APIs and refresh status/hits/containment after each action.

All keys and buttons above are wired to the right backend workflow and, where applicable, refresh the UI in real time.
