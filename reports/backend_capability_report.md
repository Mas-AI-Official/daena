# Backend Capability Report

## Summary
- **Total Route Files**: 108
- **Total Endpoints**: 807+
- **In-Memory Storage Issues**: 3 files
- **TODO Comments**: 15
- **DB-Backed Services**: Majority

---

## Critical Issues

### 1. In-Memory Storage (Must Fix)

| File | Line | Issue | Priority |
|------|------|-------|----------|
| `councils.py` | 33 | `# In-memory storage (TODO: Move to database)` | HIGH |
| `agents.py` | 654-657 | `_agent_chat_history: Dict` and `_agent_tasks: Dict` | HIGH |

### 2. Mixed Storage Patterns

| Endpoint | DB Service | JSON Fallback | Status |
|----------|------------|---------------|--------|
| `chat_history.py` delete | `chat_service.delete_session()` | `chat_history_manager.delete_session()` | ✅ Fixed |
| `chat_history.py` list | `chat_service.get_all_sessions()` | Fallback | ✅ OK |
| `councils.py` all | None | In-memory | ❌ Need fix |

---

## Tool Execution Path

```
User message → daena.py detect_and_execute_tool()
    ↓
TOOL_PATTERNS match?
    ↓ Yes
automation.py execute_tool()
    ↓
unified_tool_executor.execute()
    ↓
Real tool: browser/search/etc
```

**Status**: ✅ Path exists and is wired

---

## WebSocket Events

| Event Type | Emitter | Status |
|------------|---------|--------|
| `chat.message` | chat_history.py | ✅ |
| `chat.session.deleted` | chat_history.py | ✅ Added |
| `agent.created` | agents.py | ✅ |
| `agent.updated` | agents.py | ✅ |
| `council.created` | - | ❌ Missing |
| `project.created` | - | ❌ Missing |

---

## Route Categories

### Fully Wired (DB-backed)
- `/api/v1/daena/*` - Chat with Daena
- `/api/v1/agents/*` (core CRUD) - Agent management
- `/api/v1/departments/*` - Department management
- `/api/v1/brain/*` - Brain/model status
- `/api/v1/chat-history/*` - Session management
- `/api/v1/voice/*` - Voice interaction
- `/api/v1/automation/*` - Tool execution

### Partially Wired (In-Memory)
- `/api/v1/councils/*` - Council CRUD
- `/api/v1/agents/{id}/tasks` - Agent tasks
- `/api/v1/agents/{id}/chat/history` - Agent chat history

### Needs UI Wiring
- `/api/v1/founder/restore` - Has backend, UI shows "coming soon"
- `/api/v1/founder/backups` - Has backend, UI shows "coming soon" for list view

---

## Recommendations

1. **councils.py** - Add SQLite models for Council, CouncilMember, Debate
2. **agents.py** - Use existing Task table instead of `_agent_tasks` dict
3. **founder_panel.html** - Wire backup list to existing `/api/v1/founder/backups` endpoint
4. **Add WebSocket events** for council and project CRUD
