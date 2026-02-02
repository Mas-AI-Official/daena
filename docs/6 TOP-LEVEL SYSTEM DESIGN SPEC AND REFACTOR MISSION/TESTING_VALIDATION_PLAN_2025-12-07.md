# Testing & Validation Plan
**Date:** 2025-12-07  
**Status:** Ready for Execution

---

## Overview

This document outlines the testing and validation plan for the refactored MAS-AI Ecosystem, ensuring all changes work correctly and the system is production-ready.

---

## Testing Categories

### 1. Route Migration Testing

**Objective:** Verify all migrated routes work correctly after folder structure changes.

**Tests:**
- [ ] **Internal Routes:**
  - [ ] `GET /api/v1/daena/status` - Daena status endpoint
  - [ ] `GET /api/v1/departments` - Department listing
  - [ ] `GET /api/v1/agents` - Agent management
  - [ ] `GET /api/v1/council/governance/*` - Council endpoints

- [ ] **Public Routes:**
  - [ ] `POST /api/v1/vibe/compile` - Vibe compilation
  - [ ] `POST /api/v1/vibe/deploy` - Agent deployment
  - [ ] `POST /api/v1/users/mesh` - User mesh generation
  - [ ] `GET /api/v1/vibe/agents/{id}/status` - Agent status
  - [ ] `POST /api/v1/vibe/agents/{id}/pause` - Pause agent
  - [ ] `POST /api/v1/vibe/agents/{id}/resume` - Resume agent
  - [ ] `DELETE /api/v1/vibe/agents/{id}` - Delete agent
  - [ ] `GET /api/v1/vibe/agents/{id}/events` - SSE events

- [ ] **Shared Routes:**
  - [ ] `GET /api/v1/health` - Health check
  - [ ] `POST /api/v1/knowledge-exchange/from-vibeagent` - Knowledge Exchange
  - [ ] `GET /api/v1/knowledge-exchange/methodologies` - Get methodologies
  - [ ] `POST /api/v1/sunflower/coordinates` - Sunflower coordinates

**Method:**
- Use Postman collection or curl commands
- Verify all endpoints return expected responses
- Check for import errors in logs

---

### 2. API Alignment Testing

**Objective:** Verify frontend API calls match backend endpoints.

**Tests:**
- [ ] Test all `daenaBrainClient.ts` methods
- [ ] Test all `api.ts` methods
- [ ] Verify request/response formats match
- [ ] Test error handling

**Method:**
- Run frontend in development mode
- Test each API call
- Verify responses match expected types

---

### 3. Ecosystem Mode Testing

**Objective:** Verify per-user ecosystem mode functionality.

**Tests:**
- [ ] **Isolated Mode:**
  - [ ] Create agent with `ecosystem_mode: "isolated"`
  - [ ] Verify agent has no neighbors
  - [ ] Verify agent operates independently

- [ ] **Shared Mode:**
  - [ ] Create agent with `ecosystem_mode: "shared"`
  - [ ] Verify agent has neighbors (if other shared agents exist)
  - [ ] Verify agent can communicate with other shared agents

- [ ] **Mixed Mode:**
  - [ ] Create multiple agents with mixed modes
  - [ ] Verify isolated agents don't connect
  - [ ] Verify shared agents form connections

**Method:**
- Use VibeAgent frontend to deploy agents
- Check database records
- Verify mesh generation

---

### 4. Namespace Separation Testing

**Objective:** Verify namespace separation is enforced.

**Tests:**
- [ ] **Internal Agents:**
  - [ ] Verify internal agents use `daena_internal_*` prefix
  - [ ] Verify internal agents cannot be accessed via public endpoints

- [ ] **Public Agents:**
  - [ ] Verify public agents use `vibeagent_public_*` prefix
  - [ ] Verify public agents cannot access internal resources

- [ ] **Council Agents:**
  - [ ] Verify council agents use `council_governance_*` prefix
  - [ ] Verify council agents are separate from internal/public

**Method:**
- Check agent IDs in database
- Test endpoint access with different namespaces
- Verify namespace validation works

---

### 5. Knowledge Exchange Layer Testing

**Objective:** Verify Knowledge Exchange Layer works correctly and doesn't leak data.

**Tests:**
- [ ] **Data Sanitization:**
  - [ ] Send test data with PII
  - [ ] Verify PII is stripped before processing
  - [ ] Verify only patterns/metadata are stored

- [ ] **Pattern Exchange:**
  - [ ] Send workflow pattern from VibeAgent
  - [ ] Verify pattern is received by Daena
  - [ ] Verify pattern is anonymized

- [ ] **Methodology Retrieval:**
  - [ ] Request methodologies from Daena
  - [ ] Verify methodologies are returned
  - [ ] Verify no raw data is included

**Method:**
- Use Knowledge Exchange endpoints
- Check logs for data sanitization
- Verify database records

---

### 6. Frontend Integration Testing

**Objective:** Verify frontend can connect to backend and all features work.

**Tests:**
- [ ] **Connection:**
  - [ ] Frontend can connect to backend
  - [ ] API calls succeed
  - [ ] Error handling works

- [ ] **Features:**
  - [ ] Vibe compilation works
  - [ ] Agent deployment works
  - [ ] Agent lifecycle management works
  - [ ] User mesh visualization works
  - [ ] SSE events stream correctly

**Method:**
- Run full stack (backend + frontend)
- Test all user flows
- Check for console errors

---

### 7. Database Migration Testing

**Objective:** Verify database migration for `ecosystem_mode` works.

**Tests:**
- [ ] Run migration script
- [ ] Verify `ecosystem_mode` column exists
- [ ] Verify existing records have default value
- [ ] Verify new records can set `ecosystem_mode`

**Method:**
- Run `add_ecosystem_mode_to_public_agents.py`
- Check database schema
- Test insert/update operations

---

## Test Execution Plan

### Phase 1: Quick Smoke Tests (30 minutes)
1. Start backend server
2. Test health endpoint
3. Test a few critical endpoints
4. Check for import errors

### Phase 2: Route Testing (1-2 hours)
1. Test all migrated routes
2. Verify imports work
3. Check for broken references

### Phase 3: Integration Testing (2-3 hours)
1. Test full stack
2. Test user flows
3. Test ecosystem modes
4. Test namespace separation

### Phase 4: Knowledge Exchange Testing (1 hour)
1. Test data sanitization
2. Test pattern exchange
3. Verify no data leakage

---

## Success Criteria

- ✅ All routes respond correctly
- ✅ No import errors
- ✅ Frontend can connect to backend
- ✅ Ecosystem modes work correctly
- ✅ Namespace separation enforced
- ✅ Knowledge Exchange Layer works
- ✅ No data leakage
- ✅ Database migration successful

---

## Test Results Template

```markdown
## Test Results - [Date]

### Route Migration
- [ ] Internal routes: PASS/FAIL
- [ ] Public routes: PASS/FAIL
- [ ] Shared routes: PASS/FAIL

### API Alignment
- [ ] Frontend calls: PASS/FAIL
- [ ] Response formats: PASS/FAIL

### Ecosystem Mode
- [ ] Isolated mode: PASS/FAIL
- [ ] Shared mode: PASS/FAIL
- [ ] Mixed mode: PASS/FAIL

### Namespace Separation
- [ ] Internal agents: PASS/FAIL
- [ ] Public agents: PASS/FAIL
- [ ] Council agents: PASS/FAIL

### Knowledge Exchange
- [ ] Data sanitization: PASS/FAIL
- [ ] Pattern exchange: PASS/FAIL

### Frontend Integration
- [ ] Connection: PASS/FAIL
- [ ] Features: PASS/FAIL

### Database Migration
- [ ] Migration script: PASS/FAIL
- [ ] Schema update: PASS/FAIL
```

---

**Last Updated:** 2025-12-07






