# Frontend Wiring Report

## Summary
- **Total JS Files Scanned**: 24
- **Total fetch() Calls**: 35
- **Total Event Handlers**: 35
- **Stubs/Coming Soon Found**: 4
- **Unwired Actions**: 1

---

## Fetch Calls by File

### agent_detail.js
| Endpoint | Method | Status |
|----------|--------|--------|
| `/api/v1/agents/{id}` | GET | ✅ Wired |
| `/api/v1/agents/{id}/tasks` | GET | ⚠️ Backend in-memory |
| `/api/v1/agents/{id}/chat` | POST | ✅ Wired |
| `/api/v1/agents/{id}/performance` | GET | ✅ Wired |

### councils.js
| Endpoint | Method | Status |
|----------|--------|--------|
| `/api/v1/councils` | GET | ⚠️ Backend in-memory |
| `/api/v1/councils/{id}` | GET | ⚠️ Backend in-memory |
| `/api/v1/councils/{id}/members` | GET | ⚠️ Backend in-memory |

### voice-widget.js
| Endpoint | Method | Status |
|----------|--------|--------|
| `/api/v1/daena/chat` | POST | ✅ Wired |
| `/api/v1/voice/status` | GET | ✅ Wired |
| `/api/v1/voice/interact` | POST | ✅ Wired |

### department-chat.js
| Endpoint | Method | Status |
|----------|--------|--------|
| `/api/v1/departments/{id}/chat/sessions` | GET | ✅ Wired |
| `/api/v1/chat-history/sessions` | POST | ✅ Wired |

### automation-ui.js
| Endpoint | Method | Status |
|----------|--------|--------|
| `/api/v1/automation/status` | GET | ✅ Wired |
| `/api/v1/automation/execute` | POST | ✅ Wired |

---

## Stubs Found

| File | Line | Issue |
|------|------|-------|
| dashboard.js | 187 | `showToast('Proposal details coming soon')` |
| councils.js | 192 | `// TODO: Implement council chat interface` |
| workspace.js | 189 | `alert('OAuth not yet implemented')` |
| workspace.html | 524 | `// TODO: Render connections dynamically` |
| founder_panel.html | 992 | `Backup list view coming soon` |

---

## Keybinds Active

| File | Key | Action | Status |
|------|-----|--------|--------|
| voice-widget.js | Ctrl+Shift+V | Push-to-talk | ✅ Wired |
| department-chat.js | Enter | Send message | ✅ Wired |
| agent_detail.js | Enter | Send chat | ✅ Wired |

---

## Missing Keybinds

| Feature | Expected Key | Status |
|---------|--------------|--------|
| Delete session | Delete | ❌ Not wired in main chat |
| Cancel action | Escape | ❌ Not wired |

---

## Recommendations

1. **councils.py** - Move from in-memory to SQLite (line 33)
2. **agents.py** - Move task storage to DB (line 654)
3. **workspace.js** - Implement OAuth or remove button (line 189)
4. **founder_panel.html** - Implement backup list UI (line 992)
5. **Add Delete key handler** for session deletion in chat UI
