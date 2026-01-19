@echo off
REM Test All - Start backend and run comprehensive tests
setlocal EnableExtensions

cd /d "%~dp0.."

echo ============================================================================
echo TESTING ALL FEATURES
echo ============================================================================
echo.

REM Check Python
set "PY_MAIN=venv_daena_main_py310\Scripts\python.exe"
if not exist "%PY_MAIN%" (
    echo [ERROR] Python venv not found
    pause
    exit /b 1
)

echo [1/3] Starting backend in background...
start "Daena Backend Test" /min cmd /c "cd /d %CD% && %PY_MAIN% -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 > logs\test_backend.log 2>&1"

echo [2/3] Waiting for backend to start (20 seconds)...
timeout /t 20 /nobreak >nul

echo [3/3] Running comprehensive tests...
"%PY_MAIN%" scripts\comprehensive_test_all_phases.py

echo.
echo ============================================================================
echo Tests complete. Check results above.
echo Backend is still running in background window.
echo Press any key to stop backend and exit...
pause >nul

REM Stop backend
taskkill /FI "WINDOWTITLE eq Daena Backend Test*" /T /F >nul 2>&1



