# ⚠️ CORE FILES — DO NOT DELETE OR REWRITE

**CRITICAL**: These files are the canonical core of the Daena system. They must NOT be deleted, renamed, or completely rewritten.

## Rules for Core Files

1. **Only patch specific functions** - Never replace full file content
2. **Never rename** - Keep exact file paths and class names
3. **Extend, don't replace** - Add adapter modules around core files if needed
4. **Test before changing** - Verify existing functionality before modifications

---

## Core Brain Files

### `backend/daena_brain.py`
**Purpose**: Canonical Daena Brain - the core AI reasoning layer

**Critical Components**:
- `DaenaBrain` class
- `process_message()` method
- `_build_prompt()` method
- `daena_brain` global instance

**Allowed Changes**:
- ✅ Bug fixes in existing methods
- ✅ Performance optimizations
- ✅ Adding new optional parameters
- ✅ Extending context handling

**Forbidden Changes**:
- ❌ Replacing entire class
- ❌ Removing `process_message()` method
- ❌ Changing delegation to `LLMService`
- ❌ Removing conversation history management

**Extension Pattern**: If new features needed, create `backend/services/daena_brain_extensions.py`

---

## Core Service Files

### `backend/services/llm_service.py`
**Purpose**: Canonical LLM service (local-first: Ollama → cloud fallback)

**Critical Components**:
- `LLMService` class
- `generate_response()` method
- Local-first routing logic

**Allowed Changes**:
- ✅ Adding new LLM providers
- ✅ Improving error handling
- ✅ Performance optimizations

**Forbidden Changes**:
- ❌ Removing local-first policy
- ❌ Breaking Ollama-first routing
- ❌ Removing fallback mechanisms

---

## Core Routing Files

### `backend/routes/daena.py`
**Purpose**: Main Daena chat endpoint

**Critical Components**:
- `POST /api/v1/daena/chat` endpoint
- Integration with `daena_brain.process_message()`
- Session management

**Allowed Changes**:
- ✅ Adding new endpoints
- ✅ Improving error handling
- ✅ Adding response formatting

**Forbidden Changes**:
- ❌ Removing `/api/v1/daena/chat` endpoint
- ❌ Bypassing `daena_brain` for chat
- ❌ Breaking session management

---

## Core CMP Files

### `backend/services/cmp_service.py`
**Purpose**: Cognitive Management Plane - routes tasks to agents/tools

**Critical Components**:
- `run_cmp_tool_action()` function
- Tool dispatch logic
- Audit logging

**Allowed Changes**:
- ✅ Adding new tools
- ✅ Improving routing logic
- ✅ Enhanced audit logging

**Forbidden Changes**:
- ❌ Removing CMP dispatch mechanism
- ❌ Breaking tool execution flow
- ❌ Removing audit logging

---

## Core Memory Files

### `backend/services/nbmf_memory.py` (if exists)
**Purpose**: NBMF memory storage and recall

**Critical Components**:
- Memory storage structure
- Recall mechanisms
- Performance-critical paths

**Allowed Changes**:
- ✅ Performance optimizations
- ✅ Bug fixes
- ✅ Adding new memory types

**Forbidden Changes**:
- ❌ Breaking recall performance
- ❌ Changing core memory structure
- ❌ Removing encryption (if present)

---

## Core Registry Files

### `backend/utils/sunflower_registry.py`
**Purpose**: Agent and department registry (8×6 structure)

**Critical Components**:
- `sunflower_registry` global instance
- Department/agent structure
- Registry initialization

**Allowed Changes**:
- ✅ Adding new agents/departments
- ✅ Improving registry loading
- ✅ Adding metadata

**Forbidden Changes**:
- ❌ Breaking 8×6 structure
- ❌ Removing registry initialization
- ❌ Changing core data structure

---

## How to Modify Core Files Safely

### Step 1: Read the file completely
Understand the full context before making changes.

### Step 2: Identify the exact function/method to change
Be specific - don't change more than necessary.

### Step 3: Make minimal patch
Change only the specific function, preserve surrounding code.

### Step 4: Test immediately
Run tests to verify functionality still works.

### Step 5: Document the change
Add comments explaining why the change was made.

---

## Extension Pattern

If you need to add features that might conflict with core files:

1. **Create extension module**: `backend/services/daena_brain_extensions.py`
2. **Import core**: `from backend.daena_brain import daena_brain`
3. **Wrap/extend**: Add new functionality around core, not replacing it
4. **Route through core**: Ensure all paths still go through canonical brain

**Example**:
```python
# backend/services/daena_brain_extensions.py
from backend.daena_brain import daena_brain

async def process_message_with_extensions(message: str, context: dict):
    # Pre-processing
    enhanced_context = add_extensions(context)
    
    # Use core brain
    response = await daena_brain.process_message(message, enhanced_context)
    
    # Post-processing
    return enhance_response(response)
```

---

## Verification

Before committing changes to core files:

1. Run `scripts/verify_no_truncation.py`
2. Run `scripts/verify_no_duplicates.py`
3. Run `pytest tests/` (if tests exist)
4. Manually test the affected functionality

---

**Last Updated**: 2025-12-13  
**Status**: Active Protection









