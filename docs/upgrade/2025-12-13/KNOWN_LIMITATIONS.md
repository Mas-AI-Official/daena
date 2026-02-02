# Known Limitations

**Date**: 2025-12-13  
**Purpose**: Document intentional limitations and future improvements

---

## Current Limitations

### 1. Brain Store Storage

**Current**: JSON files in `data/brain_store/`
- `governance_queue.json` - Pending proposals
- `committed_experiences.json` - Committed experiences

**Limitation**: Not database-backed, not suitable for production scale

**Future**: Migrate to database (SQLite for local, PostgreSQL for production)

---

### 2. Governance Queue Persistence

**Current**: In-memory/file-based queue

**Limitation**: Queue is lost on server restart (unless saved to file)

**Future**: Use database for queue persistence

---

### 3. Authentication

**Current**: `DISABLE_AUTH=1` by default (dev mode)

**Limitation**: No authentication in dev mode

**Future**: 
- Production mode: `DISABLE_AUTH=0` requires JWT tokens
- Add proper auth middleware for production

---

### 4. Rate Limiting

**Current**: Basic rate limiting on some endpoints

**Limitation**: No rate limiting on brain endpoints

**Future**: Add configurable rate limiting to brain endpoints

---

### 5. Brain Query Caching

**Current**: No caching of brain queries

**Limitation**: Every query hits the LLM service

**Future**: Add query result caching (Redis or in-memory)

---

### 6. Governance State Machine

**Current**: Basic state transitions (PROPOSED → ... → COMMITTED)

**Limitation**: No automatic state progression (requires manual transitions)

**Future**: 
- Add automatic scouting (Daena reviews proposals)
- Add council voting integration
- Add automatic synthesis step

---

### 7. Brain UI

**Current**: Basic Brain panel showing status and queue

**Limitation**: 
- No UI for proposing experiences (must use API)
- No UI for council voting
- No detailed audit trail view

**Future**: 
- Add "Propose Experience" button in agent chat
- Add council voting UI
- Add detailed audit trail viewer

---

### 8. Error Handling

**Current**: Basic error handling

**Limitation**: Some errors may not be user-friendly

**Future**: Improve error messages and recovery

---

## Intentional Design Decisions

### 1. One Shared Brain

**Decision**: All agents share one brain runtime

**Rationale**: 
- Efficiency (one model instance)
- Consistency (same reasoning)
- Simplicity (no multiple model management)

**Not a limitation**: This is the intended design

---

### 2. Governance-Gated Writes

**Decision**: Agents cannot write directly to brain

**Rationale**: 
- Prevents knowledge pollution
- Ensures quality through governance
- Maintains audit trail

**Not a limitation**: This is the intended security model

---

### 3. Local-First LLM

**Decision**: Ollama-first, cloud optional

**Rationale**: 
- Works offline
- No API costs
- Privacy

**Not a limitation**: This is the intended architecture

---

## Future Improvements (Not Limitations)

### Phase 2 Features
- [ ] Embedded browser for Explorer Mode
- [ ] Full automation tools (behind flags)
- [ ] Production auth hardening
- [ ] Database persistence for brain store
- [ ] Advanced governance workflows
- [ ] Council voting UI
- [ ] Detailed audit trail viewer

---

## Workarounds

### If Brain Store Fails
- Check `data/brain_store/` directory exists
- Verify write permissions
- Check disk space

### If Governance Queue Empty
- This is normal if no proposals have been made
- Test by calling `POST /api/v1/brain/propose_experience`

### If Brain UI Doesn't Load
- Check browser console for errors
- Verify `/api/v1/brain/status` returns 200
- Check network tab for failed requests

---

**Status**: ✅ **LIMITATIONS DOCUMENTED**

**Note**: These are intentional limitations for the current phase. Future improvements are planned but not required for go-live.
