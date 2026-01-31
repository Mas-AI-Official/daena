@echo off
setlocal EnableExtensions
REM Quick verification: Python, backend imports, DB, routes, health. Does not run smoke or manual verification.

cd /d "%~dp0.."
set "PROJECT_ROOT=%CD%"
set "PY="
if exist "%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe" set "PY=%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe"
if not defined PY if exist "%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe" set "PY=%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe"
if not defined PY set "PY=python"

echo [1/5] Python...
if not "%PY%"=="python" if not exist "%PY%" (
    echo [ERROR] Python venv not found
    exit /b 1
)
"%PY%" --version
echo.

echo [2/5] Backend imports...
"%PY%" -c "import backend.main; print('[OK] Backend imports')" 2>&1
if errorlevel 1 (
    echo [ERROR] Backend import failed
    exit /b 1
)
echo.

echo [3/5] Database...
if exist "%PROJECT_ROOT%\daena.db" (
    echo [OK] daena.db exists
) else (
    echo [WARNING] daena.db not found
)
echo.

echo [4/5] Routes...
"%PY%" -c "from backend.routes.council import router; print('[OK] Council router')" 2>&1
"%PY%" -c "from backend.routes.intelligence import router; print('[OK] Intelligence router')" 2>&1
echo.

echo [5/5] Backend health (if running)...
"%PY%" -c "import urllib.request; urllib.request.urlopen(urllib.request.Request('http://localhost:8000/health'), timeout=2); print('[OK] Backend is running')" 2>nul
if errorlevel 1 echo [INFO] Backend not running. Start: scripts\start_backend_with_env.bat
echo.
echo For smoke + manual verification: scripts\run_manual_steps.bat
exit /b 0
