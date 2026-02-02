# Phase 1: Backend State Audit

## In-Memory Stores Found

### 1. `sunflower_registry` (backend/utils/sunflower_registry.py)
- **Type**: In-memory Dict
- **Contains**: departments, agents, projects, cells, adjacency_cache
- **Status**: Populated from DB but still in-memory
- **Action**: Keep as cache, but ensure DB is source of truth

### 2. `active_sessions` (backend/routes/daena.py)
- **Type**: `Dict[str, DaenaSession]`
- **Contains**: Active chat sessions
- **Status**: In-memory only, lost on restart
- **Action**: Move to SQLite ChatSession table

### 3. `_activity_store` (backend/routes/agent_activity.py)
- **Type**: `Dict[str, AgentActivity]`
- **Contains**: Agent activity data
- **Status**: In-memory only
- **Action**: Move to EventLog + Task tables

### 4. `founder_overrides` (backend/routes/founder_panel.py)
- **Type**: List
- **Contains**: Founder panel overrides
- **Status**: In-memory
- **Action**: Move to DB (Settings/Overrides table)

### 5. `audit_logs` (backend/routes/audit.py)
- **Type**: List
- **Contains**: Audit logs
- **Status**: In-memory only
- **Action**: Move to EventLog table

### 6. `voice_state` (backend/routes/voice.py)
- **Type**: Dict
- **Contains**: Voice system state
- **Status**: In-memory
- **Action**: Move to DB (VoiceState table)

## Current Database Schema

### Existing Tables (database.py):
- ✅ User
- ✅ Department (has sunflower_index, cell_id)
- ✅ Agent (has department_id, sunflower_index, cell_id)
- ✅ BrainModel
- ✅ CellAdjacency
- ✅ Project
- ✅ Task (referenced but may need enhancement)
- ✅ ChatMessage (DepartmentChatMessage exists)

### Missing Tables (Need to Create):
- ❌ ChatCategory
- ❌ ChatSession (proper schema)
- ❌ CouncilCategory
- ❌ CouncilMember
- ❌ Connection (tool connections)
- ❌ EventLog (comprehensive)
- ❌ VoiceState
- ❌ Settings/Overrides

## Endpoints Serving Mock Data

1. `/api/v1/agent-activity/activity` - Uses `_get_mock_activity()`
2. `/api/v1/daena/chat` - Uses `active_sessions` (in-memory)
3. `/api/v1/founder-panel/*` - Uses `founder_overrides` (in-memory)
4. `/api/v1/audit/*` - Uses `audit_logs` (in-memory)
5. `/api/v1/voice/*` - Uses `voice_state` (in-memory)

## Next Steps

1. Create comprehensive SQLite schema
2. Migrate all in-memory stores to DB
3. Update endpoints to use DB
4. Keep sunflower_registry as cache (populated from DB)



