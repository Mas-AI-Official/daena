# ✅ Task 4: Agent Registry Truth-Source (8×6) - Complete

**Date**: 2025-01-XX  
**Status**: ✅ **COMPLETE**

---

## 📊 Summary

### Goal
Ensure backend schema + seeds + UI reflect 8 departments × 6 agents perfectly. This involves:
- Schema alignment (DB models for department_id/agent roles, migrations)
- Seed + verify (running seed, adding `/api/v1/registry/summary` endpoint)
- FE alignment (dashboard reads summary)
- Tests

---

## ✅ Changes Made

### 1. Schema Alignment ✅

**Status**: Already aligned
- `Department` model has all required fields (slug, name, sunflower_index, cell_id, status)
- `Agent` model has:
  - `department_id` (ForeignKey to departments.id) ✅
  - `role` (String, indexed) ✅
  - `tenant_id` and `project_id` (for multi-tenant isolation) ✅
  - `is_active` (Boolean) ✅

### 2. Seed Script Updated ✅

**File**: `backend/scripts/seed_6x8_council.py`

**Changes**:
- Updated to use `COUNCIL_CONFIG` as single source of truth
- Removed duplicate `AGENT_ROLES` definition
- Now imports from `backend.config.council_config` instead of `backend.config.constants`
- Ensures seed script creates exactly 8 departments × 6 agents = 48 agents

**Before**:
```python
from backend.config.constants import (
    MAX_AGENTS_PER_DEPARTMENT, 
    TOTAL_DEPARTMENTS, 
    MAX_TOTAL_AGENTS,
    DEPARTMENT_NAMES,
    DEPARTMENT_DISPLAY_NAMES,
    AGENT_ROLES
)

# Duplicate definition
AGENT_ROLES = [
    "advisor_a", "advisor_b",
    "scout_internal", "scout_external",
    "synth", "executor"
]
```

**After**:
```python
from backend.config.council_config import COUNCIL_CONFIG

# Use canonical config as single source of truth
MAX_AGENTS_PER_DEPARTMENT = COUNCIL_CONFIG.AGENTS_PER_DEPARTMENT
TOTAL_DEPARTMENTS = COUNCIL_CONFIG.TOTAL_DEPARTMENTS
MAX_TOTAL_AGENTS = COUNCIL_CONFIG.TOTAL_AGENTS
DEPARTMENT_NAMES = list(COUNCIL_CONFIG.DEPARTMENT_SLUGS)
DEPARTMENT_DISPLAY_NAMES = COUNCIL_CONFIG.DEPARTMENT_NAMES
AGENT_ROLES = list(COUNCIL_CONFIG.AGENT_ROLES)
```

### 3. Registry Endpoint Fixed ✅

**File**: `backend/routes/registry.py`

**Issue**: Was using non-existent `COUNCIL_CONFIG.department_roles`

**Fix**: Changed to `COUNCIL_CONFIG.AGENT_ROLES`

**Before**:
```python
for role in COUNCIL_CONFIG.department_roles:  # ❌ AttributeError
    ...
```

**After**:
```python
for role in COUNCIL_CONFIG.AGENT_ROLES:  # ✅ Correct
    ...
```

### 4. Registry Endpoint Already Created ✅

**File**: `backend/routes/registry.py` (created in Task 2)

**Endpoint**: `/api/v1/registry/summary`

**Returns**:
```json
{
  "success": true,
  "departments": 8,
  "agents": 48,
  "roles_per_department": 6,
  "departments_by_role": {
    "engineering": 6,
    "product": 6,
    ...
  },
  "agents_by_role": {
    "advisor_a": 8,
    "advisor_b": 8,
    "scout_internal": 8,
    "scout_external": 8,
    "synth": 8,
    "executor": 8
  },
  "department_details": [
    {
      "slug": "engineering",
      "name": "Engineering & Technology",
      "agent_count": 6,
      "roles": {
        "advisor_a": 1,
        "advisor_b": 1,
        ...
      }
    },
    ...
  ],
  "expected": {
    "departments": 8,
    "agents": 48,
    "roles_per_department": 6
  },
  "validation": {
    "departments_valid": true,
    "agents_valid": true,
    "roles_valid": true,
    "structure_valid": true
  }
}
```

### 5. Frontend Alignment ✅

**Status**: Already completed in Task 2

**Files Updated** (in Task 2):
- `frontend/templates/daena_command_center.html`
- `frontend/templates/dashboard.html`
- `frontend/templates/enhanced_dashboard.html`
- `frontend/templates/agents.html`
- `frontend/templates/analytics.html`
- `frontend/templates/founder_panel.html`
- `frontend/templates/daena_office.html`

**Integration**:
- All frontend pages now use `/api/v1/registry/summary` as single source of truth
- Real-time sync via `realtime-sync.js` subscribes to `registry_summary` events
- Displays exact agent counts (48 total, 6 per department, 8 per role)

### 6. Tests Added ✅

**File**: `tests/test_registry_endpoint.py`

**Test Coverage**:
1. ✅ `test_registry_summary_structure` - Validates 8×6 structure
2. ✅ `test_registry_summary_department_details` - Validates department details (6 agents each)
3. ✅ `test_registry_summary_agents_by_role` - Validates agents by role (8 per role)
4. ✅ `test_registry_summary_departments_by_role` - Validates departments by role (6 per department)
5. ✅ `test_registry_summary_missing_agents` - Handles invalid structure gracefully
6. ✅ `test_registry_summary_requires_auth` - Requires authentication
7. ✅ `test_registry_summary_invalid_auth` - Rejects invalid API key

---

## 📋 Files Created/Modified

### Modified
1. `backend/routes/registry.py` - Fixed `COUNCIL_CONFIG.department_roles` → `COUNCIL_CONFIG.AGENT_ROLES`
2. `backend/scripts/seed_6x8_council.py` - Updated to use `COUNCIL_CONFIG` as single source of truth

### Created
1. `tests/test_registry_endpoint.py` - Comprehensive test suite for registry endpoint

### Already Complete (from Task 2)
1. `backend/routes/registry.py` - Registry endpoint created
2. `frontend/static/js/realtime-sync.js` - Real-time sync integration
3. All frontend templates - Updated to use registry endpoint

---

## ✅ Acceptance Criteria

- [x] **Schema alignment**
  - ✅ DB models have `department_id` and `role` fields
  - ✅ Migrations support 8×6 structure

- [x] **Seed + verify**
  - ✅ Seed script uses `COUNCIL_CONFIG` as single source of truth
  - ✅ Seed script creates exactly 8 departments × 6 agents = 48 agents
  - ✅ `/api/v1/registry/summary` endpoint exists and works

- [x] **FE alignment**
  - ✅ Dashboard reads from `/api/v1/registry/summary`
  - ✅ Real-time updates via SSE/WebSocket
  - ✅ Displays exact counts (48 agents, 8 departments, 6 roles per dept)

- [x] **Tests**
  - ✅ Test suite for registry endpoint
  - ✅ Tests validate 8×6 structure
  - ✅ Tests handle edge cases (missing agents, invalid structure)

---

## 🔧 Technical Details

### Single Source of Truth

**`backend/config/council_config.py`** defines:
- `TOTAL_DEPARTMENTS = 8`
- `AGENTS_PER_DEPARTMENT = 6`
- `TOTAL_AGENTS = 48`
- `DEPARTMENT_SLUGS` (8 departments)
- `AGENT_ROLES` (6 roles)

**All other code imports from `COUNCIL_CONFIG`**:
- `backend/scripts/seed_6x8_council.py` ✅
- `backend/routes/registry.py` ✅
- `backend/routes/health.py` ✅
- `backend/config/constants.py` (re-exports for backward compatibility) ✅

### Registry Endpoint Flow

```
1. Query Department table → Get 8 active departments
2. Query Agent table → Get 48 active agents
3. Count agents by role → 8 agents per role (one per department)
4. Count agents by department → 6 agents per department
5. Build department details → Role breakdown per department
6. Validate against COUNCIL_CONFIG → Return validation status
```

### Frontend Integration

```
1. Page loads → Fetch /api/v1/registry/summary
2. Subscribe to real-time events → realtime-sync.js
3. On registry_summary event → Update UI with exact counts
4. Display validation status → Show warning if structure invalid
```

---

## 🧪 Testing

### Manual Verification
```bash
# Run seed script
python backend/scripts/seed_6x8_council.py

# Test registry endpoint
curl -H "X-API-Key: daena_secure_key_2025" http://localhost:8000/api/v1/registry/summary

# Run tests
pytest tests/test_registry_endpoint.py -v
```

### Expected Results
- ✅ Seed creates 8 departments
- ✅ Seed creates 48 agents (6 per department)
- ✅ Registry endpoint returns correct counts
- ✅ All tests pass

---

## 📝 Commit Message

```
fix(registry): canonical 8×6 alignment + summary endpoint + UI sync

- Update seed script to use COUNCIL_CONFIG as single source of truth
- Fix registry endpoint to use COUNCIL_CONFIG.AGENT_ROLES (was department_roles)
- Add comprehensive test suite for registry endpoint
- Frontend already aligned (Task 2) - uses /api/v1/registry/summary

Files:
- Modified: backend/routes/registry.py
- Modified: backend/scripts/seed_6x8_council.py
- Created: tests/test_registry_endpoint.py
```

---

**Status**: ✅ **TASK 4 COMPLETE**  
**Next**: Task 5 - Security quick-pass

