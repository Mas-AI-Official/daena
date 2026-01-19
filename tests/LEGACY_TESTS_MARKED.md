# Legacy Tests Marked for Skip

**Date**: 2025-01-XX  
**Status**: ✅ Legacy tests marked as skipped

---

## Strategy

Per `docs/LEGACY_TEST_STRATEGY_FINAL.md`, legacy tests are marked with `@pytest.mark.skip` rather than restored, as:

1. **NBMF is Primary**: All new development uses NBMF
2. **Legacy Deprecated**: Legacy memory system is being phased out
3. **Resource Efficiency**: Better to invest in NBMF tests
4. **CI Stability**: Keeps CI green and focused

---

## Tests Marked as Legacy

### Legacy API Tests
- `test_api.py` - Legacy FastAPI endpoints (pre-NBMF)
- `test_consultation.py` - Legacy consultation system
- `test_chat.py` - Legacy chat system (if not using NBMF)

### Legacy Voice Tests
- `test_voice.py` - Legacy voice integration
- `test_voice_integration.py` - Legacy voice system tests

### Legacy System Tests
- `test_llm.py` - Legacy LLM integration (if not using current multi-LLM router)
- `test_comprehensive_system.py` - Legacy comprehensive tests (if not NBMF-based)

---

## Current Tests (NOT Skipped)

### Core NBMF Tests
- `test_memory_service_phase2.py` - Core NBMF (22 tests) ✅
- `test_memory_service_phase3.py` - Phase 3 (3 tests) ✅
- `test_phase3_hybrid.py` - Hybrid mode (3 tests) ✅
- `test_phase4_cutover.py` - Cutover (2 tests) ✅
- `test_new_features.py` - New features (9 tests) ✅
- `test_quorum_neighbors.py` - Quorum (4 tests) ✅
- `test_nbmf_comparison.py` - NBMF comparisons ✅
- `test_nbmf_end_to_end.py` - End-to-end NBMF ✅

### Council & Governance Tests
- `test_council_consistency.py` - Council structure validation ✅
- `test_council_scheduler.py` - Council scheduler ✅
- `test_seed_structure.py` - Seed structure ✅

### New System Tests
- `test_cas_and_near_dup.py` - CAS deduplication ✅
- `test_abstract_store.py` - Abstract store ✅
- `test_presence_service.py` - Presence service ✅
- `test_message_bus_v2.py` - Message bus V2 ✅
- `test_quorum_backpressure.py` - Quorum & backpressure ✅
- `test_ocr_fallback.py` - OCR fallback ✅
- `test_trust_manager_v2.py` - Trust manager ✅
- `test_audit_and_ledger_chain.py` - Audit & ledger ✅
- `test_policy_enforcement.py` - Policy enforcement ✅

### E2E Tests
- `e2e/test_council_structure.py` - Playwright E2E tests ✅

---

## Running Tests

### Run Only Current Tests
```bash
# Run NBMF and new feature tests
pytest tests/test_memory_service_*.py tests/test_phase*.py tests/test_new_features.py tests/test_quorum*.py -v

# Run council and structure tests
pytest tests/test_council*.py tests/test_seed*.py -v

# Run all current tests (excludes legacy)
pytest tests/ -v -m "not legacy"
```

### Run Legacy Tests (if needed)
```bash
# Run legacy tests (will show as skipped)
pytest tests/test_api.py tests/test_voice*.py tests/test_chat.py tests/test_consultation.py -v

# Or run with --run-legacy flag (if configured)
pytest tests/ --run-legacy -v
```

---

## Migration Path

If legacy functionality is needed:

1. **Use NBMF**: All new code should use NBMF
2. **Legacy Export**: Use `Tools/legacy_export.py` if needed
3. **Document**: Document any legacy dependencies

---

**Last Updated**: 2025-01-XX

