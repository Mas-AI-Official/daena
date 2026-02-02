# Route Fixes Summary - 2025-12-19

## Issue: Agent Chat Endpoint Returning 404

### Root Cause
The `agent_builder_platform.py` router had conflicting routes that were matching `/api/v1/agents/{agent_id}/chat` before the system `agents.py` router could handle it.

### Fixes Applied

1. **Fixed route conflicts in `backend/routes/agent_builder_platform.py`:**
   - Changed `/api/v1/agents/{agent_id}/chat` → `/agents/{agent_id}/chat` (now under `/agent-builder` prefix)
   - Changed `/api/v1/agents/{agent_id}` → `/agents/{agent_id}` (now under `/agent-builder` prefix)
   - Changed `/api/v1/agents/user` → `/agents/user` (now under `/agent-builder` prefix)
   - Changed `/api/v1/agents/create-simple` → `/agents/create-simple`
   - Changed `/api/v1/agents/create-advanced` → `/agents/create-advanced`
   - Changed `/api/v1/agents/create-from-template` → `/agents/create-from-template`

2. **Result:**
   - System agents: `/api/v1/agents/{agent_id}/chat` (handled by `agents.py`)
   - User-created agents: `/agent-builder/agents/{agent_id}/chat` (handled by `agent_builder_platform.py`)

### Files Changed
- `backend/routes/agent_builder_platform.py` - Fixed 6 route definitions

### Next Steps
1. Restart backend to apply route changes
2. Test agent chat endpoint with system agent ID
3. Verify smoke tests pass

