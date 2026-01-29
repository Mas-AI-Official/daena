@echo off
REM Quick Backend Starter - Simple and Reliable
setlocal EnableExtensions

cd /d "%~dp0.."
set "PROJECT_ROOT=%CD%"

set "PY_MAIN="
if exist "%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe" set "PY_MAIN=%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe"
if not defined PY_MAIN if exist "%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe" set "PY_MAIN=%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe"
if not defined PY_MAIN (
    echo [ERROR] Python venv not found. Create: python -m venv venv_daena_main_py310
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

set "PYTHONPATH=%PROJECT_ROOT%"
"%PY_MAIN%" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

pause



