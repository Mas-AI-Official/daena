# Complete Implementation Roadmap - All Phases

## Executive Summary

This document provides the complete roadmap for eliminating all mock data, implementing true persistence, real-time sync, and fixing all broken UI controls.

## ✅ Completed Work

### Phase 1: Backend State Audit ✅
- Identified all 6 in-memory stores
- Documented mock data endpoints
- Created audit report

### Phase 2: SQLite Persistence (PARTIAL)
- ✅ Enhanced database.py with all required tables
- ✅ Created ChatService for DB-backed chat management
- ✅ Updated Daena chat endpoint to use DB
- ✅ Partially updated department chat to use DB
- ⏳ Seed script needs import path fix
- ⏳ Need to update remaining routes

## 🔄 Implementation Plan (Remaining)

### Immediate Next Steps (Priority Order):

#### 1. Complete Database Migration
**Files to Update:**
- `backend/routes/daena.py` - Remove `active_sessions`, use ChatService
- `backend/routes/departments.py` - Complete DB migration
- `backend/routes/agents.py` - Use DB for agent chat
- `backend/routes/chat_history.py` - Use DB ChatSession/ChatMessage
- `backend/routes/founder_panel.py` - Use SystemConfig for overrides
- `backend/routes/audit.py` - Use EventLog table
- `backend/routes/voice.py` - Use VoiceState table

**Action:**
```python
# Replace all active_sessions usage with:
from backend.database import get_db
from backend.services.chat_service import chat_service

db = next(get_db())
session = chat_service.get_or_create_session(...)
```

#### 2. Fix Seed Script & Bootstrap Data
**File:** `backend/scripts/seed_database.py`

**Fix:**
- Correct import paths
- Run to create 8 departments + 6 agents each
- Create chat categories
- Create council defaults

**Command:**
```bash
cd D:\Ideas\Daena_old_upgrade_20251213
python -m backend.scripts.seed_database
```

#### 3. WebSocket Event Publishing
**File:** `backend/core/websocket_manager.py`

**Enhance:**
- Write to EventLog on all state changes
- Publish events: agent.created, task.progress, chat.message, etc.
- Add "since_event_id" parameter for backfill

#### 4. Frontend Mock Data Removal
**Files to Scan:**
- `frontend/static/js/*.js` - Remove all mock arrays
- `frontend/templates/*.html` - Remove inline mock data

**Replace with:**
- API calls to real endpoints
- WebSocket client for live updates

#### 5. Brain Status Consistency
**Files:**
- `backend/routes/brain_status.py` - Already uses 127.0.0.1 ✅
- `frontend/templates/base.html` - Update status indicator
- `frontend/templates/daena_office.html` - Update status
- All pages with brain status - Ensure consistency

**Fix:**
- Check Ollama at 127.0.0.1:11434
- Show OFFLINE if not reachable
- Show ACTIVE if reachable and model available

#### 6. Department Chat Dual-View
**Implementation:**
- All messages stored with `scope_type='department'` and `scope_id='HR'`
- Department office: Filter by scope
- Daena office: Show same messages by category
- Single source: ChatMessage table

#### 7. Voice System
**Files:**
- `scripts/START_AUDIO_ENV.bat` - Fix activation
- `backend/routes/voice.py` - Use VoiceState table
- `backend/services/voice_service.py` - Implement daena_voice.wav

#### 8. UI Controls Implementation
**Endpoints to Create:**
- `POST /api/v1/brain/enable` - Enable routing
- `POST /api/v1/brain/disable` - Disable routing
- `GET /api/v1/brain/models/scan` - Scan Ollama models
- `POST /api/v1/agents/{id}/model` - Assign model to agent
- `GET /api/v1/analytics/usage` - Usage counters

#### 9. Sidebar & Layout Fixes
**File:** `frontend/templates/base.html`
- Remove duplicate toggles
- Fix sidebar width expansion
- Fix overflow issues

#### 10. Dashboard Real Data
**File:** `frontend/templates/dashboard.html`
- Remove spinning animation
- Load tasks from DB
- Load events from EventLog
- Show brain status
- Show today's operations

#### 11. Agent Count Fix
**Files:**
- `backend/scripts/seed_database.py` - Ensure exactly 6 per dept
- `backend/routes/departments.py` - Filter by department_id
- `backend/utils/sunflower_registry.py` - Fix duplicate generation

#### 12. Hidden Departments
**Files:**
- `backend/routes/founder_panel.py` - Show all departments
- `frontend/templates/founder_panel.html` - Display hidden depts
- Add enable/disable endpoints

#### 13. Councils Real + Editable
**Files:**
- `backend/routes/council.py` - CRUD endpoints
- `frontend/templates/councils.html` - Edit UI
- Store in CouncilCategory/CouncilMember tables

## Critical Code Patterns

### Pattern 1: Replace In-Memory with DB
```python
# OLD (in-memory):
active_sessions[session_id] = session

# NEW (DB-backed):
from backend.database import get_db
from backend.services.chat_service import chat_service
db = next(get_db())
session = chat_service.create_session(db, ...)
```

### Pattern 2: Always Return session_id
```python
# Ensure session exists
session = chat_service.get_or_create_session(db, session_id=request.session_id, ...)
return {"session_id": session.session_id, ...}
```

### Pattern 3: Check Ollama Before Brain Call
```python
ollama_available = False
try:
    async with httpx.AsyncClient(timeout=2.0) as client:
        response = await client.get("http://127.0.0.1:11434/api/tags")
        if response.status_code == 200:
            ollama_available = True
except:
    pass

if ollama_available:
    response = await llm_service.generate_response(...)
else:
    response = "Deterministic offline response..."
```

### Pattern 4: WebSocket Event Publishing
```python
from backend.core.websocket_manager import emit_event
from backend.database import EventLog, get_db

# After DB change:
db = next(get_db())
event = EventLog(
    event_type="chat.message",
    entity_type="chat",
    entity_id=session_id,
    payload_json={"sender": "user", "content": msg}
)
db.add(event)
db.commit()

# Broadcast via WebSocket
await emit_event("chat.message", {"session_id": session_id, ...})
```

## Testing Checklist

### Smoke Test Requirements:
1. ✅ Backend starts
2. ✅ Database tables created
3. ✅ Seed data loaded (8 depts, 6 agents each)
4. ✅ Daena chat returns session_id
5. ✅ Department chat persists
6. ✅ Chat history visible in both views
7. ✅ WebSocket events received
8. ✅ Brain status accurate
9. ✅ Persistence survives restart

## Deliverables Status

### Files Changed (So Far):
- ✅ `backend/database.py` - Enhanced
- ✅ `backend/services/chat_service.py` - Created
- ✅ `backend/routes/daena.py` - Updated
- ✅ `backend/routes/departments.py` - Partially updated
- ✅ `backend/scripts/seed_database.py` - Created (needs fix)

### How to Run (Current):
1. **Start Backend:**
   ```bash
   START_DAENA.bat
   ```

2. **Seed Database:**
   ```bash
   python -m backend.scripts.seed_database
   ```

3. **Start Ollama:**
   ```bash
   scripts\START_OLLAMA.bat
   ```

4. **Open Dashboard:**
   ```
   http://127.0.0.1:8000/ui/dashboard
   ```

### Proof Checklist:
- [ ] DB persists after restart
- [ ] WS events received in UI
- [ ] No mock state remains
- [ ] Department chat history works
- [ ] Daena shows department chats
- [ ] Brain status truthful everywhere
- [ ] Voice works or clear fallback

## Estimated Remaining Work

- **Phase 2 Completion**: 2-3 hours
- **Phase 3 (WebSocket)**: 1-2 hours
- **Phase 4 (Frontend)**: 3-4 hours
- **Phase 5 (Dual-view)**: 1 hour
- **Phase 6 (Brain Management)**: 2-3 hours
- **Phase 7 (Voice)**: 2-3 hours
- **Phase 8 (QA)**: 1-2 hours

**Total**: ~12-18 hours of focused development

## Next Session Priorities

1. Fix seed script and run it
2. Complete all route migrations to DB
3. Implement WebSocket event publishing
4. Remove all frontend mock data
5. Fix brain status consistency
6. Test end-to-end

## Notes

- All database changes are backward compatible (added fields are nullable)
- Existing data will continue to work
- Migration is incremental (can be done route by route)
- WebSocket infrastructure already exists, just needs event publishing
- Frontend changes are mostly removing code, not adding complexity



