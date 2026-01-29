@echo off
REM Simple Backend Starter - No complex logic
setlocal EnableExtensions

cd /d "%~dp0.."
set "PROJECT_ROOT=%CD%"
set "PYTHONPATH=%PROJECT_ROOT%"

set "PY_MAIN="
if exist "%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe" set "PY_MAIN=%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe"
if not defined PY_MAIN if exist "%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe" set "PY_MAIN=%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe"
if not defined PY_MAIN (
    echo ERROR: No Python venv found. Create venv_daena_main_py310 or venv_daena_audio_py310
    pause
    exit /b 1
)

echo Starting backend...
echo Python: %PY_MAIN%
echo.

call "%PY_MAIN%" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

pause



