# Audit Report: Prompt Intelligence Brain + Local LLM Fix
**Date**: 2025-12-19  
**Target Folder**: `D:\Ideas\Daena_old_upgrade_20251213`

---

## STEP 0 — AUDIT FINDINGS

### ✅ What's Working

1. **LLM Service Methods EXIST**:
   - `generate_response()` - ✅ EXISTS (lines 137-220 in `llm_service.py`)
   - `generate_response_stream()` - ✅ EXISTS (lines 292-333)
   - `_fallback_generate()` - ✅ EXISTS (lines 446-477)

2. **Local LLM Layer EXISTS**:
   - `backend/services/local_llm_ollama.py` - ✅ EXISTS
   - `check_ollama_available()` - ✅ EXISTS
   - `generate()` - ✅ EXISTS
   - `chat()` - ✅ EXISTS

3. **Environment Variables Configured**:
   - `OLLAMA_BASE_URL` - ✅ Default: `http://localhost:11434`
   - `DEFAULT_LOCAL_MODEL` - ✅ Default: `qwen2.5:7b-instruct`
   - `TRAINED_DAENA_MODEL` - ✅ Default: `daena-brain`
   - `FALLBACK_MODEL` - ✅ Default: `llama3.2:3b`

4. **Call Path Verified**:
   - `daena_brain.process_message()` → `llm_service.generate_response()` ✅
   - `main.py` DaenaVP → `llm_service.generate_response()` ✅

---

## ❌ What's Broken

### Issue 1: `generate_response_stream()` Missing Local-First Logic

**Location**: `backend/services/llm_service.py` lines 292-333

**Problem**: 
- `generate_response_stream()` does NOT check Ollama first
- It only checks `if not self.providers:` and returns fallback message
- Should check Ollama availability BEFORE checking cloud providers
- Currently: Cloud → Fallback (skips Ollama)

**Current Code**:
```python
async def generate_response_stream(...):
    if not self.providers:
        yield "Local-first mode: cloud LLM disabled..."
        return
    # Goes straight to cloud providers, never checks Ollama
```

**Expected Behavior**:
1. Check Ollama first
2. If Ollama available → stream from Ollama
3. If Ollama unavailable AND cloud enabled → stream from cloud
4. If nothing available → stream fallback message

---

### Issue 2: No Prompt Intelligence Brain

**Problem**: 
- No central prompt optimizer exists
- All prompts are raw user input or basic templates
- No structured optimization, no provider-specific adapters
- No governance hooks for prompt versioning/transformation

**Missing Module**: `backend/services/prompt_intelligence.py`

**Required Features**:
- Normalized Intent Spec (model-agnostic)
- Provider Wrapper (model-specific)
- Rule-based optimization (cheap mode)
- Optional LLM-based rewrite (expensive mode)
- Governance hooks (versioning, allow/deny lists)

---

### Issue 3: Missing Config Variables

**Problem**: 
- No `PROMPT_BRAIN_ENABLED` config
- No `PROMPT_BRAIN_MODE` config
- No `PROMPT_BRAIN_COMPLEXITY_THRESHOLD` config

**Location**: `backend/config/settings.py`

---

## 📋 Callers of LLM Service Methods

### `generate_response()` Callers:
1. `backend/daena_brain.py:58` - `await llm.generate_response(prompt, max_tokens=800)`
2. `backend/main.py:473` - `await llm_service.generate_response(...)`
3. `backend/main.py:1561` - `await llm_service.generate_response(...)`
4. `backend/routes/departments.py:341` - `await llm_service.generate_response(...)`
5. `backend/routes/departments.py:403` - `await llm_service.generate_response(...)`
6. `backend/routes/departments.py:421` - `await llm_service.generate_response(...)`
7. `backend/services/council_service.py:419` - `await llm_service.generate_response(...)`
8. `backend/services/council_service.py:427` - `await llm_service.generate_response(...)`
9. `backend/routes/deep_search.py:169` - `await llm_service.generate_response(...)`
10. `backend/routes/deep_search.py:290` - `await llm_service.generate_response(...)`
11. `backend/routes/deep_search.py:346` - `await llm_service.generate_response(...)`

### `generate_response_stream()` Callers:
1. `backend/main.py:311` - `async for chunk in llm_service.generate_response_stream(...)`

### `_fallback_generate()` Callers:
1. `backend/scripts/test_voice_conversation.py:40` - `await llm_service._fallback_generate(...)`
2. Internal calls within `llm_service.py` (fallback chain)

---

## 🔧 Minimal Patch Plan

### Fix 1: Add Ollama Support to `generate_response_stream()`
**File**: `backend/services/llm_service.py`
**Location**: Lines 292-333
**Change**: Add Ollama check BEFORE checking `self.providers`
**Risk**: Low (additive change, doesn't break existing logic)

### Fix 2: Create Prompt Intelligence Brain
**File**: `backend/services/prompt_intelligence.py` (NEW)
**Risk**: Low (new module, doesn't modify existing code)

### Fix 3: Integrate Prompt Intelligence into LLM Service
**File**: `backend/services/llm_service.py`
**Location**: Inside `generate_response()` and `generate_response_stream()`
**Change**: Call prompt intelligence BEFORE calling Ollama/cloud
**Risk**: Medium (modifies core path, but only adds preprocessing)

### Fix 4: Add Config Variables
**File**: `backend/config/settings.py`
**Change**: Add Prompt Intelligence config fields
**Risk**: Low (additive, safe defaults)

### Fix 5: Wire to All Callers
**Change**: Automatic (all callers go through `llm_service.generate_response()`)
**Risk**: Low (transparent integration)

---

## 📊 Summary

**Status**: Methods exist, but:
- ❌ `generate_response_stream()` missing local-first logic
- ❌ No Prompt Intelligence Brain
- ❌ Missing config variables

**Impact**: 
- Streaming responses don't use Ollama (only non-streaming does)
- No prompt optimization (all prompts are raw)
- No provider-specific adapters

**Fix Complexity**: Low-Medium
- Streaming fix: ~10 lines
- Prompt Intelligence: New module (~200-300 lines)
- Integration: ~20 lines in `llm_service.py`

---

**Ready for PASS 2 Implementation**




