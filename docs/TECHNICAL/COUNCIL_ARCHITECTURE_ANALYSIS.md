# Council Architecture Analysis & Fixes

**Date**: 2025-01-XX  
**Status**: Analysis Complete, Fixes Identified

---

## 🔍 Current Architecture Analysis

### Agent Structure Per Department

**Expected**: 6 agents per department
- 5 Advisors (trained like real-world experts)
- 1 Synthesizer

**Current Implementation**:
- ✅ 5 Advisors (correct)
- ❌ 2 Scouts (should be part of advisors or separate, but not counted in 6)
- ✅ 1 Synthesizer (correct)
- **Total**: 8 agents (should be 6)

**Issue**: Scouts are separate from the 6-agent structure. They should either be:
1. Integrated into advisor roles (scout_internal/scout_external as advisor types), OR
2. Counted separately but the 6-agent structure should be: 4 advisors + 1 scout + 1 synthesizer

**Recommendation**: Keep scouts separate but clarify that the 6-agent council structure is:
- 4 Advisors (debate)
- 1 Scout (gathers intelligence) 
- 1 Synthesizer (synthesizes)

OR maintain current but document that scouts are support agents, not council members.

---

## ✅ Phase-Locked Council Rounds Analysis

### Current Implementation Status

**File**: `backend/services/council_scheduler.py`

**Phases Implemented**:
1. ✅ **Scout Phase** - Scouts publish NBMF summaries
2. ✅ **Debate Phase** - Advisors exchange counter-drafts
3. ✅ **Commit Phase** - Executor commits to NBMF

**Missing Phases**:
4. ❌ **CMP Validation** - Not implemented
5. ⚠️ **Memory Update** - Partially implemented (writes to NBMF but not full integration)

**Integration Status**:
- ⚠️ Phase-locked rounds exist but not fully integrated with `council_service.py`
- ⚠️ Routes use old non-phase-locked flow
- ✅ Scheduler exists and works independently

---

## 🔧 Issues Identified

### 1. Agent Count Mismatch
**Issue**: Expected 6 agents (5 advisors + 1 synthesizer), but scouts are separate
**Location**: `backend/services/council_service.py:78-183`
**Fix**: Clarify architecture or adjust agent count

### 2. Phase-Locked Rounds Not Integrated
**Issue**: `council_scheduler.py` exists but routes use old flow
**Location**: `backend/routes/council.py`
**Fix**: Integrate phase-locked scheduler into routes

### 3. Missing CMP Validation
**Issue**: No CMP (Council Memory Protocol) validation step
**Location**: Missing entirely
**Fix**: Add CMP validation phase

### 4. Cross-Agent Awareness
**Issue**: Limited awareness between agents
**Location**: Multiple files
**Fix**: Enhance shared memory and awareness

### 5. Shared Memory Links
**Issue**: No explicit memory linking between agents
**Location**: Missing
**Fix**: Implement memory linking system

### 6. Expert-Mindset Consistency
**Issue**: Personas exist but consistency not verified
**Location**: `council_service.py:46-62`
**Fix**: Add consistency checks

### 7. Council Automatic Evolution
**Issue**: No automatic improvement/evolution
**Location**: Missing
**Fix**: Add evolution mechanism

---

## 📋 Phase 7 Features Status

### ✅ Implemented
1. **Hex-Mesh Message Bus** - `backend/utils/message_bus_v2.py` ✅
2. **Phase-Locked Rounds** - `backend/services/council_scheduler.py` ✅
3. **Quorum Logic** - `backend/utils/quorum.py` ✅
4. **Presence Beacons** - `backend/services/presence_service.py` ✅
5. **Topic Routing** - `backend/utils/message_bus_v2.py` ✅
6. **Abstract + Lossless Pointer** - `memory_service/abstract_store.py` ✅

### ⚠️ Partially Implemented
- Phase-locked rounds exist but not fully integrated
- Abstract + pointer pattern exists but not used in council flow

---

## 🎯 Recommended Fixes

### Priority 1: Architecture Clarification
1. Document agent structure clearly (6 agents = 5 advisors + 1 synthesizer, scouts are support)
2. OR adjust to 4 advisors + 1 scout + 1 synthesizer = 6

### Priority 2: Integration
1. Integrate phase-locked scheduler into council routes
2. Add CMP validation phase
3. Enhance memory update integration

### Priority 3: Enhancements
1. Cross-agent awareness system
2. Shared memory links
3. Expert-mindset consistency checks
4. Council automatic evolution

---

**Next**: Implement fixes based on this analysis

