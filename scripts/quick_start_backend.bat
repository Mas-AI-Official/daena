@echo off
REM Quick Backend Starter - Simple and Reliable
setlocal EnableExtensions

cd /d "%~dp0.."

set "PY_MAIN=venv_daena_main_py310\Scripts\python.exe"
if not exist "%PY_MAIN%" (
    echo [ERROR] Python venv not found at: %PY_MAIN%
    echo [INFO] Please run: python -m venv venv_daena_main_py310
    pause
    exit /b 1
)

echo ============================================================================
echo Starting Daena Backend Server
echo ============================================================================
echo Python: %PY_MAIN%
echo Port: 8000
echo.
echo Press CTRL+C to stop
echo ============================================================================
echo.

"%PY_MAIN%" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

pause



