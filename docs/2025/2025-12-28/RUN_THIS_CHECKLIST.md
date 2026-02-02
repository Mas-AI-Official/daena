# RUN THIS CHECKLIST
**Quick verification guide for all fixes**

## 1. Start Services

### Option A: All-in-One (Recommended)
```batch
START_DAENA.bat
```
This will:
- Activate backend environment
- Start backend server
- Open browser to dashboard
- Keep window open for monitoring

### Option B: Manual Start
```batch
# Terminal 1: Backend
cd D:\Ideas\Daena_old_upgrade_20251213
venv_daena_main_py310\Scripts\activate
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Audio (optional)
scripts\START_AUDIO_ENV.bat
```

## 2. Verify URLs Work

Open these URLs in browser:

- ✅ **Dashboard**: http://127.0.0.1:8000/ui/dashboard
- ✅ **API Docs**: http://127.0.0.1:8000/docs
- ✅ **Department Page**: Click any department from dashboard
- ✅ **Daena Office**: http://127.0.0.1:8000/ui/daena-office

## 3. Test Department Chat History

1. Go to any department page (e.g., Engineering)
2. Send a message
3. Refresh the page
4. **Expected**: Message should still be there (loaded from backend)
5. Go to Daena Office
6. Select "Departments" category
7. **Expected**: Department chat should appear in the list

## 4. Test Brain Status

1. Check brain status indicator on dashboard
2. **If Ollama is running**: Should show "ONLINE" or "CONNECTED"
3. **If Ollama is offline**: Should show "OFFLINE" (not "CONNECTED")
4. Send message to Daena
5. **If Ollama is running**: Should get real AI response
6. **If Ollama is offline**: Should get deterministic offline message (not mock)

## 5. Run Tests

```batch
# Comprehensive test
python scripts/comprehensive_test_all_phases.py

# Smoke test
python scripts/smoke_test.py
```

## 6. Verify No Mock Data

- Department chat history should load from backend (not localStorage)
- Agents should use real brain when Ollama is available
- Brain status should reflect actual Ollama reachability

---

**All fixes are complete and ready for testing!**


