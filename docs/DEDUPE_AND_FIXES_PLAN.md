# Duplicate Sweep & Broken Links - Cleanup Plan

**Date**: 2025-01-XX  
**Status**: 🔄 In Progress

---

## 📊 Inventory Summary

### Files Scanned
- **Total files**: Scanned memory_service, backend, docs, Tools
- **Exact duplicates**: 0 (by hash)
- **Same-name files**: 18 (some legitimate, some duplicates)
- **COMPLETE*.md files**: 75 ⚠️
- **SUMMARY*.md files**: 50 ⚠️
- **STATUS*.md files**: 17 ⚠️

---

## 🔍 Analysis Results

### Legitimate Same-Name Files (Keep Both)
1. `memory_service/abstract_store.py` vs `backend/routes/abstract_store.py`
   - ✅ Different: Implementation vs API routes
   - **Action**: Keep both

2. `memory_service/knowledge_distillation.py` vs `backend/routes/knowledge_distillation.py`
   - ✅ Different: Service vs API routes
   - **Action**: Keep both

3. All `__init__.py` files
   - ✅ Normal package structure
   - **Action**: Keep all

### Duplicate/Obsolute Files (Need Action)

1. **`backend/routers/health.py`** vs **`backend/routes/health.py`**
   - ⚠️ `routers/health.py`: Simple ping (3 lines)
   - ✅ `routes/health.py`: Full health check with council validation
   - **Action**: DELETE `backend/routers/health.py`, keep `routes/health.py`
   - **Risk**: Low - check if anything imports from `routers.health`

2. **`backend/routers/agents.py`** vs **`backend/routes/agents.py`**
   - **Action**: CHECK which one is used in main.py

3. **`backend/routers/llm.py`** vs **`backend/routes/llm.py`**
   - **Action**: CHECK which one is used

4. **`backend/routers/voice.py`** vs **`backend/routes/voice.py`**
   - **Action**: CHECK which one is used

5. **`backend/routes/tenant_rate_limit.py`** vs **`backend/middleware/tenant_rate_limit.py`**
   - **Action**: Likely one is routes, one is middleware - verify

### Documentation Duplicates

**COMPLETE*.md files (75 total)** - Need consolidation:
- Many are historical completion summaries
- Should consolidate to a few key files:
  - `DAENA_2_HARDENING_COMPLETE.md` - Main hardening completion
  - `docs/CURRENT_SYSTEM_STATUS.md` - Current status
  - Delete/archive: 70+ redundant completion files

**SUMMARY*.md files (50 total)** - Need consolidation:
- Similar to COMPLETE files
- Keep only essential summaries

**STATUS*.md files (17 total)** - Need consolidation:
- Keep: `docs/PHASE_STATUS_AND_NEXT_STEPS.md` (canonical)
- Delete: Others or archive

---

## 🛠️ Fix Plan

### Phase 1: Code Duplicates
1. ✅ Check which router files are actually used
2. Delete unused router files
3. Update imports in main.py if needed

### Phase 2: Documentation Consolidation
1. Keep canonical files:
   - `DAENA_2_HARDENING_COMPLETE.md`
   - `docs/PHASE_STATUS_AND_NEXT_STEPS.md`
   - `docs/CURRENT_SYSTEM_STATUS.md`
2. Move historical files to `docs/archive/` or delete
3. Update any references

### Phase 3: Broken Imports
1. Run mypy to find broken imports
2. Fix import paths
3. Verify with pytest

---

## 📋 Files to Delete (After Verification)

### Routers (if unused):
- `backend/routers/health.py` (if unused)

### Documentation (Historical):
- TBD after consolidation plan

---

## ✅ Acceptance Criteria

- [ ] `pytest -q` passes for NBMF and monitoring suites
- [ ] No duplicate symbols across memory_service, backend, frontend
- [ ] No unresolved imports (mypy)
- [ ] No unused modules (ruff)
- [ ] Documentation reduced from 142+ files to <20 essential files

---

## 🚨 Risk Notes

- **Low Risk**: Deleting unused router files
- **Medium Risk**: Consolidating documentation (ensure no broken links)
- **High Risk**: Deleting code files - verify imports first

---

**Next Steps**: 
1. Verify router usage in main.py
2. Create documentation archive
3. Execute deletions
4. Run tests

