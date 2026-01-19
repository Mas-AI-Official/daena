@echo off
REM ============================================================
REM  DAENA DEMO LAUNCHER - AI Tinkerers Toronto Jan 2026
REM  Activates environment, starts backend, opens demo page
REM ============================================================

title Daena Demo Launcher - AI Tinkerers Toronto

echo.
echo  ========================================================
echo   🐝 DAENA DEMO LAUNCHER
echo   AI Tinkerers Toronto - January 29, 2026
echo  ========================================================
echo.

REM Navigate to project directory
cd /d D:\Ideas\Daena_old_upgrade_20251213

REM Set demo mode environment variable
set DEMO_MODE=1
echo [✓] Demo mode enabled (DEMO_MODE=1)

REM Set correct model environment variables (CRITICAL FIX)
REM Backend reads DEFAULT_LOCAL_MODEL (not DEFAULT_MODEL)
REM Backend reads OLLAMA_BASE_URL (not OLLAMA_HOST)
set DEFAULT_LOCAL_MODEL=deepseek-r1:8b
set OLLAMA_BASE_URL=http://127.0.0.1:11434
echo [✓] Model set to: %DEFAULT_LOCAL_MODEL%

REM Check if Ollama is running
echo.
echo [1/5] Checking Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo       [✓] Ollama is running
) else (
    echo       [!] Ollama not running - starting...
    start "" "ollama" serve
    timeout /t 3 /nobreak >nul
    curl -s http://localhost:11434/api/tags >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        echo       [✓] Ollama started successfully
    ) else (
        echo       [WARNING] Ollama failed to start - demo will use cloud/cached fallback
    )
)

REM Activate Python virtual environment
echo.
echo [2/5] Activating Python environment...
if exist "venv_daena_main_py310\Scripts\activate.bat" (
    call venv_daena_main_py310\Scripts\activate.bat
    echo       [✓] Virtual environment activated
) else (
    echo       [!] venv not found - using system Python
)

REM Check Python
echo.
echo [3/5] Verifying Python...
python --version 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo       [ERROR] Python not found!
    pause
    exit /b 1
)

REM Start backend server
echo.
echo [4/5] Starting Daena backend server...
echo       (This window will stay open for the server)
echo.

REM Open demo page in browser after a short delay
echo [5/5] Opening demo page in 5 seconds...
start "" cmd /c "timeout /t 5 /nobreak >nul && start http://localhost:8000/demo"

REM Also open smoke test option
echo.
echo ========================================================
echo   DEMO READY!
echo.
echo   Demo Page:  http://localhost:8000/demo
echo   API Health: http://localhost:8000/api/v1/demo/health
echo   
echo   To run smoke test: python scripts\demo_smoke_test.py
echo ========================================================
echo.
echo Starting backend... (Press Ctrl+C to stop)
echo.

REM Start the backend (this will block and keep the window open)
python -m backend.main
