@echo off
REM Simple Backend Starter - No complex logic
setlocal EnableExtensions

cd /d "%~dp0.."

set "PY_MAIN=venv_daena_main_py310\Scripts\python.exe"
if not exist "%PY_MAIN%" (
    echo ERROR: Python venv not found at: %PY_MAIN%
    pause
    exit /b 1
)

echo Starting backend...
echo Python: %PY_MAIN%
echo.

call "%PY_MAIN%" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

pause



