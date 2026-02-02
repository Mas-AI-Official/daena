# Duplicate & Dead Code Report

**Date**: 2025-12-09  
**Status**: In Progress

## Duplicate Route Files Identified

### Agent Builder Routes (6 files - likely duplicates)
- `backend/routes/agent_builder.py` - **KEEP** (canonical)
- `backend/routes/agent_builder_api.py` - **MERGE/REMOVE**
- `backend/routes/agent_builder_api_simple.py` - **MERGE/REMOVE**
- `backend/routes/agent_builder_complete.py` - **MERGE/REMOVE**
- `backend/routes/agent_builder_platform.py` - **MERGE/REMOVE**
- `backend/routes/agent_builder_simple.py` - **MERGE/REMOVE**

**Action**: Consolidate into single `agent_builder.py` or move extras to `/legacy/agent_builders/`

### Council Routes (6 files - need consolidation)
- `backend/routes/internal/council_governance.py` - **KEEP** (canonical, in internal/)
- `backend/routes/council_approval.py` - **CHECK** (may be different purpose)
- `backend/routes/council_rounds.py` - **CHECK** (may be different purpose)
- `backend/routes/council_status.py` - **CHECK** (may be different purpose)
- `backend/routes/council_v2.py` - **MERGE/REMOVE** (v2 suggests old version)
- `backend/routes/council_vibe.py` - **CHECK** (VibeAgent-specific?)
- `backend/routes/council.py` - **MERGE/REMOVE** (likely old version)

**Action**: Review each, keep unique functionality, merge duplicates

### Strategic Routes (3 files - may be duplicates)
- `backend/routes/strategic_assembly.py` - **CHECK**
- `backend/routes/strategic_meetings.py` - **CHECK**
- `backend/routes/strategic_room.py` - **CHECK**

**Action**: Review if these serve different purposes or can be merged

### Health Routes (2 files)
- `backend/routes/shared/health.py` - **KEEP** (canonical, in shared/)
- `backend/routes/health_routing.py` - **CHECK** (may be different purpose)

**Action**: Review and merge if duplicate

## Files to Move to Legacy

1. `demos/01_full_system_demo_backup.html` → `legacy/demos/`
2. Old agent_builder variants → `legacy/agent_builders/`
3. Old council variants → `legacy/council_routes/`

## Next Steps

1. Review each duplicate file to determine if unique functionality exists
2. Merge unique functionality into canonical files
3. Move confirmed duplicates to `/legacy/` with README explaining why
4. Update imports in `main.py` to remove references to moved files
5. Test that no routes are broken

