# Frontend Interactions Map

Generated: 2026-01-19

## Overview

The Daena frontend has **43 HTML templates** and **33 JavaScript files**.

---

## Key Pages & Their Wiring

### 🏢 Daena Office (`daena_office.html`)
| Element | Action | API Call | Status |
|---------|--------|----------|--------|
| New Chat button | `startNewChat()` | `POST /api/v1/chat-history/sessions` | ✅ Wired |
| Send Message | form submit | `POST /api/v1/daena/chat/stream` | ✅ Wired |
| Delete Session | `deleteSession()` | `DELETE /api/v1/daena/chat/{id}` | ✅ Wired |
| Rename Session | `renameSession()` | `PUT /api/v1/chat-history/sessions/{id}` | ✅ Wired |
| Voice Toggle | `toggleVoice()` | `POST /api/v1/voice/talk-mode` | ✅ Wired |
| Export Chat | `exportChat()` | Local JSON/TXT generation | ✅ Working |
| Edit Message | `editMessage()` | Local UI only | ✅ Working |
| Category Filter | `filterByCategory()` | Refetches sessions | ✅ Wired |
| Keyboard Delete | - | Not implemented | ⚠️ Missing |

### 🧠 Brain Settings (`brain_settings.html`)
| Element | Action | API Call | Status |
|---------|--------|----------|--------|
| List Models | on load | `GET /api/v1/brain/models` | ✅ Wired |
| Select Model | toggle | `POST /api/v1/brain/models/{name}/select` | ✅ Wired |
| Test Model | button | `POST /api/v1/brain/test` | ✅ Wired |
| Pull Model | button | `POST /api/v1/brain/pull` | ✅ Wired |
| Model Usage | on load | `GET /api/v1/brain/models/usage` | ✅ Wired |

### 👔 Dashboard (`dashboard.html`)
| Element | Action | API Call | Status |
|---------|--------|----------|--------|
| Department Cards | on load | `GET /api/v1/departments/` | ✅ Wired |
| Agent Status | realtime | WebSocket `/ws/events` | ✅ Wired |
| System Health | on load | `GET /api/v1/health/` | ✅ Wired |

### 🗳️ Council Dashboard (`council_dashboard.html`)
| Element | Action | API Call | Status |
|---------|--------|----------|--------|
| List Councils | on load | `GET /api/v1/councils` | ✅ Wired |
| Council Details | click | `GET /api/v1/councils/{id}` | ✅ Wired |
| Start Debate | button | `POST /api/v1/council/debate` | ⚠️ Check endpoint |

### 👤 Founder Panel (`founder_panel.html`)
| Element | Action | API Call | Status |
|---------|--------|----------|--------|
| Overview | on load | `GET /api/v1/founder/overview` | ⚠️ Check endpoint |
| Create Backup | button | `POST /api/v1/system/backup` | ✅ Wired |
| List Backups | on load | `GET /api/v1/system/backups` | ✅ Wired |
| Rollback | button | `POST /api/v1/system/rollback` | ✅ Wired |
| Snapshots | - | - | 🔴 Not Implemented |

### 🔗 Connections (`connections.html`)
| Element | Action | API Call | Status |
|---------|--------|----------|--------|
| List MCP Servers | on load | `GET /api/v1/connections/mcp/servers` | ✅ Wired |
| Test Connection | button | `POST /api/v1/connections/{id}/test` | ✅ Wired |

### 🎤 Voice Widget (`voice-widget.js`)
| Element | Action | API Call | Status |
|---------|--------|----------|--------|
| Voice Status | on load | `GET /api/v1/voice/status` | ✅ Wired |
| Voice Interact | on speak | `POST /api/v1/voice/interact` | ✅ Wired |
| Chat via Voice | voice input | `POST /api/v1/daena/chat` | ✅ Wired |

### 🎯 Demo Page (`demo.html`, `demo.js`)
| Element | Action | API Call | Status |
|---------|--------|----------|--------|
| Run Demo | button | `POST /api/v1/demo/run` | ✅ Wired |
| Demo Health | on load | `GET /api/v1/demo/health` | ✅ Wired |
| Trace Timeline | after run | `GET /api/v1/demo/trace/{id}` | ✅ Wired |

---

## JavaScript Modules Summary

| File | Purpose | Lines |
|------|---------|-------|
| `api-client.js` | Unified API wrapper | 443 |
| `session-manager.js` | Chat session handling | ~150 |
| `voice-widget.js` | Voice/audio controls | ~450 |
| `demo.js` | Demo page logic | ~260 |
| `dashboard.js` | Main dashboard | ~200 |
| `councils.js` | Council management | ~180 |
| `connections.js` | API connections | ~100 |
| `automation-ui.js` | Tool automation | ~150 |
| `websocket-client.js` | Real-time events | ~200 |

---

## Key Findings

### ✅ Well Wired
1. Chat create/send/delete flow
2. Brain model selection  
3. Voice toggle
4. Export/share chat
5. WebSocket real-time updates
6. Demo endpoints

### ⚠️ Partially Wired
1. Keyboard shortcuts (Delete key for sessions)
2. Council debate (endpoint needs verification)
3. Founder overview (endpoint path unclear)

### 🔴 Not Implemented
1. **Snapshots/Rollback UI** in Founder Panel
2. **Tools execution** visible in chat
3. **Web search tool** integration
4. **URL fetch tool** integration
