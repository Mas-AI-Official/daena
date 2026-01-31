@echo off
setlocal EnableExtensions
REM Smoke-only: control plane (execution, proactive). Backend must be running. Set EXECUTION_TOKEN and optionally DAENA_BASE_URL.

set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"

set "PY="
if exist "%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe" set "PY=%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe"
if not defined PY if exist "%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe" set "PY=%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe"
if not defined PY set "PY=python"

set "BASE=%DAENA_BASE_URL%"
if not defined BASE set "BASE=http://localhost:8000"
if "%EXECUTION_TOKEN%"=="" set "EXECUTION_TOKEN=smoke-test-token"

echo Smoke tests (backend %BASE%)...
"%PY%" "%PROJECT_ROOT%\scripts\smoke_control_plane.py" --base "%BASE%" --token %EXECUTION_TOKEN%
set "EXIT_CODE=%ERRORLEVEL%"
if %EXIT_CODE% neq 0 (
    echo Smoke tests failed. Start backend: scripts\start_backend_with_env.bat
)
exit /b %EXIT_CODE%
