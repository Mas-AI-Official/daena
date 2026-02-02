# Backend Capabilities Map

Generated: 2026-01-19

## Overview

The Daena backend exposes **400+ API endpoints** across **113 route files**.

---

## Route Categories

### 🧠 Brain & LLM (brain.py, brain_status.py, llm.py, llm_status.py)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/brain/status` | Get brain connection status |
| GET | `/api/v1/brain/models` | List available models |
| POST | `/api/v1/brain/switch-model` | Switch active model |
| GET | `/api/v1/llm-status/providers` | List LLM providers |
| GET | `/api/v1/llm-status/status` | Get LLM status |
| GET | `/api/v1/llm-status/active` | Get active LLM |
| POST | `/api/v1/llm/completion` | Generate completion |
| POST | `/api/v1/llm/stream` | Stream completion |
| DELETE | `/api/v1/brain/models/{model_name}` | Remove model |

### 💬 Chat & History (chat_history.py, daena.py)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/chat-history/sessions` | List chat sessions |
| POST | `/api/v1/chat-history/sessions` | Create new session |
| GET | `/api/v1/chat-history/sessions/{id}` | Get session |
| DELETE | `/api/v1/chat-history/sessions/{id}` | Delete session |
| GET | `/api/v1/chat-history/messages/{session_id}` | Get messages |
| POST | `/api/v1/daena/chat` | Send chat message |
| POST | `/api/v1/daena/chat/stream` | Stream chat response |
| DELETE | `/api/v1/daena/chat/{session_id}` | Delete chat |

### 👔 Departments & Agents (departments.py, agents.py, agent_activity.py)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/departments/` | List departments |
| GET | `/api/v1/departments/{id}` | Get department |
| GET | `/api/v1/agents/` | List agents |
| GET | `/api/v1/agents/{id}` | Get agent |
| POST | `/api/v1/agents/` | Create agent |
| PUT | `/api/v1/agents/{id}` | Update agent |
| DELETE | `/api/v1/agents/{id}` | Delete agent |
| DELETE | `/api/v1/departments/{id}/chat/sessions/{session_id}` | Delete dept chat |

### 🗳️ Council & Governance (council.py, councils.py, council_v2.py)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/councils/` | List councils |
| GET | `/api/v1/councils/{id}` | Get council |
| POST | `/api/v1/councils/` | Create council |
| DELETE | `/api/v1/councils/{id}` | Delete council |
| POST | `/api/v1/council/debate` | Start debate |
| GET | `/api/v1/council/synthesis` | Get synthesis |

### 🔧 Tools & Automation (automation.py, daena_tools.py, tool_playbooks.py)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/automation/playbooks` | List playbooks |
| POST | `/api/v1/automation/execute` | Execute automation |
| GET | `/api/v1/daena-tools/code-scanner` | Scan code |
| GET | `/api/v1/daena-tools/db-inspector` | Inspect database |
| POST | `/api/v1/daena-tools/api-tester` | Test API |

### 🎤 Voice & Audio (voice.py, voice_agents.py, voice_panel.py)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/voice/status` | Get voice status |
| POST | `/api/v1/voice/toggle` | Toggle voice |
| POST | `/api/v1/voice/speak` | Text-to-speech |
| GET | `/api/v1/voice/listen` | Start listening |

### 🔗 Connections & APIs (connections.py, integrations.py)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/connections/` | List connections |
| POST | `/api/v1/connections/` | Create connection |
| DELETE | `/api/v1/connections/{id}` | Delete connection |
| GET | `/api/v1/integrations/` | List integrations |
| POST | `/api/v1/integrations/{id}/connect` | Connect integration |

### 📊 Projects & Tasks (projects.py, tasks.py, task_timeline.py)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/projects/` | List projects |
| POST | `/api/v1/projects/` | Create project |
| GET | `/api/v1/tasks/` | List tasks |
| POST | `/api/v1/tasks/` | Create task |
| DELETE | `/api/v1/tasks/{id}` | Delete task |

### ❤️ Health & Monitoring (health.py, monitoring.py)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/health/` | Basic health check |
| GET | `/api/v1/health/council` | Council health |
| GET | `/api/v1/health/system` | Full system health |
| GET | `/api/v1/monitoring/metrics` | System metrics |

### 🎯 Demo (demo.py)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/demo/health` | Demo health check |
| POST | `/api/v1/demo/run` | Run demo scenario |
| GET | `/api/v1/demo/trace/{id}` | Get demo trace |

### 👤 Founder & God Mode (founder_panel.py, founder_api.py, god_mode.py)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/founder/overview` | Founder dashboard |
| POST | `/api/v1/god-mode/memory/store` | Store memory |
| POST | `/api/v1/god-mode/router/dispatch` | Dispatch to router |
| POST | `/api/v1/god-mode/change-control/propose` | Propose change |

---

## Key Backend Services

| Service | File | Purpose |
|---------|------|---------|
| `llm_service` | services/llm_service.py | Multi-provider LLM |
| `intelligent_router` | services/intelligent_router.py | Task routing |
| `council_service` | services/council_service.py | Council orchestration |
| `voice_service` | services/voice_service.py | TTS/STT |
| `demo_council` | services/demo_council.py | Demo council |
| `demo_trace` | services/demo_trace.py | Demo tracing |
| `event_bus` | services/event_bus.py | WebSocket events |

---

## Total Counts

- **Route files**: 113
- **GET endpoints**: 470+
- **POST endpoints**: 350+
- **DELETE endpoints**: 22
- **PUT/PATCH endpoints**: 30+
