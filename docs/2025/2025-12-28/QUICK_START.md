# Quick Start Guide - 3 Steps

## Step 1: Start Backend
```cmd
cd D:\Ideas\Daena_old_upgrade_20251213
START_DAENA.bat
```

**Expected Result:**
- Backend window opens and stays open
- Dashboard opens in browser automatically
- Main launcher window stays open

## Step 2: Start Audio Environment (Optional)
```cmd
scripts\START_AUDIO_ENV.bat
```

**Expected Result:**
- Audio environment window opens
- Voice dependencies installed
- Window stays open

## Step 3: Verify Everything Works

### Test 1: Health Check
Open browser: http://127.0.0.1:8000/api/v1/health/
- Should return: `{"status": "healthy", ...}`

### Test 2: Dashboard
Open: http://127.0.0.1:8000/ui/dashboard
- Should load without errors
- Check browser console (F12) - no red errors

### Test 3: Department Chat Persistence
1. Go to a department page (e.g., Engineering)
2. Send a test message
3. Restart backend (CTRL+C in backend window, then restart START_DAENA.bat)
4. Reload department page
5. **Verify**: Message should still be there ✅

### Test 4: Daena Department Category
1. Go to Daena Office
2. Click "Departments" category
3. **Verify**: Department chats appear here (same messages, different view) ✅

## Troubleshooting

### Backend Not Starting
- Check `logs\backend_*.log` for errors
- Verify Python venv exists: `venv_daena_main_py310\Scripts\python.exe`
- Verify requirements installed: `pip list | findstr fastapi`

### Dashboard Not Loading
- Check browser console (F12) for errors
- Verify backend is running: http://127.0.0.1:8000/api/v1/health/
- Check network tab for failed requests

### Chat Not Persisting
- Check database exists: `backend\data\daena.db`
- Verify SQLite tables: Use DB browser or `sqlite3 backend\data\daena.db`
- Check backend logs for database errors


