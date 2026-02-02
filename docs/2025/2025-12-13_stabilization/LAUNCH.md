# Daena One-Click Launch Instructions

**Date**: 2025-12-13  
**Status**: ✅ Ready for use

---

## Quick Start (One Command)

### Windows
```batch
cd /d D:\Ideas\Daena_old_upgrade_20251213
START_DAENA.bat
```

**That's it!** The launcher handles everything automatically.

---

## What the Launcher Does

The launcher performs these steps in order:

1. **Project Root Verification**
   - Ensures you're in the correct directory
   - Verifies `backend/main.py` exists

2. **Environment Setup**
   - Creates/activates virtual environment (`venv_daena_main_py310`)
   - Upgrades pip, setuptools, wheel
   - Installs dependencies from `requirements.txt`
   - Generates `requirements.lock.txt`

3. **Environment Verification**
   - Checks Python version (3.10+)
   - Verifies critical packages (FastAPI, uvicorn, httpx, etc.)
   - Verifies backend modules can be imported

4. **Guard Scripts**
   - Runs `scripts/verify_no_truncation.py` (fails if truncation markers found)
   - Runs `scripts/verify_no_duplicates.py` (fails if duplicate modules found)
   - **Stops launch if either guard fails**

5. **Backend Launch**
   - Preflight checks: Verifies `backend.main` and `uvicorn` can be imported
   - Launches uvicorn in separate window using safe launcher (`scripts/start_backend.bat`)
   - Backend runs on `http://127.0.0.1:8000`
   - All output logged to `logs/backend_<timestamp>.log`

6. **Health Check**
   - Waits up to 120 seconds for backend to become healthy
   - Polls `http://127.0.0.1:8000/api/v1/health/` every second
   - Shows progress every 10 seconds
   - **Fails loudly if backend doesn't become healthy**

7. **Smoke Tests**
   - Runs `scripts/smoke_test.py` automatically
   - Tests: Health endpoint, Daena chat, Agent chat
   - **Fails launch if any test fails**

8. **Browser Launch**
   - Opens dashboard: `http://127.0.0.1:8000/ui/dashboard`
   - Opens health page: `http://127.0.0.1:8000/ui/health`
   - Opens agents page: `http://127.0.0.1:8000/ui/agents`
   - Opens strategic meetings: `http://127.0.0.1:8000/ui/strategic-meetings`

9. **Final Status**
   - Shows "DAENA IS LIVE - PRESS CTRL+C TO STOP" banner
   - Launcher window stays open forever (infinite wait loop)
   - Backend continues running in separate window

---

## Expected Output

When successful, you'll see:

```
============================================================================
                    DAENA IS LIVE - PRESS CTRL+C TO STOP
============================================================================

Services:
  Backend:    http://127.0.0.1:8000
  API Docs:   http://127.0.0.1:8000/docs
  Health:     http://127.0.0.1:8000/api/v1/health/

UI Pages:
  Dashboard:  http://127.0.0.1:8000/ui/dashboard
  Health:     http://127.0.0.1:8000/ui/health
  Agents:     http://127.0.0.1:8000/ui/agents
  Meetings:   http://127.0.0.1:8000/ui/strategic-meetings

Logs:
  Launcher:   logs\launch_<timestamp>.log
  Backend:    logs\backend_<timestamp>.log
  Smoke:      logs\smoke_<timestamp>.log

============================================================================

This window will stay open. Close it to stop the launcher (backend continues).
Press Ctrl+C to exit this window.
```

---

## Manual Launch (If Launcher Fails)

If the launcher fails, you can launch manually:

```batch
REM 1. Navigate to project root
cd /d D:\Ideas\Daena_old_upgrade_20251213

REM 2. Activate venv
call venv_daena_main_py310\Scripts\activate.bat

REM 3. Set environment variables
set DISABLE_AUTH=1

REM 4. Start backend
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

REM 5. In another terminal, verify health
curl http://127.0.0.1:8000/api/v1/health/

REM 6. Open browser
start http://127.0.0.1:8000/ui/dashboard
```

---

## Environment Variables

### Required (Local Dev)
- `DISABLE_AUTH=1` - Bypass authentication (set automatically by launcher)

### Optional
- `DAENA_LAUNCHER_STAY_OPEN=1` - Keep window open on error (default: 1)
- `ENABLE_AUDIO=0` - Disable audio features (default: 0)

---

## Verification

After launch, verify:

1. **Backend is running**: Check the "Daena Backend Server" window
2. **Health endpoint**: Visit `http://127.0.0.1:8000/api/v1/health/`
3. **API docs**: Visit `http://127.0.0.1:8000/docs`
4. **Dashboard**: Visit `http://127.0.0.1:8000/ui/dashboard`
5. **Daena chat**: Type "Daena say hello" in dashboard chat
6. **Agent chat**: Go to agents page, select an agent, send a message

---

## Stopping Daena

1. **Stop backend**: Close the "Daena Backend Server" window (or press Ctrl+C in that window)
2. **Stop launcher**: Close the launcher window (or press Ctrl+C)

**Note**: The launcher window can be closed safely - it doesn't stop the backend. Only closing the backend window stops the server.

---

## Logs Location

All logs are in `logs/` directory:
- `logs/launch_<timestamp>.log` - Launcher output
- `logs/backend_<timestamp>.log` - Backend server output
- `logs/smoke_<timestamp>.log` - Smoke test output

---

**Status**: ✅ **READY TO USE**








