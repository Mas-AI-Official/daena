@echo off
setlocal EnableExtensions
REM Start backend with PYTHONPATH and EXECUTION_TOKEN (used by tests and run_manual_steps).

cd /d "%~dp0.."
set "PROJECT_ROOT=%CD%"
set "PYTHONPATH=%PROJECT_ROOT%"
if "%EXECUTION_TOKEN%"=="" set "EXECUTION_TOKEN=manual-verify-token"

set "PY="
if exist "%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe" set "PY=%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe"
if not defined PY if exist "%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe" set "PY=%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe"
if not defined PY set "PY=python"

echo Starting backend at http://127.0.0.1:8000 (PYTHONPATH set, EXECUTION_TOKEN=%EXECUTION_TOKEN%)...
"%PY%" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
