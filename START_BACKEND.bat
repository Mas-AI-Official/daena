@echo off
chcp 65001 >nul
echo ==========================================
echo  DAENA BACKEND - Super Sync Mode
echo ==========================================
echo.

REM Set Python Path
set PYTHONPATH=%cd%

REM Set Environment Variables for Super Sync
set WEBSOCKET_ENABLED=true
set AUTOMATION_ENABLE_DESKTOP=true
set AUTOMATION_ENABLE_BROWSER=true
set AUTOMATION_ENABLE_SHELL=false

REM Check if virtual environment exists
if exist "venv_daena\Scripts\activate.bat" (
    echo [INFO] Activating virtual environment...
    call venv_daena\Scripts\activate.bat
) else (
    echo [WARNING] Virtual environment not found. Using system Python.
)

echo [INFO] Starting Backend Server...
echo [INFO] WebSocket: Enabled (ws://localhost:8000/api/v1/realtime/ws)
echo [INFO] API: http://localhost:8000/api/v1
echo.

python -m backend.main

if errorlevel 1 (
    echo.
    echo [ERROR] Backend failed to start!
    echo [INFO] Checking common issues...
    echo 1. Ensure Python 3.10+ is installed
    echo 2. Install dependencies: pip install -r backend/requirements.txt
    echo 3. Check if port 8000 is available
    pause
)
