# Daena AI VP System - Comprehensive Audit Report
**Date:** 2025-01-23
**Scope:** Backend routes vs Frontend calls, Chat storage, Session lifecycle

## 1. BACKEND ROUTES AUDIT

### Chat Endpoints (Current State)
- ✅ `POST /api/v1/chat-history/sessions` - Creates session, returns session_id
- ✅ `GET /api/v1/chat-history/sessions` - Lists all sessions
- ✅ `GET /api/v1/chat-history/sessions/{session_id}` - Gets specific session
- ✅ `POST /api/v1/chat-history/sessions/{session_id}/messages` - Adds message
- ✅ `GET /api/v1/departments/{dept_id}/chat/sessions` - Lists department sessions
- ✅ `POST /api/v1/departments/{dept_id}/chat` - Department chat (may not use session_id)
- ✅ `POST /api/v1/daena/chat` - Daena chat (may not use session_id)
- ✅ `POST /api/v1/daena/chat/start` - Starts Daena session

### Issues Found
1. **Department chat endpoint** (`/api/v1/departments/{dept_id}/chat`) may not enforce session creation
2. **Daena chat endpoint** (`/api/v1/daena/chat`) may accept messages without session_id
3. **Session creation** sometimes fails silently (returns null/undefined)

## 2. FRONTEND CALLS AUDIT

### Daena Office Chat
- Calls: `POST /api/v1/chat-history/sessions` ✅
- Expects: `{session_id}` in response ✅
- Issue: May not handle missing session_id gracefully

### Department Chat
- Calls: `POST /api/v1/chat-history/sessions` for creation ✅
- Calls: `POST /api/v1/departments/{dept_id}/chat` for messages ⚠️
- Issue: Department chat endpoint may not require/use session_id

## 3. CHAT STORAGE AUDIT

### Current Storage
- **Primary:** SQLite via `ChatSession` and `ChatMessage` models ✅
- **Fallback:** JSON file storage (backward compatibility) ⚠️
- **Scope Support:** 
  - `scope_type`: executive, department, agent, general ✅
  - `scope_id`: department_id, agent_id, "daena" ✅

### Issues
1. Two competing storage systems (SQLite + JSON)
2. Department chats may not appear in Daena's chat list
3. No single source of truth enforcement

## 4. SESSION LIFECYCLE ISSUES

### Problem: "No session_id" Error
**Root Cause Analysis:**
- Session creation endpoint exists and should return session_id
- Frontend may not wait for session creation before sending messages
- Some endpoints accept messages without session_id (fallback behavior)

### Fix Required:
1. Enforce session creation before message sending
2. All chat endpoints must require session_id
3. Frontend must handle session creation errors gracefully

## 5. REAL-TIME SYNC AUDIT

### Current WebSocket
- `/ws/events` - General event stream ✅
- `/ws/chat/{session_id}` - Chat-specific (may not exist) ⚠️
- `/ws/council` - Council updates ✅

### Issues
- No unified event bus
- Events may not persist to database
- Frontend may not subscribe to all necessary events

## 6. VOICE SYSTEM AUDIT

### Current State
- Two environments: main backend + audio env
- `START_DAENA.bat` - Main backend launcher
- `START_AUDIO_ENV.bat` - Audio service launcher
- Voice endpoints: `/api/v1/voice/status`, `/api/v1/voice/speak` (may be missing)

### Issues
- Voice environment may not activate reliably
- `daena_voice.wav` cloning may not work
- Agents may not have unique voice IDs

## 7. COUNCIL SYSTEM AUDIT

### Current Endpoints
- `GET /api/v1/council/list` - Lists councils (returns empty) ❌
- `POST /api/v1/council/{council_id}/toggle` - Toggle council ✅
- Missing: Create council, debate start, synthesis storage

### Issues
- Councils not being seeded/returned properly
- No debate session storage
- No synthesis result storage

## 8. INTELLIGENCE ROUTING (NEW REQUIREMENT)

### Required
- Add intelligence dimension scoring (IQ/EQ/AQ/Execution)
- Route queries to appropriate agent/model based on intelligence needs
- Merge outputs into single response
- Store intelligence scores in audit log

### Current State
- Router exists but may not have intelligence dimension scoring
- Need to add intelligence evaluation layer

## PRIORITY FIX ORDER

1. **CRITICAL:** Fix session creation flow (ensure session_id always returned)
2. **CRITICAL:** Enforce session_id requirement in all chat endpoints
3. **HIGH:** Fix department chat history visibility
4. **HIGH:** Implement unified event bus
5. **MEDIUM:** Fix voice system activation
6. **MEDIUM:** Fix council system end-to-end
7. **LOW:** Add intelligence routing layer


