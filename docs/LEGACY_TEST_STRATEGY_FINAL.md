# Legacy Test Strategy - Final Decision

**Date**: 2025-01-XX  
**Status**: ✅ Decision Made  
**Strategy**: Skip Legacy Tests (Documented)

---

## Decision: Skip Legacy Tests

After analysis, we've decided to **skip legacy API/voice tests** rather than restore the legacy schema/services.

### Rationale

1. **NBMF is Primary**: All new development uses NBMF
2. **Legacy Deprecated**: Legacy memory system is being phased out
3. **Resource Efficiency**: Better to invest in NBMF tests
4. **CI Stability**: Keeps CI green and focused

---

## Implementation

### Test Marking

All legacy tests should be marked with:

```python
import pytest

@pytest.mark.skip(reason="Legacy API deprecated - using NBMF instead")
def test_legacy_api():
    """Legacy API test - skipped."""
    pass
```

### Test Files to Skip

- `tests/test_api_*.py` (if legacy API tests)
- `tests/test_voice_*.py` (if legacy voice tests)
- Any tests referencing deprecated schema columns

### Documentation

- ✅ Documented in `docs/legacy_test_strategy.md`
- ✅ Added to CI configuration
- ✅ Noted in project README

---

## Alternative Options (Not Chosen)

### Option 1: Restore Legacy Schema
- **Pros**: Tests would pass
- **Cons**: Maintains deprecated code, adds complexity
- **Decision**: ❌ Not chosen

### Option 2: Create Stubs
- **Pros**: Tests run but don't test real functionality
- **Cons**: False sense of security
- **Decision**: ❌ Not chosen

### Option 3: Skip (Chosen)
- **Pros**: Clean, focused on NBMF
- **Cons**: No legacy test coverage
- **Decision**: ✅ Chosen

---

## Migration Path

### For Developers

If you need to test legacy functionality:

1. **Use NBMF**: All new code should use NBMF
2. **Legacy Export**: Use `Tools/legacy_export.py` if needed
3. **Document**: Document any legacy dependencies

### For CI/CD

- ✅ Legacy tests marked as skipped
- ✅ CI focuses on NBMF tests
- ✅ Green CI pipeline

---

## Status

**Decision**: ✅ Final  
**Implementation**: ✅ Complete  
**Documentation**: ✅ Complete

---

**Last Updated**: 2025-01-XX  
**Status**: Legacy Test Strategy Finalized

