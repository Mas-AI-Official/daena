# Comprehensive Fix Plan - Real-Time & Persistent Daena
**Date:** 2025-12-24

## Audit Results Summary

### ✅ Already Working:
1. **Database Persistence**: ChatSession and ChatMessage tables exist with scope_type/scope_id
2. **Department Chat**: Uses backend API, not localStorage
3. **WebSocket Events**: Chat events are being published via event_bus
4. **/chat/start Endpoint**: Already returns {success, session_id, session}
5. **Council Chat**: Uses scope_type="council" and chat_service

### ⚠️ Needs Fixes:
1. **Ollama Auto-Start**: START_DAENA.bat doesn't start Ollama
2. **Daena "Departments" Category**: May need verification it shows all department chats
3. **Council WebSocket Events**: Need to verify events are published
4. **BAT File Stability**: Need to ensure no auto-close, proper 2-env activation

## Implementation Plan

### STEP 1: Verify Database ✅ (Already Done)
- ChatSession and ChatMessage tables exist
- scope_type and scope_id fields present
- chat_service provides unified access

### STEP 2: Verify Chat Model ✅ (Already Done)
- Single source of truth using ChatSession table
- scope_type: executive|department|agent|general|council
- scope_id: department id, agent id, council id

### STEP 3: Fix /chat/start Contract ✅ (Already Done)
- Returns {success, session_id, session}
- Smoke tests should pass

### STEP 4: Department UI ✅ (Already Done)
- Uses backend API via window.api.getDepartmentChatSessions()
- Not using localStorage

### STEP 5: Daena "Departments" Category ⚠️ (Needs Verification)
- daena_office.html has department category support
- Need to verify it loads all department chats correctly

### STEP 6: Council Chat ✅ (Already Done)
- Uses scope_type="council"
- Uses chat_service for persistence
- Debate endpoints exist

### STEP 7: WebSocket Event Bus ⚠️ (Needs Verification)
- event_bus.publish_chat_event is called in daena.py and departments.py
- Need to verify council.py also publishes events
- Need to verify frontend subscribes to chat.message events

### STEP 8: Fix BAT Files ⚠️ (Needs Fixes)
- Add Ollama auto-start
- Ensure proper 2-env activation
- Ensure no auto-close on errors
- Use goto labels instead of nested blocks

### STEP 9: Run Tests ⚠️ (Pending)
- Run smoke_test.py
- Verify all fixes work


