# Quick Test Guide
**Date:** 2025-12-24

## Quick Verification Steps

### 1. Start Daena
```batch
START_DAENA.bat
```

**Expected**:
- PHASE 2C should start Ollama (if not running)
- Backend should start and stay open
- No syntax errors

### 2. Test Department Chat Persistence
1. Open browser: http://127.0.0.1:8000/ui/departments/engineering
2. Send a message: "Hello Engineering"
3. Restart backend (CTRL+C, then restart)
4. Reload page
5. **Verify**: Message should still be there

### 3. Test Daena "Departments" Category
1. Open: http://127.0.0.1:8000/ui/daena-office
2. Select "Departments" from category dropdown
3. **Verify**: All department chats appear in the list

### 4. Test Real-Time Updates
1. Open Daena Office in two browser tabs
2. Send message in Tab 1
3. **Verify**: Message appears in Tab 2 immediately (via WebSocket)

### 5. Run Smoke Test
```bash
python scripts/smoke_test.py
```

**Expected**: All tests pass, including session_id check

## Common Issues & Fixes

### Issue: "No session_id in response"
**Fix**: Already fixed - /chat/start returns session_id

### Issue: Department chats not showing in Daena
**Fix**: Already fixed - api-client.js now filters by scope_type=department

### Issue: Ollama not starting
**Fix**: START_DAENA.bat now auto-starts Ollama (PHASE 2C)

### Issue: WebSocket events not working
**Fix**: All routes now use event_bus (council.py migrated)


