# Unified Task List - All Remaining Tasks
**Date:** 2025-01-23
**Merged from:** Previous tasks (17/29) + New requirements

## ✅ COMPLETED (From Previous Work)

1. ✅ Session Creation Enforcement - All endpoints now guarantee session_id
2. ✅ Department Chat Agent Session - Uses DB-backed service
3. ✅ Department Chat History Visibility - Updated get_all_sessions to use DB service
4. ✅ Frontend API Client - Updated to use unified chat-history endpoint

## 🔄 CRITICAL FIXES (Must Complete)

### A. Session Lifecycle (Partially Done)
- ✅ Fix "No session_id" - All endpoints now return session_id
- ⚠️ **TODO:** Ensure frontend handles session creation errors gracefully
- ⚠️ **TODO:** Add session validation middleware

### B. Department Chat History (Partially Done)
- ✅ Department chats stored in DB with scope_type="department"
- ✅ Department chats queryable via unified endpoint
- ⚠️ **TODO:** Verify department chats appear in Daena office view
- ⚠️ **TODO:** Ensure department chat history shows in department office page

### C. Data Persistence (Partially Done)
- ✅ Chat sessions + messages in SQLite
- ⚠️ **TODO:** Add activity feed persistence (EventLog table exists but may not be used)
- ⚠️ **TODO:** Add reset tooling (founder-only) to wipe DB safely

### D. Real-time Sync (Not Started)
- ❌ **TODO:** Implement unified event bus that persists to DB
- ❌ **TODO:** WebSocket broadcasts for:
  - agent activity events
  - new chat messages (department + executive)
  - council session/debate updates
- ❌ **TODO:** Frontend WebSocket client with fallback to polling

### E. Voice System (Not Started)
- ❌ **TODO:** Fix START_DAENA.bat to never close silently
- ❌ **TODO:** Fix START_AUDIO_ENV.bat to activate audio env reliably
- ❌ **TODO:** Ensure voice toggle works end-to-end
- ❌ **TODO:** Verify daena_voice.wav cloning works
- ❌ **TODO:** Add /api/v1/voice/status endpoint if missing
- ❌ **TODO:** Add /api/v1/voice/speak endpoint if missing
- ❌ **TODO:** Ensure agents have unique voice IDs

### F. Council System (Partially Done)
- ⚠️ **TODO:** Fix council seeding/listing (currently returns empty)
- ❌ **TODO:** Add POST /api/v1/council/create endpoint
- ❌ **TODO:** Add POST /api/v1/council/{council_id}/debate/start
- ❌ **TODO:** Add POST /api/v1/council/{council_id}/debate/{session_id}/message
- ❌ **TODO:** Add GET /api/v1/council/{council_id}/debate/{session_id}
- ❌ **TODO:** Add POST /api/v1/council/{council_id}/debate/{session_id}/synthesize
- ❌ **TODO:** Store debate transcript in chat storage (scope_type="council")
- ❌ **TODO:** Store synthesis into memory/knowledge store

### G. Intelligence Routing Layer (New Requirement)
- ❌ **TODO:** Add intelligence dimension scoring (IQ/EQ/AQ/Execution)
- ❌ **TODO:** Route queries to appropriate agent/model based on intelligence needs
- ❌ **TODO:** Merge outputs into single response
- ❌ **TODO:** Store intelligence scores in audit log
- ❌ **TODO:** Add internal report: IQ/EQ/AQ/Execution score + which agent/model contributed

## 📋 TESTING & DOCUMENTATION

### H. Smoke Tests & Launcher
- ❌ **TODO:** Update START_DAENA.bat so it never closes silently
- ❌ **TODO:** Add health check + ollama check + voice check to launcher
- ❌ **TODO:** Ensure smoke tests pass 12/12:
  - ✅ ollama reachable OR UI shows "BRAIN OFFLINE" but chat still works
  - ✅ creating session returns session_id
  - ✅ department chat sends message and persists
  - ✅ restarting backend keeps chat history
  - ✅ websocket live updates work (or polling fallback)
  - ⚠️ Council system works end-to-end
  - ⚠️ Voice system works end-to-end

### I. Documentation
- ❌ **TODO:** Create CHANGES.md listing every modified file + why
- ❌ **TODO:** Create RUNBOOK.md with exact steps to start: ollama, backend, voice env
- ❌ **TODO:** Create VERIFY.md checklist with curl commands for each major endpoint

## PRIORITY ORDER

1. **IMMEDIATE:** Fix council seeding/listing (blocking tests)
2. **IMMEDIATE:** Implement unified event bus (required for real-time)
3. **HIGH:** Fix voice system activation
4. **HIGH:** Complete council system endpoints
5. **MEDIUM:** Add intelligence routing layer
6. **MEDIUM:** Complete documentation


