# Launch Troubleshooting Guide

**Date**: 2025-12-13

---

## "BAT Closes Instantly" - Root Causes & Prevention

### Root Cause 1: Error Without Pause
**Problem**: BAT file hits an error and exits immediately.

**How It's Now Prevented**:
- All commands wrapped in error checking
- On error: window stays open forever (`:WAIT_FOREVER` loop)
- Error logged to `logs/launch_YYYYMMDD_HHMMSS.log`
- Exact command and exit code displayed

### Root Cause 2: Wrong Folder
**Problem**: Launcher runs from wrong directory, can't find files.

**How It's Now Prevented**:
- `PROJECT_ROOT` explicitly set to `D:\Ideas\Daena_old_upgrade_20251213`
- `scripts/where_am_i.py` verifies folder before proceeding
- Fails loudly with huge warning if wrong folder

### Root Cause 3: Missing Dependencies
**Problem**: Python packages not installed, backend fails to start.

**How It's Now Prevented**:
- `scripts/setup_env.py` automatically installs dependencies
- `scripts/check_env.py` verifies critical packages before starting
- Fails loudly if packages missing

### Root Cause 4: Backend Crashes Immediately
**Problem**: Backend starts but crashes, launcher doesn't detect it.

**How It's Now Prevented**:
- Health check loop waits up to 120 seconds
- Tests `/api/v1/health/` endpoint
- Shows last 50 lines of backend log on failure
- Window stays open for inspection

---

## Where Logs Are

### Launcher Log
**Location**: `logs/launch_YYYYMMDD_HHMMSS.log`

**Contains**:
- All launcher output
- Error messages
- Command execution results
- Health check status

### Backend Log
**Location**: `logs/backend_YYYYMMDD_HHMMSS.log`

**Contains**:
- Backend server output
- Application errors
- Request logs

### How to View Logs

```batch
REM View launcher log (most recent)
powershell -Command "Get-Content logs\launch_*.log -Tail 50 | Select-Object -Last 1"

REM View backend log (most recent)
powershell -Command "Get-Content logs\backend_*.log -Tail 50 | Select-Object -Last 1"
```

---

## Common Fixes

### Fix 1: "Python not found"
**Solution**:
```batch
REM Create venv if missing
python -m venv venv_daena_main_py310

REM Or use system Python
set PY_MAIN=python
```

### Fix 2: "Requirements install failed"
**Solution**:
```batch
REM Install manually
venv_daena_main_py310\Scripts\python.exe -m pip install --upgrade pip
venv_daena_main_py310\Scripts\python.exe -m pip install -r requirements.txt
```

### Fix 3: "Backend not healthy"
**Solution**:
1. Check backend log: `logs/backend_*.log`
2. Look for Python errors or import failures
3. Verify `backend/main.py` exists and is valid
4. Check if port 8000 is already in use:
   ```batch
   netstat -ano | findstr :8000
   ```

### Fix 4: "Wrong folder detected"
**Solution**:
```batch
cd /d D:\Ideas\Daena_old_upgrade_20251213
START_DAENA.bat
```

### Fix 5: "Truncation markers detected"
**Solution**:
1. Run: `python scripts\verify_no_truncation.py`
2. Fix files listed in output
3. Remove truncation markers or restore full content

### Fix 6: "Duplicate files detected"
**Solution**:
1. Run: `python scripts\verify_no_duplicates.py`
2. Consolidate duplicate files
3. Update imports to use canonical file

---

## Diagnostic Mode

Enable diagnostic mode to see every command before execution:

```batch
set DAENA_DIAG=1
START_DAENA.bat
```

This will echo every command before running it.

---

## Manual Health Check

If launcher fails at health check, test manually:

```batch
REM Test health endpoint
python -c "import httpx; r=httpx.get('http://127.0.0.1:8000/api/v1/health/', timeout=5.0); print(f'Status: {r.status_code}')"
```

---

## Still Having Issues?

1. **Check logs first**: `logs/launch_*.log` and `logs/backend_*.log`
2. **Run smoke test**: `python tests\test_go_live_smoke.py`
3. **Verify environment**: `python scripts\check_env.py`
4. **Verify project root**: `python scripts\where_am_i.py`

---

**Last Updated**: 2025-12-13









