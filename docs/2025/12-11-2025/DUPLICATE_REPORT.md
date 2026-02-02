# Duplicate Router/Registry Report

## Duplicates Found

### 1. Model Routers

#### `backend/llm/model_router.py`
- **Purpose**: Basic task→provider mapping
- **Status**: ✅ **KEEP** - Integrated into unified router
- **Action**: Can be deprecated but keep for backward compatibility

#### `Core/model_gateway.py`
- **Purpose**: Hardware-aware routing (CPU/GPU/TPU)
- **Status**: ✅ **KEEP** - Different purpose (hardware, not task routing)
- **Action**: No change needed

#### `Core/llm/llm_router_core.py`
- **Purpose**: Very simple router (just returns "reflex")
- **Status**: ❌ **CAN REMOVE** - Too simple, not used
- **Action**: Mark for removal (check dependencies first)

#### `Core/kernel/model_router.py`
- **Purpose**: Simple model selection
- **Status**: ❌ **CAN REMOVE** - Too simple, superseded by unified router
- **Action**: Mark for removal (check dependencies first)

#### `Core/cmp/cmp_multimodel_router.py`
- **Purpose**: CMP-specific multi-model routing
- **Status**: 🟡 **REVIEW** - May be needed for CMP system
- **Action**: Keep for now, review later

### 2. Model Registries

#### `backend/services/model_registry.py`
- **Status**: ✅ **CANONICAL** - This is the main registry
- **Action**: No change

#### `backend/utils/sunflower_registry.py`
- **Purpose**: Department/agent registry (8×6 structure)
- **Status**: ✅ **KEEP** - Different purpose (org structure, not models)
- **Action**: No change

#### `backend/routes/registry.py`
- **Purpose**: API routes for registry
- **Status**: ✅ **KEEP** - API layer, not duplicate
- **Action**: No change

## Recommendations

### Immediate Actions
1. ✅ **Created unified router** - Consolidates routing logic
2. ✅ **Created adapter service** - Manages skill adapters
3. 🟡 **Mark simple routers for removal** - After verifying no dependencies

### Future Cleanup
1. Remove `Core/llm/llm_router_core.py` (if no dependencies)
2. Remove `Core/kernel/model_router.py` (if no dependencies)
3. Review `Core/cmp/cmp_multimodel_router.py` usage
4. Deprecate `backend/llm/model_router.py` (keep for compatibility)

### Before Removal
- Check all imports of these files
- Verify no tests depend on them
- Update any documentation references

## Summary

- **Total duplicates found**: 4 simple routers
- **Action taken**: Created unified router to replace them
- **Removed**: 0 (deferred to avoid breaking changes)
- **Marked for removal**: 2 (`Core/llm/llm_router_core.py`, `Core/kernel/model_router.py`)
- **Kept**: 2 (different purposes: hardware routing, CMP)


