# Council Architecture Fixes & Enhancements

**Date**: 2025-01-XX  
**Status**: Implementation Plan

---

## 🎯 Architecture Clarification

### Correct Structure: 6 Agents Per Department
- **5 Advisors**: Expert AI agents trained on real-world experts
- **1 Synthesizer**: AI agent that synthesizes advisor inputs
- **Scouts**: Support/auxiliary agents (not counted in 6)

**Current Issue**: Scouts are treated as separate council members
**Fix**: Clarify that scouts are support agents, not council members

---

## 📋 Implementation Plan

### Phase 1: Architecture Fixes
1. ✅ Document 6-agent structure clearly
2. ✅ Update council service to reflect structure
3. ✅ Ensure scouts are treated as support agents

### Phase 2: Phase-Locked Integration
1. ✅ Integrate `council_scheduler.py` into routes
2. ✅ Add CMP validation phase
3. ✅ Enhance memory update integration

### Phase 3: Collaboration Enhancements
1. ✅ Cross-agent awareness system
2. ✅ Shared memory links
3. ✅ Expert-mindset consistency
4. ✅ Council automatic evolution

---

## 🔧 Detailed Fixes

### Fix 1: Agent Structure Documentation
**File**: `backend/services/council_service.py`
**Change**: Add clear documentation that 6 agents = 5 advisors + 1 synthesizer

### Fix 2: Phase-Locked Integration
**File**: `backend/routes/council.py`
**Change**: Use `council_scheduler.council_tick()` instead of manual flow

### Fix 3: CMP Validation
**File**: `backend/services/council_scheduler.py`
**Change**: Add CMP validation phase between Commit and Memory Update

### Fix 4: Cross-Agent Awareness
**New File**: `backend/services/agent_awareness.py`
**Purpose**: Track what each agent knows about others

### Fix 5: Shared Memory Links
**File**: `memory_service/router.py`
**Change**: Add memory linking between related council decisions

### Fix 6: Expert-Mindset Consistency
**File**: `backend/services/council_service.py`
**Change**: Add consistency checks for persona adherence

### Fix 7: Council Evolution
**New File**: `backend/services/council_evolution.py`
**Purpose**: Automatic improvement based on outcomes

---

**Next**: Begin implementation

