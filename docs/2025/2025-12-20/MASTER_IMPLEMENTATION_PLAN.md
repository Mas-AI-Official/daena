# Master Implementation Plan - Complete System Rebuild

## Executive Summary

This document outlines the complete implementation plan to eliminate all mock data, implement true persistence, add real-time sync, and fix all broken UI controls.

## Current State Analysis

### In-Memory Stores Identified:
1. `sunflower_registry` - Departments/Agents (populated from DB but cached)
2. `active_sessions` - Chat sessions (lost on restart)
3. `_activity_store` - Agent activity (in-memory only)
4. `founder_overrides` - Founder panel settings (in-memory)
5. `audit_logs` - Audit trail (in-memory)
6. `voice_state` - Voice system state (in-memory)

### Database Schema Status:
✅ **Existing Tables**: Department, Agent, Task, ChatSession, ChatMessage, EventLog
✅ **Enhanced**: Added hidden, metadata_json, voice_id, last_seen fields
✅ **New Tables Created**: ChatCategory, CouncilCategory, CouncilMember, Connection, VoiceState

## Implementation Phases

### Phase 1: Backend State Audit ✅
- [x] Identified all in-memory stores
- [x] Documented mock data endpoints
- [x] Enhanced database schema

### Phase 2: SQLite Persistence (IN PROGRESS)
- [x] Enhanced database.py with missing tables
- [ ] Create migration script
- [ ] Update all endpoints to use DB
- [ ] Seed bootstrap data (8 depts, 6 agents each)

### Phase 3: WebSocket Event Bus
- [ ] Enhance websocket_manager with event publishing
- [ ] Add EventLog writes on all state changes
- [ ] Implement "since_event_id" backfill

### Phase 4: Frontend Remove Mock + Real API
- [ ] Remove all local JS mock arrays
- [ ] Wire all widgets to real API endpoints
- [ ] Add WebSocket client for live updates

### Phase 5: Department Chat History Dual-View
- [ ] Ensure ChatMessage stores scope_type/scope_id
- [ ] Department pages filter by scope
- [ ] Daena page shows same messages by category

### Phase 6: Brain + Model Management
- [ ] Real Ollama model scanning
- [ ] Brain enabled/disabled routing switch
- [ ] Per-agent model assignment
- [ ] Usage counters

### Phase 7: Voice Pipeline
- [ ] Fix audio env launcher
- [ ] Daena voice cloning (daena_voice.wav)
- [ ] Per-agent voice mapping

### Phase 8: QA + Smoke Tests
- [ ] Comprehensive smoke test script
- [ ] Verify persistence after restart
- [ ] Verify WebSocket events
- [ ] Verify chat history sync

## Critical Fixes Required

### A) Chat History & Session Sync
**Problem**: Departments show no chat history. Need dual-view.

**Solution**:
1. All messages stored in ChatMessage with scope_type/scope_id
2. Department office: Filter by `scope_type='department' AND scope_id='HR'`
3. Daena office: Show same messages organized by category
4. Single source of truth: ChatMessage table

### B) Brain Connection
**Problem**: Mock responses, missing session_id, inconsistent status

**Solution**:
1. Always return session_id (auto-create if missing)
2. If Ollama offline: Return deterministic "humanized" reply
3. If Ollama online: Route through real brain
4. Brain status reflects actual Ollama reachability

### C) Voice System
**Problem**: Audio env not activating, TTS not working

**Solution**:
1. Fix START_AUDIO_ENV.bat
2. Ensure daena_voice.wav is used
3. Per-agent voice_id mapping in DB
4. Stable fallback if cloning fails

### D) UI Controls
**Problem**: Buttons do nothing, no backend implementation

**Solution**:
1. Implement all missing endpoints
2. Brain on/off = routing switch (not true stop)
3. Model scanning = real Ollama /api/tags
4. Usage counters = approximate from ChatMessage tokens

### E) Sidebar Toggle
**Problem**: Multiple toggles, layout issues

**Solution**:
1. Keep single toggle in base.html
2. Expand sidebar width to show names
3. Fix overflow and layout

### F) Dashboard
**Problem**: Wrong layout, mock data, spinning animation

**Solution**:
1. Remove spinning animation
2. Load real data from DB
3. Active tasks by department
4. Recent events from EventLog
5. Brain status + model
6. Today's operations summary

### G) Agent Count Mismatch
**Problem**: Shows 12 or 96 instead of 6 per department

**Solution**:
1. Ensure seed creates exactly 6 agents per dept
2. Fix duplicate generation
3. Filter by department_id in queries

### H) Hidden Departments
**Problem**: Not appearing in Founder page

**Solution**:
1. Add hidden field to Department
2. Founder page shows all (including hidden)
3. Enable/disable functionality

### I) Councils
**Problem**: Not real, not editable

**Solution**:
1. Store in CouncilCategory/CouncilMember tables
2. CRUD endpoints for councils
3. UI for rename, settings, enable/disable

## Files to Modify

### Backend:
- `backend/database.py` - ✅ Enhanced
- `backend/routes/daena.py` - Replace active_sessions
- `backend/routes/departments.py` - Use DB, fix agent counts
- `backend/routes/agents.py` - Use DB
- `backend/routes/chat_history.py` - Use DB ChatSession/ChatMessage
- `backend/routes/founder_panel.py` - Use DB
- `backend/routes/brain.py` - Real Ollama scanning, routing switch
- `backend/routes/council.py` - Real CRUD
- `backend/core/websocket_manager.py` - Event publishing
- `backend/utils/sunflower_registry.py` - Keep as cache, populate from DB

### Frontend:
- `frontend/templates/dashboard.html` - Remove mock, use real API
- `frontend/templates/base.html` - Fix sidebar toggle
- `frontend/templates/daena_office.html` - Real chat history
- `frontend/templates/department_office.html` - Real chat history
- `frontend/templates/founder_panel.html` - Show hidden departments
- `frontend/templates/councils.html` - Real council CRUD
- `frontend/static/js/*.js` - Remove mock arrays, use API

## Next Steps

1. Complete Phase 2: Run seed script, verify DB
2. Update all routes to use DB instead of in-memory
3. Implement WebSocket event publishing
4. Update frontend to remove mock data
5. Fix all specific issues (A-I)
6. Create comprehensive smoke test



