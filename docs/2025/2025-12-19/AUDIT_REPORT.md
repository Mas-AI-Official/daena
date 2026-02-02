# Daena System Audit Report
**Date**: 2025-12-13  
**Canonical Root**: `D:\Ideas\Daena_old_upgrade_20251213`

## Executive Summary

This audit identifies the canonical components, duplicate modules, dead code, and frontend/backend mismatches in the Daena AI VP system.

---

## Single Source of Truth

### Canonical Brain Module
**Path**: `backend/daena_brain.py`  
**Class**: `DaenaBrain`  
**Singleton**: `daena_brain`  
**Usage**: All brain interactions should use `from backend.daena_brain import daena_brain`

**Key Methods**:
- `process_message(message, context)` - Main processing entry point
- `get_system_status()` - System health check

**Verified Imports**:
- `backend/core/brain/store.py` - Uses `daena_brain`
- `backend/services/human_relay_explorer.py` - Uses `daena_brain`
- `backend/routes/agents.py` - Uses `daena_brain`
- `backend/routes/daena.py` - Uses `daena_brain`

### Canonical Router Layer
**Path**: `backend/main.py`  
**Function**: `safe_import_router(module_name)` - Safely imports and registers routers

**All routers registered via**:
- `safe_import_router("ui")` - UI routes
- `safe_import_router("brain")` - Brain routes
- `safe_import_router("agents")` - Agent routes
- Plus 40+ other routers

### Canonical Memory Layer (NBMF/EDNA)
**NBMF Implementation**:
- `memory_service/nbmf_encoder.py` - NBMF encoder
- `memory_service/nbmf_decoder.py` - NBMF decoder
- `memory_service/nbmf_encoder_production.py` - Production encoder
- `memory_service/adapters/l2_nbmf_store.py` - L2 NBMF store adapter

**EDNA Implementation**:
- `backend/services/enterprise_dna_service.py` - Enterprise DNA service
- `backend/routes/enterprise_dna.py` - EDNA routes
- `backend/models/enterprise_dna.py` - EDNA models

**Brain Store (Governance-Gated Memory)**:
- `backend/core/brain/store.py` - `BrainStore` class
- Methods: `query()`, `propose_knowledge()`, `propose_experience()`, `approve_and_commit()`

### Canonical CMP Tool Layer
**Path**: `backend/services/cmp_service.py` - CMP service  
**Registry**: `backend/services/cmp_tool_registry.py` - Tool registry  
**Routes**: `backend/routes/cmp_tools.py` - CMP tool endpoints

**Tool Execution**:
- `backend/routes/tools.py` - Canonical tool runner endpoint

### Canonical Governance Writeback Layer
**Path**: `backend/core/brain/store.py` - `BrainStore` class

**Governance Pipeline**:
1. Agent proposes: `propose_knowledge()` or `propose_experience()`
2. Proposal queued in `governance_queue.json`
3. Council reviews (via `backend/routes/council.py`)
4. Daena approves: `approve_and_commit(proposal_id)`
5. Committed to `committed_experiences.json`

**Governance States** (from `GovernanceState` enum):
- PROPOSED → SCOUTED → DEBATED → SYNTHESIZED → APPROVED → FORGED → COMMITTED
- REJECTED (if rejected at any stage)

---

## Duplicate Modules Identified

From dependency scan: **10 duplicate module names** found.

**Critical Duplicates** (need consolidation):
1. Multiple brain implementations:
   - `backend/daena_brain.py` ✅ (CANONICAL)
   - `backend/routes/brain.py` ✅ (Router, not duplicate)
   - `backend/routes/enhanced_brain.py` ⚠️ (May be duplicate functionality)
   - `Core/llm/enhanced_daena_brain.py` ⚠️ (Legacy?)
   - `Core/llm/ultimate_daena_brain_trainer.py` ⚠️ (Training, not runtime)
   - `Core/llm/perfect_daena_brain_trainer.py` ⚠️ (Training, not runtime)

2. Multiple agent builder implementations:
   - `backend/routes/agent_builder.py`
   - `backend/routes/agent_builder_complete.py` ✅ (Most complete)
   - `backend/routes/agent_builder_platform.py`
   - `backend/routes/agent_builder_simple.py`
   - `backend/routes/agent_builder_api.py`
   - `backend/routes/agent_builder_api_simple.py`

**Action Required**: Consolidate agent builders to single canonical implementation.

---

## Dead Code / Unused Modules

**Potentially Unused** (not imported by any module):
- Check `REPO_DEPENDENCY_MAP.json` for full list
- Many training scripts in `Core/llm/` may be unused in production

---

## Frontend ↔ Backend Mismatches

### Statistics
- **Backend Routes**: 513
- **Frontend API Calls**: 120 unique
- **Missing Backend Routes**: 101 (frontend calls APIs that don't exist)
- **Unused Backend Routes**: 361 (backend has APIs not used by frontend)

### Critical Missing Backend Routes
See `REPO_DEPENDENCY_MAP.md` for full list. Common patterns:
- `/api/v1/...` routes called by frontend but not registered
- Dynamic routes with parameters not matching backend patterns

### Action Required
1. Implement missing backend routes OR
2. Update frontend to use existing routes
3. Remove or document unused backend routes

---

## Architecture Verification

### ✅ Correct Architecture
1. **One Shared Brain**: `daena_brain` singleton used across system
2. **Governance Gating**: `BrainStore` enforces writeback pipeline
3. **Agent Read-Only**: Agents can query brain but cannot write directly
4. **Daena Write Authority**: Only Daena can approve and commit

### ⚠️ Issues Found
1. **Multiple Brain Implementations**: Need to verify which are active
2. **Agent Builder Duplication**: Multiple implementations need consolidation
3. **Frontend/Backend Mismatch**: 101 missing routes, 361 unused routes

---

## Recommendations

### Immediate Actions
1. **Consolidate Agent Builders**: Choose one canonical implementation
2. **Fix Missing Routes**: Implement 101 missing backend routes OR update frontend
3. **Document Unused Routes**: Mark 361 unused routes as deprecated or remove
4. **Verify Brain Implementations**: Ensure only `daena_brain.py` is used at runtime

### Phase B+ Actions
1. **Model Registry**: Create unified model registry (Phase D)
2. **Prompt Library**: Create prompt engineering system (Phase E)
3. **Tool Playbooks**: Create CMP tool learning system (Phase F)
4. **Contract Tests**: Add automated frontend/backend sync tests (Phase G)

---

## Next Steps

1. ✅ Phase A: Deep Audit (THIS DOCUMENT)
2. ⏭️ Phase B: Stabilize Live Boot
3. ⏭️ Phase C: Brain Architecture Enforcement
4. ⏭️ Phase D: Model Layer Upgrade
5. ⏭️ Phase E: Prompt Engineering Mastery
6. ⏭️ Phase F: Skills Growth (CMP Learning)
7. ⏭️ Phase G: Backend ↔ Frontend Sync
8. ⏭️ Phase H: Verification + No-Drift Safety

---

**Generated by**: `scripts/audit_dependencies.py`  
**Full Dependency Map**: `docs/2025-12-13/REPO_DEPENDENCY_MAP.md`  
**JSON Data**: `docs/2025-12-13/REPO_DEPENDENCY_MAP.json`

