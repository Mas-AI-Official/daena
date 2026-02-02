# MAS-AI Ecosystem Refactor & Cleanup Plan

**Date:** 2025-12-07  
**Status:** IN PROGRESS  
**Priority:** CRITICAL

---

## EXECUTIVE SUMMARY

This document tracks the systematic refactoring and cleanup of the MAS-AI ecosystem (Daena + VibeAgent) to enforce proper architecture separation, remove duplicates, and align with the official system design specification.

---

## CRITICAL ISSUES IDENTIFIED

### 1. Agent Count Inconsistency ⚠️ **FIXED**

**Issue:** Documentation conflicts on agents per department:
- **Spec says:** 6 agents per department (hexagonal)
- **Some docs say:** 8 agents per department
- **Code says:** 6 agents per department (council_config.py)

**Status:** ✅ Spec is correct - 6 agents per department
**Action:** Update all documentation to reflect 6 agents per department

**Files to Update:**
- `ARCHITECTURE_UPDATE_SUMMARY.md` - Says 8, should say 6
- `COMPLETE_IMPLEMENTATION_STATUS.md` - Says 8, should say 6
- `SYSTEM_TESTING_GUIDE.md` - Says 8, should say 6
- `ARCHITECTURE_SEEDING_GUIDE.md` - Says 8, should say 6
- Any other docs mentioning 8 agents per department

---

### 2. API Client Duplication ⚠️ **IN REVIEW**

**Issue:** Multiple API clients in VibeAgent:
- `lib/api.ts` - Axios-based client
- `lib/apiProxy.ts` - SSO proxy client
- `lib/daenaBrainClient.ts` - Daena brain client

**Analysis:**
- `api.ts` - General API client for VibeAgent endpoints
- `apiProxy.ts` - SSO token proxy (different purpose)
- `daenaBrainClient.ts` - Specific client for Daena brain integration

**Status:** ⚠️ Need to verify they don't duplicate functionality
**Action:** Review and consolidate if duplicates exist

---

### 3. Namespace Separation ⚠️ **TO IMPLEMENT**

**Issue:** Need to enforce clear namespace separation:
- `daena_internal_*` - Daena internal agents
- `vibeagent_public_*` - VibeAgent user agents
- `council_governance_*` - Council governance agents

**Status:** ⚠️ Partially implemented, needs enforcement
**Action:** 
- Review agent registration code
- Add namespace validation
- Ensure no cross-contamination

---

### 4. Knowledge Exchange Layer ✅ **IMPLEMENTED**

**Status:** ✅ Already implemented in:
- `backend/services/knowledge_exchange.py`
- `backend/routes/knowledge_exchange.py`
- `lib/daenaBrainClient.ts` (VibeAgent side)

**Action:** Verify it's properly separated and not sharing raw data

---

### 5. Duplicate Documentation Files ⚠️ **TO CLEAN**

**Issue:** Many duplicate or conflicting documentation files:
- Multiple status/summary files
- Old architecture docs vs new
- Archive vs active docs

**Action:** 
- Consolidate status files
- Move old docs to archive
- Create single source of truth

---

### 6. Dead Code & Backup Files ⚠️ **TO CLEAN**

**Found:**
- `Daena_Clean_Backup/` - Backup directory
- `frontend_backup/` - Backup directory
- Various `*_old`, `*_backup`, `*_copy` files

**Action:** 
- Move to `/legacy` or `/archive`
- Remove from active codebase
- Update .gitignore

---

### 7. Per-User Ecosystem Model ⚠️ **TO IMPLEMENT**

**Status:** ⚠️ Partially implemented in `daenaBrainClient.ts`
**Missing:**
- Isolated vs Shared mode selection
- Per-account ecosystem graph
- Dashboard controls for ecosystem management

**Action:** Implement according to PART 7 of spec

---

## CLEANUP PRIORITIES

### Phase 1: Critical Fixes (IMMEDIATE)
1. ✅ Fix agent count documentation (6 agents per department)
2. ⚠️ Verify API client separation
3. ⚠️ Enforce namespace separation
4. ⚠️ Verify Knowledge Exchange Layer isolation

### Phase 2: Structure Cleanup (HIGH PRIORITY)
1. ⚠️ Consolidate duplicate documentation
2. ⚠️ Remove/move backup directories
3. ⚠️ Clean up dead code
4. ⚠️ Standardize folder structure

### Phase 3: Feature Implementation (MEDIUM PRIORITY)
1. ⚠️ Implement per-user ecosystem model
2. ⚠️ Add dashboard controls
3. ⚠️ Implement Vibe Main Brain
4. ⚠️ Add Daena escalation flow

### Phase 4: Final Polish (LOW PRIORITY)
1. ⚠️ Update all documentation
2. ⚠️ Create architecture diagrams
3. ⚠️ Write migration guide
4. ⚠️ Update README files

---

## FOLDER STRUCTURE TARGET

```
Daena/
├── backend/                    # Daena internal backend
│   ├── routes/
│   │   ├── daena/             # Internal Daena routes
│   │   ├── council/           # Council governance routes
│   │   ├── departments/       # Department routes
│   │   └── knowledge_exchange/ # Knowledge Exchange Layer
│   ├── services/
│   │   └── knowledge_exchange.py
│   └── config/
│       └── council_config.py  # 6 agents per department
├── frontend/
│   └── apps/
│       ├── daena/             # Internal Daena UI
│       └── vibeagent/          # Public VibeAgent platform
└── docs/
    └── 6 TOP-LEVEL SYSTEM DESIGN SPEC AND REFACTOR MISSION/
        ├── MAS-AI_ECOSYSTEM_ARCHITECTURE_SPEC.md
        └── REFACTOR_CLEANUP_PLAN.md

VibeAgent/
├── app/                       # Next.js app
├── components/
├── lib/
│   ├── api.ts                 # General API client
│   ├── apiProxy.ts            # SSO proxy
│   └── daenaBrainClient.ts    # Daena brain client
└── store/
```

---

## PROGRESS TRACKING

- [x] Create spec document
- [x] Create cleanup plan
- [ ] Fix agent count documentation
- [ ] Review API client separation
- [ ] Enforce namespace separation
- [ ] Consolidate duplicate docs
- [ ] Remove backup directories
- [ ] Implement per-user ecosystem
- [ ] Final verification

---

**Last Updated:** 2025-01-XX

