@echo off
setlocal EnableDelayedExpansion

echo ==========================================
echo Starting Daena Backend (Main Environment)
echo ==========================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Use the main Python environment
echo [INFO] Activating main Python environment...

if exist "venv_daena_main_py310\Scripts\activate.bat" (
    call venv_daena_main_py310\Scripts\activate.bat
    echo [OK] Activated: venv_daena_main_py310
    goto :env_activated
)
if exist "venv_daena_audio_py310\Scripts\activate.bat" (
    echo [WARNING] Main env not found, using audio env
    call venv_daena_audio_py310\Scripts\activate.bat
    echo [OK] Activated: venv_daena_audio_py310
    goto :env_activated
)
echo [ERROR] No virtual environment found!
echo [INFO] Expected: venv_daena_main_py310 or venv_daena_audio_py310
pause
exit /b 1

:env_activated
python --version
echo.

REM Check critical files
echo [INFO] Checking services...
if not exist "backend\services\websocket_manager.py" (
    echo [ERROR] WebSocket manager missing!
    pause
    exit /b 1
)
if not exist "backend\routes\realtime.py" (
    echo [ERROR] Realtime route missing!
    pause
    exit /b 1
)
if not exist "backend\services\ollama_scanner.py" (
    echo [ERROR] Ollama scanner missing!
    pause
    exit /b 1
)
if not exist "backend\services\action_dispatcher.py" (
    echo [ERROR] Action dispatcher missing!
    pause
    exit /b 1
)

echo [OK] All services present
echo.

REM Set environment variables
set PYTHONPATH=%CD%
echo [INFO] PYTHONPATH: %CD%

if not defined DATABASE_URL (
    set DATABASE_URL=sqlite:///daena.db
)
if not defined OLLAMA_BASE_URL (
    set OLLAMA_BASE_URL=http://localhost:11434
)

REM Create necessary folders
if not exist "logs" mkdir logs
if not exist "data" mkdir data
if not exist "workspace\screenshots" mkdir workspace\screenshots

echo.
echo ==========================================
echo Backend: http://localhost:8000
echo Environment: Main (venv_daena_main_py310)
echo ==========================================
echo.

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
if errorlevel 1 (
    echo.
    echo [ERROR] Backend crashed!
    pause
)

echo.
echo Backend stopped.
pause
