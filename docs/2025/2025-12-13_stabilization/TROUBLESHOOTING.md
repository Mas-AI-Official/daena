# Daena Launch Troubleshooting

**Date**: 2025-12-13

---

## Common Issues and Fixes

### Issue 1: Launcher Closes Immediately

**Symptoms**: Launcher window closes right after starting, no error visible

**Causes**:
- Script error before error handling is set up
- Missing project root directory
- Python not found

**Fix**:
1. Check you're running from correct directory: `D:\Ideas\Daena_old_upgrade_20251213`
2. Verify Python is installed: `python --version` (should be 3.10+)
3. Run launcher from command prompt to see errors:
   ```batch
   cd /d D:\Ideas\Daena_old_upgrade_20251213
   START_DAENA.bat
   ```

---

### Issue 2: Backend Window Closes Immediately

**Symptoms**: "Daena Backend Server" window opens then closes immediately

**Causes**:
- Import error in `backend.main`
- Missing dependencies
- Port 8000 already in use

**Fix**:
1. Check backend log: `logs/backend_<timestamp>.log`
2. Verify imports manually:
   ```batch
   python -c "import backend.main; print('OK')"
   python -c "import uvicorn; print('OK')"
   ```
3. Check if port 8000 is in use:
   ```batch
   netstat -ano | findstr :8000
   ```
   If port is in use, kill the process or change port in launcher

---

### Issue 3: Health Check Fails

**Symptoms**: Launcher waits 120 seconds then fails with "Backend did not become healthy"

**Causes**:
- Backend crashed during startup
- Backend listening on wrong host/port
- Firewall blocking port 8000

**Fix**:
1. Check backend window for errors
2. Check backend log: `logs/backend_<timestamp>.log`
3. Try accessing health endpoint manually:
   ```batch
   curl http://127.0.0.1:8000/api/v1/health/
   ```
4. Check Windows Firewall isn't blocking port 8000

---

### Issue 4: Smoke Tests Fail

**Symptoms**: Launcher shows "Go-live smoke tests FAILED"

**Causes**:
- Backend not fully started when tests run
- Agent ID format mismatch
- Network connectivity issues

**Fix**:
1. Check smoke test log: `logs/smoke_<timestamp>.log`
2. Verify backend is actually running (check backend window)
3. Run smoke test manually:
   ```batch
   python scripts\smoke_test.py
   ```
4. Check which specific test failed (health, Daena chat, or agent chat)

---

### Issue 5: Truncation Guard Fails

**Symptoms**: Launcher stops with "FATAL ERROR: Truncation markers detected"

**Causes**:
- A `.py`, `.html`, or `.js` file contains truncation markers
- File was accidentally truncated by editor/tool

**Fix**:
1. Check which file(s) have truncation markers:
   ```batch
   python scripts\verify_no_truncation.py
   ```
2. Restore truncated files from git:
   ```batch
   git checkout <filename>
   ```
3. If file is legitimately long, ensure it doesn't contain truncation phrases

---

### Issue 6: Duplicate Files Detected

**Symptoms**: Launcher stops with "FATAL ERROR: Duplicate files detected"

**Causes**:
- Multiple implementations of same module exist
- Duplicate routers or services

**Fix**:
1. Check which files are duplicates:
   ```batch
   python scripts\verify_no_duplicates.py
   ```
2. Consolidate duplicates - keep one canonical version
3. Update imports to use canonical version
4. Remove duplicate files

---

### Issue 7: "uvicorn not found"

**Symptoms**: Launcher stops with "FATAL ERROR: uvicorn not found"

**Causes**:
- Virtual environment not activated
- Dependencies not installed
- Wrong Python executable

**Fix**:
1. Activate venv manually:
   ```batch
   call venv_daena_main_py310\Scripts\activate.bat
   ```
2. Install uvicorn:
   ```batch
   pip install uvicorn
   ```
3. Or reinstall all dependencies:
   ```batch
   python scripts\setup_env.py
   ```

---

### Issue 8: "backend.main import failed"

**Symptoms**: Preflight check fails with "Cannot import backend.main"

**Causes**:
- Missing dependencies
- Syntax error in backend code
- Import path issues

**Fix**:
1. Check full error:
   ```batch
   python -c "import backend.main"
   ```
2. Install missing dependencies:
   ```batch
   pip install -r requirements.txt
   ```
3. Check for syntax errors in `backend/main.py`

---

### Issue 9: Dashboard Doesn't Load

**Symptoms**: Browser opens but dashboard shows error or blank page

**Causes**:
- Backend not running
- Wrong URL
- Template rendering error

**Fix**:
1. Verify backend is running (check backend window)
2. Check backend log for template errors
3. Try accessing directly: `http://127.0.0.1:8000/ui/dashboard`
4. Check browser console for JavaScript errors

---

### Issue 10: Agent Chat Returns 404

**Symptoms**: Smoke test fails with "Agent chat failed: status 404"

**Causes**:
- Agent ID format mismatch
- Agent not found in registry
- Route path incorrect

**Fix**:
1. Check agent ID format in smoke test log
2. Verify agents exist:
   ```batch
   curl http://127.0.0.1:8000/api/v1/agents
   ```
3. Check agent route exists: `/api/v1/agents/{agent_id}/chat`

---

## Log Locations

All logs are in `logs/` directory with timestamps:

- `logs/launch_<YYYYMMDD_HHMMSS>.log` - Launcher output
- `logs/backend_<YYYYMMDD_HHMMSS>.log` - Backend server output
- `logs/smoke_<YYYYMMDD_HHMMSS>.log` - Smoke test output

**To view last 50 lines of any log**:
```batch
powershell -Command "Get-Content 'logs\backend_<timestamp>.log' -Tail 50"
```

---

## Getting Help

If issues persist:

1. **Check all logs** in `logs/` directory
2. **Run manual verification**:
   ```batch
   python scripts\check_env.py
   python scripts\verify_no_truncation.py
   python scripts\verify_no_duplicates.py
   ```
3. **Test backend manually**:
   ```batch
   python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
   ```
4. **Check backend window** for runtime errors

---

## Prevention

To avoid common issues:

1. **Always run from project root**: `D:\Ideas\Daena_old_upgrade_20251213`
2. **Keep dependencies updated**: Run `python scripts\setup_env.py` regularly
3. **Check logs first**: Most errors are visible in logs
4. **Don't truncate files**: Use git to restore if accidentally truncated
5. **One launcher only**: Don't create duplicate launchers

---

**Last Updated**: 2025-12-13








