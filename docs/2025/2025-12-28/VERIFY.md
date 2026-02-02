# Verification Checklist
**Date:** 2025-01-23
**Purpose:** Verify all features are working correctly

## Pre-Flight Checks

### 1. Environment
```bash
# Check Python version
venv_daena_main_py310\Scripts\python.exe --version
# Expected: Python 3.10.x

# Check critical packages
venv_daena_main_py310\Scripts\python.exe -c "import fastapi, uvicorn, sqlalchemy; print('✅ Packages OK')"
```

### 2. Database
```bash
# Check database exists
dir daena.db
# Expected: File exists with size > 0

# Check database structure
python -c "from backend.database import SessionLocal, ChatSession, Agent, Department; db = SessionLocal(); print(f'✅ DB OK: {db.query(ChatSession).count()} sessions, {db.query(Agent).count()} agents, {db.query(Department).count()} departments')"
```

### 3. Ollama (Optional)
```bash
# Check Ollama is running
curl http://127.0.0.1:11434/api/tags
# Expected: JSON with models list
```

## Backend Health

### Basic Health Check
```bash
curl http://127.0.0.1:8000/api/v1/health/
# Expected: {"status": "healthy", ...}
```

### System Status
```bash
curl http://127.0.0.1:8000/api/v1/system/status
# Expected: System status with components
```

## Core Features

### 1. Agents API
```bash
# List all agents
curl http://127.0.0.1:8000/api/v1/agents/
# Expected: List of agents (48 total)

# Get specific agent
curl http://127.0.0.1:8000/api/v1/agents/{agent_id}
# Expected: Agent details
```

### 2. Departments API
```bash
# List all departments
curl http://127.0.0.1:8000/api/v1/departments/
# Expected: List of departments (8 total)

# Get department agents
curl http://127.0.0.1:8000/api/v1/departments/{department_id}/agents
# Expected: 6 agents per department
```

### 3. Chat System
```bash
# Create chat session
curl -X POST http://127.0.0.1:8000/api/v1/chat-history/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Chat", "category": "general"}'
# Expected: {"session_id": "...", ...}

# List all sessions
curl http://127.0.0.1:8000/api/v1/chat-history/sessions
# Expected: List of sessions

# Add message
curl -X POST http://127.0.0.1:8000/api/v1/chat-history/sessions/{session_id}/messages \
  -H "Content-Type: application/json" \
  -d '{"sender": "user", "content": "Hello", "category": "general"}'
# Expected: {"success": true, ...}
```

### 4. Daena Chat
```bash
# Start Daena chat
curl -X POST http://127.0.0.1:8000/api/v1/daena/chat/start
# Expected: {"session_id": "...", ...}

# Send message to Daena
curl -X POST http://127.0.0.1:8000/api/v1/daena/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello Daena", "session_id": "..."}'
# Expected: {"success": true, "session_id": "...", "response": "..."}
```

### 5. Department Chat
```bash
# Send message to department
curl -X POST http://127.0.0.1:8000/api/v1/departments/{department_id}/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello department", "context": {}}'
# Expected: {"success": true, "session_id": "...", "response": "..."}
```

### 6. Council System
```bash
# List councils
curl http://127.0.0.1:8000/api/v1/council/list
# Expected: At least 2 councils (Finance, Tech)

# Get specific council
curl http://127.0.0.1:8000/api/v1/council/finance
# Expected: Council details with experts

# Toggle council
curl -X POST "http://127.0.0.1:8000/api/v1/council/finance/toggle?enabled=false"
# Expected: {"success": true, "status": "inactive"}

# Start debate
curl -X POST http://127.0.0.1:8000/api/v1/council/finance/debate/start \
  -H "Content-Type: application/json" \
  -d '{"topic": "Test debate topic"}'
# Expected: {"success": true, "session_id": "...", "topic": "..."}
```

### 7. Intelligence Routing
```bash
# Score a query
curl -X POST http://127.0.0.1:8000/api/v1/intelligence/score \
  -H "Content-Type: application/json" \
  -d '{"query": "Analyze the financial data and calculate ROI"}'
# Expected: {"success": true, "scores": {"iq": 0.8, "eq": 0.0, "aq": 0.0, "execution": 0.2}, ...}

# Route a query
curl -X POST http://127.0.0.1:8000/api/v1/intelligence/route \
  -H "Content-Type: application/json" \
  -d '{"query": "Help me understand customer emotions", "context": {"department": "customer"}}'
# Expected: {"success": true, "response": "...", "intelligence_scores": {...}, ...}
```

### 8. Voice System
```bash
# Get voice status
curl http://127.0.0.1:8000/api/v1/voice/status
# Expected: {"talk_active": false, "voice_name": "default", ...}

# Toggle talk mode
curl -X POST http://127.0.0.1:8000/api/v1/voice/talk-mode \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
# Expected: {"success": true, "talk_active": true, ...}

# Get Daena voice file
curl http://127.0.0.1:8000/api/v1/voice/daena-voice
# Expected: WAV file download (if daena_voice.wav exists)
```

### 9. Brain Status
```bash
# Get brain status
curl http://127.0.0.1:8000/api/v1/brain/status
# Expected: {"connected": true/false, "model": "...", ...}

# List models
curl http://127.0.0.1:8000/api/v1/brain/models
# Expected: List of available models
```

### 10. Tasks
```bash
# List tasks
curl http://127.0.0.1:8000/api/v1/tasks/
# Expected: List of tasks

# Create task
curl -X POST http://127.0.0.1:8000/api/v1/tasks/ \
  -H "Content-Type: application/json" \
  -d '{"title": "Test Task", "description": "Test", "department_id": "engineering"}'
# Expected: {"success": true, "task": {...}}
```

### 11. Projects
```bash
# List projects
curl http://127.0.0.1:8000/api/v1/projects/
# Expected: List of projects

# Create project
curl -X POST http://127.0.0.1:8000/api/v1/projects/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Project", "description": "Test"}'
# Expected: {"success": true, "project": {...}}
```

## WebSocket Verification

### Connect to Events Stream
```javascript
// In browser console or WebSocket client
const ws = new WebSocket('ws://127.0.0.1:8000/ws/events');
ws.onmessage = (event) => {
  console.log('Event:', JSON.parse(event.data));
};
```

## Database Verification

### Check Persistence
```bash
# Create a chat session
SESSION_ID=$(curl -X POST http://127.0.0.1:8000/api/v1/chat-history/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "Persistence Test"}' | jq -r '.session_id')

# Restart backend (stop and start)

# Verify session still exists
curl http://127.0.0.1:8000/api/v1/chat-history/sessions/$SESSION_ID
# Expected: Session details
```

## Comprehensive Test

Run the full test suite:
```bash
python scripts/comprehensive_test_all_phases.py
```

**Expected Results:**
- ✅ Phase 1: Backend Health
- ✅ Phase 2: Database Persistence
- ✅ Phase 2: Tasks Persistence
- ✅ Phase 3: WebSocket Events Log
- ✅ Phase 4: Agents No Mock Data
- ✅ Phase 5: Department Chat Sessions
- ✅ Phase 6: Brain Status
- ✅ Phase 7: Voice Status
- ✅ Councils DB Migration
- ✅ Council Toggle
- ✅ Projects DB Migration
- ✅ Project Create
- ✅ Voice State Persistence
- ✅ System Status

**Target:** 12/12 tests passing

## Troubleshooting

### If Tests Fail

1. **Check Backend Logs:**
   ```bash
   type logs\backend_*.log | more
   ```

2. **Check Database:**
   ```bash
   python -c "from backend.database import SessionLocal; db = SessionLocal(); print('DB connection OK')"
   ```

3. **Check Council Seeding:**
   ```bash
   python -c "from backend.database import SessionLocal, CouncilCategory; db = SessionLocal(); print(f'Councils: {db.query(CouncilCategory).count()}')"
   ```

4. **Verify Endpoints:**
   ```bash
   curl http://127.0.0.1:8000/api/v1/health/
   ```

## Success Criteria

✅ All endpoints return 200 OK (or appropriate status)
✅ Database persists data across restarts
✅ WebSocket events are received
✅ Council system works end-to-end
✅ Intelligence routing scores queries correctly
✅ Voice system responds to requests
✅ All 12 comprehensive tests pass


