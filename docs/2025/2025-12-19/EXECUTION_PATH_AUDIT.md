# Execution Path Audit - Model Selection Rubric

**Date**: 2025-12-19  
**Purpose**: Map where messages enter, where decisions are made, and where LLM calls happen.

## Chat Entrypoints

### REST Endpoints
1. **`POST /api/v1/daena/chat`** (daena.py:148)
   - Handler: `send_message_to_daena()`
   - Calls: `daena_brain.process_message()`
   - Flow: User → REST → daena_brain → llm_service

2. **`POST /api/v1/daena/chat/{session_id}/message`** (daena.py:174)
   - Handler: `send_message_to_daena()`
   - Same flow as above

3. **`POST /api/v1/agents/{agent_id}/chat`** (agents.py:366)
   - Handler: Agent-specific chat
   - Should also use daena_brain (needs verification)

4. **`POST /api/v1/departments/{department_id}/chat`** (departments.py:291)
   - Handler: Department chat
   - Should also use daena_brain (needs verification)

### WebSocket Endpoints
1. **`WS /ws/chat`** (daena.py:252) - **PRIMARY**
   - Handler: `daena_websocket_simple()`
   - Calls: `send_message_to_daena()` → `daena_brain.process_message()`
   - Frontend uses this endpoint

2. **`WS /ws/chat/{session_id}/ws`** (daena.py:313) - Legacy
   - Handler: `daena_websocket()`
   - Same flow

## Brain & Decision Points

### Canonical Brain
- **File**: `backend/daena_brain.py`
- **Class**: `DaenaBrain`
- **Method**: `process_message(message, context)`
- **Flow**: 
  1. Builds prompt via `_build_prompt()`
  2. Delegates to `llm_service.generate_response()`
  3. Returns response

### LLM Service (Single Source of Truth)
- **File**: `backend/services/llm_service.py`
- **Class**: `LLMService`
- **Method**: `generate_response(prompt, provider, model, temperature, max_tokens, context)`
- **Current Flow**:
  1. Apply Prompt Intelligence (if enabled)
  2. Check Ollama first (local-first)
  3. Fall back to cloud providers if available
  4. Return fallback message if nothing available

## Router Status

### Active Router
- **`backend/services/llm_service.py`** ✅ ACTIVE
  - Used by: daena_brain.py, all chat endpoints
  - Single source of truth

### Deprecated Router
- **`backend/llm/model_router.py`** ⚠️ DEPRECATED
  - Not imported anywhere
  - Marked as deprecated
  - Can be safely ignored

## Integration Points for Model Selection Rubric

### Where to Add Deterministic Gate
- **Location**: `llm_service.generate_response()` - BEFORE Prompt Intelligence
- **Check**: If deterministic_gate handles it, return immediately (no LLM call)

### Where to Add Complexity Scorer
- **Location**: `llm_service.generate_response()` - AFTER deterministic gate, BEFORE provider selection
- **Purpose**: Determine which model tier to use

### Where Prompt Intelligence Runs
- **Location**: `llm_service.generate_response()` - Already integrated (line 148-179)
- **Status**: ✅ Already working
- **Enhancement**: Add complexity-aware optimization

### Where Provider Selection Happens
- **Location**: `llm_service.generate_response()` - Lines 181-253
- **Current**: Local-first (Ollama) → Cloud → Fallback
- **Enhancement**: Add complexity-based model selection within tiers

## Current Architecture

```
User Message
    ↓
REST/WebSocket Endpoint
    ↓
daena_brain.process_message()
    ↓
llm_service.generate_response()
    ↓
[Prompt Intelligence] ← Already integrated
    ↓
[Ollama Check] ← Local-first
    ↓
[Cloud Provider] ← If Ollama unavailable
    ↓
[Fallback Message] ← If nothing available
```

## Proposed Architecture (After Rubric)

```
User Message
    ↓
REST/WebSocket Endpoint
    ↓
daena_brain.process_message()
    ↓
llm_service.generate_response()
    ↓
[Deterministic Gate] ← NEW: Handle trivial tasks
    ↓ (if not handled)
[Complexity Scorer] ← NEW: Score 0-10
    ↓
[Prompt Intelligence] ← Enhanced: Complexity-aware
    ↓
[Model Selection] ← NEW: Based on complexity tier
    ↓
[Provider Selection] ← Enhanced: Local-first + tier-aware
    ↓
[Cost Guard] ← NEW: Safety checks
    ↓
[Execute LLM Call]
    ↓
[Return Response]
```

## Next Steps

1. ✅ Audit complete
2. ⏳ Create deterministic_gate.py
3. ⏳ Create complexity_scorer.py
4. ⏳ Enhance prompt_intelligence.py
5. ⏳ Integrate into llm_service.py
6. ⏳ Add cost_guard.py
7. ⏳ Create tests




