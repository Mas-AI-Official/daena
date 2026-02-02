# Folder Structure Standardization Plan
**Date:** 2025-12-07  
**Status:** Planning Phase

---

## Current Structure Analysis

### Daena (Internal System)
```
Daena/
├── backend/                    # Daena internal backend
│   ├── routes/                 # ALL routes (mixed internal + public)
│   │   ├── daena.py           # ✅ Internal Daena routes
│   │   ├── council_governance.py  # ✅ Internal Council routes
│   │   ├── departments.py     # ✅ Internal Department routes
│   │   ├── agents.py          # ✅ Internal Agent routes
│   │   ├── vibe.py            # ⚠️ PUBLIC VibeAgent routes (should be separated)
│   │   ├── user_mesh.py       # ⚠️ PUBLIC VibeAgent routes (should be separated)
│   │   ├── vibe_agents.py     # ⚠️ PUBLIC VibeAgent routes (should be separated)
│   │   ├── vibe_agent_events.py  # ⚠️ PUBLIC VibeAgent routes (should be separated)
│   │   ├── knowledge_exchange.py  # ✅ Shared Knowledge Exchange Layer
│   │   └── ... (80+ other route files)
│   ├── services/              # Internal services
│   ├── database.py            # Database models (mixed internal + public)
│   └── main.py                # Main FastAPI app
├── frontend/                   # Internal Daena UI
├── Core/                       # Core AI system
├── Agents/                     # Agent definitions
└── ... (many other directories)
```

### VibeAgent (Public Platform)
```
VibeAgent/
├── app/                        # Next.js app (public)
├── components/                 # React components (public)
├── lib/                        # Library code (public)
│   ├── api.ts                 # API client
│   ├── daenaBrainClient.ts    # Daena brain client
│   └── ...
└── ... (other public files)
```

---

## Problem Statement

### Issues Identified:

1. **Mixed Routes in Daena Backend:**
   - `routes/vibe.py` - Public VibeAgent routes are in Daena backend
   - `routes/user_mesh.py` - Public VibeAgent routes are in Daena backend
   - `routes/vibe_agents.py` - Public VibeAgent routes are in Daena backend
   - `routes/vibe_agent_events.py` - Public VibeAgent routes are in Daena backend
   
   **These should be clearly separated or moved to a shared location.**

2. **Database Models:**
   - `database.py` contains both `Agent` (internal) and `PublicAgent` (public)
   - This is actually correct per spec (namespace separation), but could be clearer

3. **No Clear Physical Separation:**
   - While namespace separation exists (`daena_internal_*` vs `vibeagent_public_*`), there's no clear folder structure showing the separation

---

## Target Structure Options

### Option A: Keep Routes in Daena, Organize by Namespace (RECOMMENDED)
**Pros:**
- Minimal disruption
- Routes already work
- Namespace separation already enforced
- Knowledge Exchange Layer can stay in Daena

**Cons:**
- Public routes still in Daena folder structure
- Less clear physical separation

**Structure:**
```
Daena/
├── backend/
│   ├── routes/
│   │   ├── internal/              # NEW: Internal Daena routes
│   │   │   ├── daena.py
│   │   │   ├── council_governance.py
│   │   │   ├── departments.py
│   │   │   └── agents.py
│   │   ├── public/                # NEW: Public VibeAgent routes
│   │   │   ├── vibe.py
│   │   │   ├── user_mesh.py
│   │   │   ├── vibe_agents.py
│   │   │   └── vibe_agent_events.py
│   │   ├── shared/                # NEW: Shared routes
│   │   │   ├── knowledge_exchange.py
│   │   │   └── health.py
│   │   └── ... (other routes stay as-is for now)
│   └── ...
```

### Option B: Create Separate Backend Structure
**Pros:**
- Clear physical separation
- Easier to understand

**Cons:**
- Major refactoring required
- More complex deployment
- Knowledge Exchange Layer needs to be in both or shared

**Structure:**
```
Daena/
├── daena-internal/               # NEW: Internal Daena
│   ├── backend/
│   │   ├── routes/
│   │   │   ├── daena.py
│   │   │   ├── council_governance.py
│   │   │   └── ...
│   └── frontend/
└── vibeagent-public/             # NEW: Public VibeAgent backend
    ├── backend/
    │   ├── routes/
    │   │   ├── vibe.py
    │   │   ├── user_mesh.py
    │   │   └── ...
    └── frontend/                  # This is already VibeAgent/

Shared/
└── knowledge-exchange/            # Shared Knowledge Exchange Layer
```

### Option C: Hybrid Approach (BEST FOR CURRENT STATE)
**Pros:**
- Maintains current working structure
- Adds clear organization
- Minimal breaking changes
- Can evolve to Option B later if needed

**Cons:**
- Still some mixing in Daena folder

**Structure:**
```
Daena/
├── backend/
│   ├── routes/
│   │   ├── internal/              # NEW: Internal Daena routes
│   │   │   ├── __init__.py
│   │   │   ├── daena.py
│   │   │   ├── council_governance.py
│   │   │   ├── departments.py
│   │   │   ├── agents.py
│   │   │   └── ... (other internal routes)
│   │   ├── public/                # NEW: Public VibeAgent routes
│   │   │   ├── __init__.py
│   │   │   ├── vibe.py
│   │   │   ├── user_mesh.py
│   │   │   ├── vibe_agents.py
│   │   │   └── vibe_agent_events.py
│   │   ├── shared/                # NEW: Shared routes
│   │   │   ├── __init__.py
│   │   │   ├── knowledge_exchange.py
│   │   │   ├── health.py
│   │   │   └── sunflower_api.py
│   │   └── ... (legacy routes - to be organized later)
│   └── ...
└── ...

VibeAgent/                        # Already separate, no changes needed
├── app/
├── components/
└── lib/
```

---

## Recommended Approach: Option C (Hybrid)

### Implementation Steps:

1. **Create New Folder Structure:**
   ```bash
   Daena/backend/routes/
   ├── internal/     # Internal Daena routes
   ├── public/      # Public VibeAgent routes
   └── shared/      # Shared routes (Knowledge Exchange, Health, etc.)
   ```

2. **Move Routes to Appropriate Folders:**
   - Move internal routes to `internal/`
   - Move public routes to `public/`
   - Move shared routes to `shared/`

3. **Update Imports:**
   - Update `main.py` to import from new locations
   - Update any route files that import from moved routes

4. **Update Documentation:**
   - Document the new structure
   - Update README files

5. **Test:**
   - Verify all routes still work
   - Test internal Daena functionality
   - Test public VibeAgent functionality
   - Test Knowledge Exchange Layer

---

## Files to Move

### Internal Routes → `routes/internal/`
- `daena.py`
- `daena_decisions.py`
- `daena_vp.py`
- `council_governance.py`
- `council_rounds.py`
- `council_approval.py`
- `council_status.py`
- `council_v2.py`
- `council.py`
- `departments.py`
- `agents.py`
- `enterprise_dna.py`
- `founder_panel.py`
- `strategic_room.py`
- `strategic_assembly.py`
- `strategic_meetings.py`
- `conference_room.py`
- `meetings.py`
- `hiring.py`
- `projects.py`
- `tasks.py`
- `workflows.py` (if internal)
- ... (other internal-only routes)

### Public Routes → `routes/public/`
- `vibe.py`
- `user_mesh.py`
- `vibe_agents.py`
- `vibe_agent_events.py`

### Shared Routes → `routes/shared/`
- `knowledge_exchange.py`
- `health.py`
- `sunflower_api.py`
- `sunflower.py` (if shared)
- `honeycomb.py` (if shared)

---

## Migration Checklist

- [ ] Create `routes/internal/` folder
- [ ] Create `routes/public/` folder
- [ ] Create `routes/shared/` folder
- [ ] Create `__init__.py` files in each folder
- [ ] Move internal routes
- [ ] Move public routes
- [ ] Move shared routes
- [ ] Update imports in `main.py`
- [ ] Update imports in moved route files
- [ ] Test internal routes
- [ ] Test public routes
- [ ] Test shared routes
- [ ] Update documentation
- [ ] Update README files

---

## Notes

- **Namespace Separation:** Already enforced via `agent_namespace.py` - this is separate from folder structure
- **Database Models:** `Agent` (internal) and `PublicAgent` (public) are correctly separated in `database.py`
- **Knowledge Exchange Layer:** Must remain accessible to both internal and public routes
- **Backward Compatibility:** Keep old route files as symlinks or redirects during transition (optional)

---

## Timeline

- **Phase 1:** Create folder structure (1 hour)
- **Phase 2:** Move routes (2-3 hours)
- **Phase 3:** Update imports (1-2 hours)
- **Phase 4:** Testing (2-3 hours)
- **Phase 5:** Documentation (1 hour)

**Total Estimated Time:** 7-10 hours

---

**Last Updated:** 2025-12-07






