# Backend Route Map - Daena E2E Audit

## Critical Routes (Must Be Wired)

### Core Health & Status
| Route | Method | File | Frontend Caller | Status |
|-------|--------|------|-----------------|--------|
| `/health` | GET | main.py:1914 | Tool Console | ✅ Exists |
| `/api/v1/brain/status` | GET | brain.py | daena_office.html | ✅ Wired |
| `/api/v1/daena/status` | GET | daena.py | dashboard.js | ✅ Wired |

### Chat & Sessions
| Route | Method | File | Frontend Caller | Status |
|-------|--------|------|-----------------|--------|
| `/api/v1/daena/chat` | POST | daena.py:566 | daena_office.html | ✅ Wired |
| `/api/v1/daena/chat/{id}` | DELETE | daena.py:1094 | daena_office.html | ✅ Fixed |
| `/api/v1/chat-history/sessions` | GET | chat_history.py | daena_office.html | ✅ Wired |

### Voice
| Route | Method | File | Frontend Caller | Status |
|-------|--------|------|-----------------|--------|
| `/api/v1/voice/status` | GET | voice.py:38 | daena_office.html | ✅ Fixed |
| `/api/v1/voice/talk-mode` | POST | voice.py:82 | daena_office.html | ✅ Fixed |
| `/api/v1/voice/settings` | GET/POST | voice.py:57,74 | founder_panel.html | ✅ Wired |

### Departments & Agents
| Route | Method | File | Frontend Caller | Status |
|-------|--------|------|-----------------|--------|
| `/api/v1/departments/` | GET | departments.py | department pages | ✅ Wired |
| `/api/v1/agents/` | GET | agents.py | agent pages | ✅ Wired |

### Brain & Models
| Route | Method | File | Frontend Caller | Status |
|-------|--------|------|-----------------|--------|
| `/api/v1/brain/models` | GET | brain.py | brain_settings.html | ✅ Wired |
| `/api/v1/models/` | GET | model_registry.py | brain_settings.html | ✅ Fixed |

## Key Fixes Applied This Session

1. **model_registry.py** - Added singleton export
2. **main.py** - Fixed 20 sunflower_registry imports
3. **daena_office.html** - Fixed modal callback, voice toggle paths
4. **daena.py** - Added diagnostics tool pattern

## 108 Total Route Files Found
See `backend/routes/*.py` for complete list.
