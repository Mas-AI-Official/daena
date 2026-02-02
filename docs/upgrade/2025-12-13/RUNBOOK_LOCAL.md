# Runbook: Local Development

**Date**: 2025-12-13  
**Purpose**: Exact one-click launch steps for Daena system

---

## One-Click Launch

### Command
```batch
cd D:\Ideas\Daena_old_upgrade_20251213
START_DAENA.bat
```

### What It Does (Automatic)

1. **Bootstrap** (via `scripts/bootstrap_venv.bat`):
   - Creates venv if missing
   - Upgrades pip, setuptools, wheel
   - Installs from `requirements.txt`
   - Generates `requirements.lock.txt`

2. **Guardrails**:
   - Runs `verify_no_truncation.py` (fails if truncation detected)
   - Runs `verify_no_duplicates.py` (fails if duplicates detected)
   - Runs `verify_file_integrity.py` (fails if core files modified)

3. **Environment**:
   - Sets `DISABLE_AUTH=1` (dev mode)
   - Sets local LLM vars

4. **Backend**:
   - Starts uvicorn on port 8000
   - Logs to `logs/backend_YYYYMMDD_HHMMSS.log`

5. **Health Check**:
   - Waits for `/api/v1/health/` to return 200 (up to 120 seconds)
   - Shows log tail on failure

6. **Browser**:
   - Opens `http://127.0.0.1:8000/ui/dashboard`
   - Opens `http://127.0.0.1:8000/ui/health`

---

## Expected URLs

After launcher completes, these URLs should be accessible:

### UI Pages
- **Dashboard**: http://127.0.0.1:8000/ui/dashboard
- **Agents**: http://127.0.0.1:8000/ui/agents
- **Departments**: http://127.0.0.1:8000/ui/departments
- **Council**: http://127.0.0.1:8000/ui/council-dashboard
- **Health**: http://127.0.0.1:8000/ui/health

### API Endpoints
- **API Docs**: http://127.0.0.1:8000/docs
- **Health**: http://127.0.0.1:8000/api/v1/health/
- **Daena Chat**: `POST http://127.0.0.1:8000/api/v1/daena/chat`
- **Brain Status**: http://127.0.0.1:8000/api/v1/brain/status
- **Brain Queue**: http://127.0.0.1:8000/api/v1/brain/queue

---

## Manual Steps (If Launcher Fails)

### Step 1: Bootstrap
```batch
cd D:\Ideas\Daena_old_upgrade_20251213
call scripts\bootstrap_venv.bat
```

### Step 2: Run Guardrails
```batch
call venv_daena_main_py310\Scripts\activate.bat
python scripts\verify_no_truncation.py
python scripts\verify_no_duplicates.py
python scripts\verify_file_integrity.py
```

### Step 3: Set Environment
```batch
set DISABLE_AUTH=1
set DAENA_LAUNCHER_STAY_OPEN=1
```

### Step 4: Start Backend
```batch
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### Step 5: Verify Health
```batch
REM In another terminal:
curl http://127.0.0.1:8000/api/v1/health/
REM Should return: {"status": "ok", ...}
```

### Step 6: Open Browser
```batch
start http://127.0.0.1:8000/ui/dashboard
```

---

## Running Tests

### End-to-End Tests
```batch
cd D:\Ideas\Daena_old_upgrade_20251213
call venv_daena_main_py310\Scripts\activate.bat
set DISABLE_AUTH=1
python -m pytest tests\test_daena_go_live.py -v
```

### All Tests
```batch
python -m pytest tests\ -v
```

---

## Troubleshooting

### Port 8000 Already in Use
```batch
REM Find process using port 8000
netstat -ano | findstr :8000

REM Kill process (replace PID with actual process ID)
taskkill /PID <PID> /F
```

### Venv Not Found
```batch
REM Recreate venv
python -m venv venv_daena_main_py310
call venv_daena_main_py310\Scripts\activate.bat
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### Guardrails Fail
- **Truncation detected**: Check `scripts/verify_no_truncation.py` output for file names
- **Duplicates detected**: Check `scripts/verify_no_duplicates.py` output for duplicate files
- **File integrity failed**: Run `python scripts\verify_file_integrity.py --update-baseline` to update baseline

### Backend Won't Start
- Check `logs/backend_*.log` for errors
- Verify Python version: `python --version` (should be 3.10+)
- Verify dependencies: `pip list` (should show fastapi, uvicorn, etc.)

### Health Check Fails
- Check backend logs for startup errors
- Verify port 8000 is not blocked by firewall
- Try accessing http://127.0.0.1:8000/docs manually

---

## Environment Variables

### Required (Local Dev)
- `DISABLE_AUTH=1` - Bypass authentication (default in launcher)

### Optional
- `DAENA_UPDATE_REQUIREMENTS=1` - Update requirements.txt from lock
- `DAENA_RUN_TESTS=1` - Run tests before launch
- `DAENA_LAUNCHER_STAY_OPEN=1` - Keep launcher window open (default)

---

## Logs Location

- **Backend logs**: `logs/backend_YYYYMMDD_HHMMSS.log`
- **Launcher output**: Console window (stays open)

---

## Quick Verification

After launcher completes, verify:

1. **Dashboard loads**: http://127.0.0.1:8000/ui/dashboard
2. **Can chat with Daena**: Type message in dashboard chat, get response
3. **Brain status works**: Click "Brain" button, see status
4. **Agents list works**: http://127.0.0.1:8000/api/v1/agents returns 200

---

**Status**: ✅ **READY FOR USE**

**One Command**: `START_DAENA.bat`
