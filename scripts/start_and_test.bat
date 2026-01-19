@echo off
REM Start Backend and Run Tests
setlocal EnableExtensions

cd /d "%~dp0.."

set "PY_MAIN=venv_daena_main_py310\Scripts\python.exe"
if not exist "%PY_MAIN%" (
    echo [ERROR] Python venv not found
    pause
    exit /b 1
)

echo ============================================================================
echo STARTING BACKEND AND RUNNING TESTS
echo ============================================================================
echo.

echo [STEP 1] Starting backend server...
start "Daena Backend" cmd /k "%PY_MAIN% -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"

echo [STEP 2] Waiting for backend to start (25 seconds)...
timeout /t 25 /nobreak >nul

echo [STEP 3] Checking backend health...
"%PY_MAIN%" -c "import httpx; r = httpx.get('http://127.0.0.1:8000/api/v1/health/', timeout=5); print('✅ Backend is running - Status:', r.status_code)" 2>&1
if errorlevel 1 (
    echo [WARNING] Backend may not be ready yet, but continuing with tests...
)

echo.
echo [STEP 4] Running comprehensive tests...
echo ============================================================================
"%PY_MAIN%" scripts\comprehensive_test_all_phases.py

echo.
echo ============================================================================
echo TESTING COMPLETE
echo ============================================================================
echo.
echo Backend is still running in the "Daena Backend" window.
echo Close that window to stop the backend.
echo.
pause



