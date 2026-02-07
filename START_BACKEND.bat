@echo off
setlocal EnableDelayedExpansion

echo ==========================================
echo Starting Daena Backend
echo ==========================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Check and activate environment
if exist "venv_daena\Scripts\activate.bat" (
    call venv_daena\Scripts\activate.bat
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
) else (
    echo [ERROR] No virtual environment found!
    pause
    exit /b 1
)

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

echo [OK] All services present
echo.

REM Set environment
set PYTHONPATH=%CD%
set DATABASE_URL=sqlite:///daena.db
set OLLAMA_BASE_URL=http://localhost:11434

REM Create logs folder
if not exist "logs" mkdir logs

echo ==========================================
echo Backend ready at http://localhost:8000
echo ==========================================
echo.
echo Press Ctrl+C to stop
echo.

REM Start backend
python -m backend.main

call deactivate
echo.
echo Backend stopped.
pause