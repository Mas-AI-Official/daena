# Daena AI VP - Architecture Audit & Fixes

**Date:** 2025-12-19  
**Status:** In Progress  
**Goal:** Production-ready, efficient, world-class system

---

## PART 1: BACKEND AUDIT

### ✅ LLM Router Status
- **Location:** `backend/services/llm_service.py`
- **Status:** GOOD - Has local-first priority (Ollama → cloud fallback)
- **Components:**
  - Deterministic Gate: ✅ Handles trivial tasks (math, time, JSON)
  - Complexity Scorer: ✅ Routes to appropriate model tier
  - Cost Guard: ✅ Enforces safety rules
  - Prompt Intelligence: ✅ Optimizes prompts
- **Issue:** Error message when Ollama unavailable is too verbose
- **Fix Needed:** Improve error message clarity

### ✅ Ollama Connectivity
- **Location:** `backend/services/local_llm_ollama.py`
- **Status:** GOOD - Properly configured with local_brain path
- **Models:** daena-brain:latest, qwen2.5:14b-instruct
- **Issue:** Model name matching needs improvement (handles :latest tags)
- **Fix Needed:** Already fixed in brain.py, verify it works

### ✅ CMP Integration
- **Location:** `backend/services/cmp_service.py`
- **Status:** GOOD - Thin orchestrator over tools registry
- **Issue:** CMP doesn't directly call LLM, routes through tools
- **Fix Needed:** Verify tools can call LLM service

### ⚠️ Health Endpoints
- **Location:** `backend/routes/health.py`
- **Status:** EXISTS - Has `/api/v1/health/`
- **Missing:** `/api/v1/llm/status` (exists in llm_status.py)
- **Missing:** `/api/v1/voice/status` (exists in voice.py)
- **Fix Needed:** Verify all endpoints are registered in main.py

---

## PART 2: BRAIN ARCHITECTURE

### ✅ Current Understanding
- **Reality:** Brain is orchestration layer, NOT trained model
- **Components:**
  - Local logic engine (deterministic gate)
  - Prompt optimizer (prompt_intelligence.py)
  - Model selector (complexity_scorer.py)
  - Memory + summarization (brain_store.py)
  - Tool & agent commander (CMP)
- **Status:** Architecture is correct, needs documentation

### ⚠️ Memory Summarization
- **Location:** `backend/core/brain/store.py`
- **Status:** EXISTS - Has governance queue and committed experiences
- **Missing:** Automatic summarization of long conversations
- **Fix Needed:** Add conversation summarization module

---

## PART 3: VOICE SYSTEM

### ❌ Current Issues
- **Location:** `backend/services/voice_service.py`
- **Problem:** Voice toggle triggers playback, not state
- **Problem:** TTS treated as "play audio file", not "stream voice"
- **Problem:** Replays full voice on each click
- **Fix Needed:** Convert to state-based system with streaming TTS

### ✅ Voice State Endpoint
- **Location:** `backend/routes/voice.py`
- **Status:** EXISTS - Has `/api/v1/voice/state`
- **Fix Needed:** Ensure it's properly used by frontend

---

## PART 4: FRONTEND

### ❌ Current Issues
- **Nested Scrollbars:** Multiple `overflow-y-auto` containers
- **Duplicate Pages:** Multiple dashboard variants
- **Mixed Concepts:** Executive Office vs Dashboard confusion
- **Agent Cards:** Not sortable/filterable
- **Voice Toggle:** Broken logic (plays full audio)

### ✅ Good Elements
- **Sunflower/Hive Visualization:** World-class, keep it
- **Executive Office Layout:** Good foundation, needs refinement

### Fixes Needed:
1. Single global layout (ChatGPT-style)
2. Fixed sidebar, single main scroll
3. Executive Office = main chat interface
4. Departments = office-style pages
5. Agents page cleaned and sortable
6. Remove duplicate UI and unused pages

---

## PART 5: UX QUALITY

### ❌ Current Issues
- Daena responses feel robotic and vague
- No visible system states (thinking, routing, consulting)
- Error messages too technical

### Fixes Needed:
1. Improve Daena personality prompt
2. Add visible system states
3. Humanize error messages
4. Add "thinking" indicators

---

## FIXES TO APPLY

### Priority 1: Critical Backend Fixes
1. ✅ Verify Ollama connectivity (DONE)
2. ✅ Fix brain status endpoint (DONE)
3. ⏳ Add comprehensive health endpoints
4. ⏳ Verify CMP can call LLM service
5. ⏳ Improve error messages

### Priority 2: Voice System Fix
1. ⏳ Convert voice toggle to STATE
2. ⏳ Implement streaming TTS
3. ⏳ Sync animation with audio
4. ⏳ Remove old playback logic

### Priority 3: Frontend Redesign
1. ⏳ Create single global layout
2. ⏳ Fix nested scrollbars
3. ⏳ Clean Executive Office
4. ⏳ Fix Agents page
5. ⏳ Remove duplicates

### Priority 4: UX Quality
1. ⏳ Improve Daena responses
2. ⏳ Add system states
3. ⏳ Humanize errors

---

## FILES TO CHANGE

### Backend
- `backend/routes/health.py` - Add comprehensive health check
- `backend/routes/llm_status.py` - Verify status endpoint
- `backend/routes/voice.py` - Fix voice state management
- `backend/services/voice_service.py` - Implement streaming TTS
- `backend/services/llm_service.py` - Improve error messages
- `backend/daena_brain.py` - Improve personality prompt

### Frontend
- `frontend/templates/daena_office.html` - Main chat interface
- `frontend/templates/dashboard.html` - Keep Sunflower, clean up
- `frontend/templates/agents.html` - Make sortable/filterable
- `frontend/templates/layout.html` - Single global layout
- Remove duplicate templates

---

## FILES TO DELETE

- `frontend/templates/enhanced_dashboard.html` (if duplicate)
- Unused department templates (if not needed)
- Old voice panel templates (if replaced)

---

## NEXT STEPS

1. Complete backend audit fixes
2. Fix voice system
3. Redesign frontend
4. Improve UX quality
5. Test end-to-end

