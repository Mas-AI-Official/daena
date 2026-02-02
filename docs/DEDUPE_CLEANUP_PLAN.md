# Duplicate Cleanup Plan

**Date**: 2025-01-XX  
**Status**: Analysis Complete

---

## Analysis Results

### Dashboard Files (NOT Duplicates - Different Purposes)

1. **`dashboard.html`** ✅ KEEP
   - Main system dashboard
   - Purpose: General system overview

2. **`enhanced_dashboard.html`** ✅ KEEP
   - Enhanced analytics dashboard
   - Purpose: Advanced analytics and metrics

3. **`council_dashboard.html`** ✅ KEEP
   - Council operations dashboard
   - Purpose: Council debates, advisors, scouts, synthesizer
   - Route: `/council-dashboard` (in `backend/main.py`)

4. **`strategic_assembly_dashboard.html`** ✅ KEEP
   - Strategic assembly dashboard
   - Purpose: Cross-department strategic analysis, founder override
   - Route: `/api/v1/strategic-assembly/dashboard` (in `backend/routes/strategic_assembly.py`)

**Conclusion**: All 4 dashboards serve distinct purposes. No duplicates.

---

## Actual Duplicates Identified

### 1. Duplicate Detection Tools
- `Tools/fast_duplicate_sweep.py` ✅ KEEP (latest version)
- `Tools/duplicate_sweep.py` ⚠️ CHECK - May be obsolete
- `Tools/execute_duplicate_cleanup.py` ⚠️ CHECK - May be obsolete

**Action**: Review and consolidate if obsolete.

### 2. Backup Directory
- `Daena_Clean_Backup/` ⚠️ ARCHIVE
  - Contains old versions of files
  - Should be excluded from active codebase

**Action**: Move to archive or exclude from searches.

### 3. Voice Service Files
Multiple voice-related files exist. Need to verify:
- `backend/routes/voice.py` ✅ KEEP (main voice route)
- `backend/routes/voice_panel.py` ⚠️ CHECK - May be duplicate
- `backend/routes/voice_agents.py` ⚠️ CHECK - May be duplicate

**Action**: Review and consolidate if duplicates.

---

## Files to Review

### High Priority
1. `Tools/duplicate_sweep.py` - Check if obsolete
2. `Tools/execute_duplicate_cleanup.py` - Check if obsolete
3. `backend/routes/voice_panel.py` - Check if duplicate of voice.py
4. `backend/routes/voice_agents.py` - Check if duplicate of voice.py

### Medium Priority
1. `Daena_Clean_Backup/` - Archive or exclude
2. Multiple test files in `Daena_Clean_Backup/tests/` - Archive

---

## Cleanup Actions

### Immediate Actions
1. ✅ Verify dashboard files are not duplicates (DONE)
2. ⏳ Review duplicate detection tools
3. ⏳ Review voice route files
4. ⏳ Archive `Daena_Clean_Backup/` directory

### Future Actions
1. Create `.gitignore` entry for `Daena_Clean_Backup/`
2. Update import paths if any files reference backup directory
3. Run full duplicate sweep after cleanup

---

## Summary

**Total Dashboards**: 4 (all serve different purposes - KEEP ALL)  
**Actual Duplicates Found**: 3-4 files need review  
**Backup Directory**: 1 (should be archived)

**Status**: Most "duplicates" are actually different features. Minimal cleanup needed.

