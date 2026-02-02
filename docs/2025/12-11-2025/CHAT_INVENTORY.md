# Chat System Inventory

## Existing Chat Routes

### 1. Main Chat Endpoints
**File**: `backend/main.py`

**Endpoints**:
- `POST /api/v1/chat` - Universal chat endpoint (line 1950)
  - Supports streaming (`text/event-stream`)
  - Uses `daena.process_message()` or `daena.process_message_stream()`
  - Context-aware

- `POST /api/v1/daena/chat` - Direct Daena chat (line 1935)
  - Uses `daena.process_message()`
  - Returns JSON response

- `POST /api/v1/daena/executive-chat` - Executive chat (line 1609)
  - Enhanced executive context
  - Dynamic max_tokens based on query type

- `WebSocket /ws/chat` - Real-time WebSocket chat (line 1878)
  - Uses `daena.process_message()`
  - Maintains active connections

### 2. DaenaVP Class
**File**: `backend/main.py` (line 65)

**Methods**:
- `process_message(message, context)` - Main message processing (line 323)
  - Uses LLM service if available
  - Builds system prompt with real system state
  - Has conversation rules (greeting only once, etc.)
  - Returns string response

- `process_message_stream(message, context)` - Streaming version (line 221)
  - Yields chunks as they're generated
  - Uses `llm_service.generate_response_stream()`

**Current System Prompt** (embedded in code, line 274-439):
- Defines Daena as AI VP
- Has conversation rules (greeting only once)
- Includes real system state
- **Issue**: Hard-coded in Python, not configurable

### 3. Department Chat
**File**: `backend/routes/internal/departments.py` (line 214)

- `POST /api/v1/departments/{department_id}/chat`
- Uses `DaenaBrain` for agent responses
- Department-specific context

### 4. Conference Room Chat
**File**: `backend/routes/conference_room.py` (line 418)

- `generate_ai_response()` - Uses council service LLM
- `generate_councilor_response()` - Councilor-specific responses

## Current Greeting/Verbosity Handling

### Greeting Detection
- **Current**: Hard-coded rule in system prompt (line 422)
  - "Use 'Hey boss!' ONLY for the very first greeting"
  - No automatic detection of greeting messages
  - Relies on conversation state tracking

### Verbosity Control
- **Current**: None
- Responses can be verbose
- No post-processing to trim length
- No configurable style settings

### System Prompt Location
- **Current**: Embedded in `DaenaVP.process_message()` (line 274-439)
- **Issue**: Not in separate file, hard to modify
- **Issue**: Mixed with code logic

## Response Generation Flow

1. User sends message → `/api/v1/chat`
2. `daena.process_message()` called
3. System prompt built (embedded in code)
4. LLM service generates response
5. Response returned as-is (no post-processing)

## Issues Found

1. ❌ **No separate persona file** - System prompt hard-coded
2. ❌ **No style controller** - No verbosity trimming
3. ❌ **No greeting detection** - Relies on conversation state
4. ❌ **No configurable style** - Can't adjust tone/length
5. ❌ **No post-processing** - Responses can be verbose

## Integration Points

### Where to Add Style Controller
- `DaenaVP.process_message()` - After LLM response, before returning
- `DaenaVP.process_message_stream()` - After full response assembled
- All chat endpoints that call `process_message()`

### Where to Add Persona File
- Create `prompts/system/daena_persona.txt`
- Load in `DaenaVP.process_message()` instead of hard-coded prompt

### Where to Add Greeting Detection
- In chat endpoints before calling `process_message()`
- Pass `is_greeting` flag to style controller

## Summary

**Current State**:
- ✅ Chat routes exist and work
- ✅ Streaming support exists
- ❌ No style controller
- ❌ No persona file
- ❌ No greeting detection
- ❌ No verbosity control

**Action Needed**:
1. Create persona file
2. Create style controller
3. Integrate into existing chat flow
4. Add greeting detection
5. Add UI control (optional)


