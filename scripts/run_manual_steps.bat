@echo off
setlocal EnableExtensions
REM Run health check + smoke + manual verification. Backend must be running (use scripts\start_backend_with_env.bat in another terminal).

cd /d "%~dp0.."
set "PROJECT_ROOT=%CD%"
set "PY="
if exist "%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe" set "PY=%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe"
if not defined PY if exist "%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe" set "PY=%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe"
if not defined PY set "PY=python"

if "%EXECUTION_TOKEN%"=="" set "EXECUTION_TOKEN=manual-verify-token"
if "%DAENA_BASE_URL%"=="" set "DAENA_BASE_URL=http://localhost:8000"

echo Checking backend at %DAENA_BASE_URL% ...
"%PY%" -c "import urllib.request; urllib.request.urlopen(urllib.request.Request('%DAENA_BASE_URL%/health'), timeout=5)" 2>nul
if errorlevel 1 (
    echo ERROR: Backend not reachable. Run: scripts\start_backend_with_env.bat
    exit /b 1
)
echo Backend is up.

echo.
echo --- Skill registry smoke (in-process, no server) ---
"%PY%" -m backend.scripts.smoke_skills_registry
if errorlevel 1 exit /b 1

echo.
echo --- Smoke tests ---
"%PY%" "%PROJECT_ROOT%\scripts\smoke_control_plane.py" --base %DAENA_BASE_URL% --token %EXECUTION_TOKEN%
if errorlevel 1 exit /b 1

echo.
echo --- Manual verification steps ---
"%PY%" "%PROJECT_ROOT%\scripts\manual_verification_steps.py"
if errorlevel 1 exit /b 1

echo.
echo All manual steps passed.
exit /b 0
