# E2E Integration Matrix
## Frontend Action → Backend Endpoint → DB Side Effects → WebSocket Event

---

## Chat Actions

| Frontend Action | Endpoint | Method | DB Side Effect | WebSocket Event |
|-----------------|----------|--------|----------------|-----------------|
| Click "New Chat" | `/api/v1/daena/chat/start` | POST | INSERT ChatSession | `chat.session_created` |
| Send message | `/api/v1/daena/chat` | POST | INSERT ChatMessage (2x) | `chat.message` |
| Load session | `/api/v1/daena/chat/{id}` | GET | None | None |
| Rename session | `/api/v1/chat-history/sessions/{id}` | PUT | UPDATE ChatSession.title | `chat.session_updated` |
| Delete session | `/api/v1/daena/chat/{id}` | DELETE | UPDATE ChatSession.is_active=false | `chat.session_deleted` |
| Export session | `/api/v1/daena/chat/{id}/export` | GET | None | None |
| Restore session | `/api/v1/daena/chat/{id}/restore` | POST | UPDATE ChatSession.is_active=true | `chat.session_restored` |
| List deleted | `/api/v1/daena/chat/deleted` | GET | None | None |
| List sessions | `/api/v1/daena/chat/sessions` | GET | None | None |

---

## Brain/Model Actions

| Frontend Action | Endpoint | Method | DB Side Effect | WebSocket Event |
|-----------------|----------|--------|----------------|-----------------|
| Check brain status | `/api/v1/brain/status` | GET | None | None |
| List models | `/api/v1/brain/models` | GET | None | None |
| Switch model | `/api/v1/brain/switch` | POST | None | `brain.status` |
| Pull model | `/api/v1/brain/pull` | POST | None | `brain.download_started` |
| Pull progress | WebSocket `/ws/brain` | WS | None | `brain.download_progress` |

---

## Voice Actions

| Frontend Action | Endpoint | Method | DB Side Effect | WebSocket Event |
|-----------------|----------|--------|----------------|-----------------|
| Check voice status | `/api/v1/voice/status` | GET | None | None |
| Toggle voice | `/api/v1/voice/toggle` | POST | None | None |
| Voice interaction | `/api/v1/voice/interact` | POST | None | None |
| Update settings | `/api/v1/voice/settings` | PUT | None | None |

---

## Tool Actions

| Frontend Action | Endpoint | Method | DB Side Effect | WebSocket Event |
|-----------------|----------|--------|----------------|-----------------|
| Web search | `/api/v1/tools/search` | POST | INSERT ToolExecution | None |
| List providers | `/api/v1/tools/providers` | GET | None | None |
| Execute tool | `/api/v1/tools/execute` | POST | INSERT ToolExecution | `tool.executed` |
| Tool status | `/api/v1/tools/status` | GET | None | None |

---

## Snapshot/Rollback Actions

| Frontend Action | Endpoint | Method | DB Side Effect | WebSocket Event |
|-----------------|----------|--------|----------------|-----------------|
| List snapshots | `/api/v1/snapshots` | GET | None | None |
| Create snapshot | `/api/v1/snapshots` | POST | File creation in backups/ | `system.snapshot_created` |
| Restore snapshot | `/api/v1/snapshots/{id}/restore` | POST | Multiple table updates | `system.reset` |
| Delete snapshot | `/api/v1/snapshots/{id}` | DELETE | File deletion | None |

---

## Department Actions

| Frontend Action | Endpoint | Method | DB Side Effect | WebSocket Event |
|-----------------|----------|--------|----------------|-----------------|
| List departments | `/api/v1/departments/` | GET | None | None |
| Get department | `/api/v1/departments/{id}` | GET | None | None |
| Create department | `/api/v1/departments/` | POST | INSERT Department | `department.created` |
| Update department | `/api/v1/departments/{id}` | PUT | UPDATE Department | `department.updated` |
| Delete department | `/api/v1/departments/{id}` | DELETE | UPDATE Department.is_active=false | `department.deleted` |

---

## Council Actions

| Frontend Action | Endpoint | Method | DB Side Effect | WebSocket Event |
|-----------------|----------|--------|----------------|-----------------|
| List councils | `/api/v1/council/` | GET | None | None |
| Consult council | `/api/v1/council/consult` | POST | INSERT CouncilDecision | `council.debate_started` |
| Get synthesis | `/api/v1/council/synthesis` | GET | None | `council.synthesis_posted` |

---

## Agent Actions

| Frontend Action | Endpoint | Method | DB Side Effect | WebSocket Event |
|-----------------|----------|--------|----------------|-----------------|
| List agents | `/api/v1/agents/` | GET | None | None |
| Create agent | `/api/v1/agents/` | POST | INSERT Agent | `agent.created` |
| Update agent | `/api/v1/agents/{id}` | PUT | UPDATE Agent | `agent.updated` |
| Delete agent | `/api/v1/agents/{id}` | DELETE | UPDATE Agent.is_active=false | `agent.deleted` |
| Assign task | `/api/v1/agents/{id}/tasks` | POST | INSERT Task | `task.created` |

---

## Task Actions

| Frontend Action | Endpoint | Method | DB Side Effect | WebSocket Event |
|-----------------|----------|--------|----------------|-----------------|
| List tasks | `/api/v1/tasks/` | GET | None | None |
| Create task | `/api/v1/tasks/` | POST | INSERT Task | `task.created` |
| Update task | `/api/v1/tasks/{id}` | PUT | UPDATE Task | `task.updated` |
| Complete task | `/api/v1/tasks/{id}/complete` | POST | UPDATE Task.status='completed' | `task.completed` |
| Cancel task | `/api/v1/tasks/{id}/cancel` | POST | UPDATE Task.status='cancelled' | `task.cancelled` |

---

## Demo Actions

| Frontend Action | Endpoint | Method | DB Side Effect | WebSocket Event |
|-----------------|----------|--------|----------------|-----------------|
| Demo login | `/demo/login` | POST | None (session cookie) | None |
| Demo logout | `/demo/logout` | GET | None | None |
| Run demo | `/api/v1/demo/run` | POST | INSERT DemoTrace | None |
| Get trace | `/api/v1/demo/trace/{id}` | GET | None | None |
| Demo health | `/api/v1/demo/health` | GET | None | None |

---

## Health/System Actions

| Frontend Action | Endpoint | Method | DB Side Effect | WebSocket Event |
|-----------------|----------|--------|----------------|-----------------|
| Health check | `/api/v1/health` | GET | None | None |
| System health | `/api/v1/health/system` | GET | None | None |
| Council health | `/api/v1/health/council` | GET | None | None |
| Emergency stop | `/api/v1/founder-panel/system/emergency/stop-all` | POST | UPDATE all agents | `system.emergency_stop` |
| System reset | `/api/v1/system/reset-to-default` | POST | TRUNCATE/reseed | `system.reset` |

---

## WebSocket Subscriptions

| Event Type | Payload | UI Update |
|------------|---------|-----------|
| `chat.message` | `{session_id, sender, content}` | Append message to chat |
| `brain.status` | `{connected, model}` | Update brain indicator |
| `task.progress` | `{task_id, progress, status}` | Update task card |
| `agent.created` | `{agent_id, name, department}` | Add to agent list |
| `council.synthesis_posted` | `{decision, votes}` | Show council result |
| `system.reset` | `{action: "reset"}` | Refresh page |

---

## Test Script (Manual Verification)

```bash
# 1. Create session -> send message -> tool search
curl -X POST http://localhost:8000/api/v1/daena/chat/start
# Note session_id
curl -X POST http://localhost:8000/api/v1/daena/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "search the web for Python tutorials", "session_id": "SESSION_ID"}'

# 2. Export -> delete -> verify gone
curl http://localhost:8000/api/v1/daena/chat/SESSION_ID/export
curl -X DELETE http://localhost:8000/api/v1/daena/chat/SESSION_ID
curl http://localhost:8000/api/v1/daena/chat/deleted

# 3. Restore -> confirm back
curl -X POST http://localhost:8000/api/v1/daena/chat/SESSION_ID/restore
curl http://localhost:8000/api/v1/daena/chat/sessions

# 4. Switch model
curl http://localhost:8000/api/v1/brain/models
curl -X POST http://localhost:8000/api/v1/brain/switch \
  -H "Content-Type: application/json" \
  -d '{"model": "llama3.2:3b"}'

# 5. Tools search
curl http://localhost:8000/api/v1/tools/providers
curl "http://localhost:8000/api/v1/tools/search?q=Python+tutorials"

# 6. Snapshots
curl http://localhost:8000/api/v1/snapshots
curl -X POST http://localhost:8000/api/v1/snapshots \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Snapshot"}'
```

---

**Generated:** 2026-01-19  
**For:** AI Tinkerers Toronto Demo
