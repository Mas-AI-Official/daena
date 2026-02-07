@echo off
setlocal EnableDelayedExpansion
title Daena AI - Super-Sync Startup

echo =====================================================
echo    DAENA AI - SUPER-SYNC STARTUP
echo =====================================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Check directories
if not exist "backend" (
    echo [ERROR] Backend directory not found!
    pause
    exit /b 1
)

if not exist "frontend" (
    echo [ERROR] Frontend directory not found!
    pause
    exit /b 1
)

echo [OK] Directories verified
echo.

REM Check Python
echo [INFO] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Install Python 3.10+
    pause
    exit /b 1
)
echo [OK] Python found:
python --version
echo.

REM Check Node.js
echo [INFO] Checking Node.js installation...
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found! Install Node.js 18+
    pause
    exit /b 1
)
echo [OK] Node.js found:
node --version
echo.

REM Detect Python environment
echo [INFO] Detecting Python environment...
if exist "venv_daena_main_py310\Scripts\activate.bat" (
    set VENV_NAME=venv_daena_main_py310
    echo [OK] Main environment found: venv_daena_main_py310
) else if exist "venv_daena_audio_py310\Scripts\activate.bat" (
    set VENV_NAME=venv_daena_audio_py310
    echo [OK] Audio environment found (using as fallback): venv_daena_audio_py310
) else (
    echo [ERROR] No virtual environment found!
    echo [INFO] Expected: venv_daena_main_py310 or venv_daena_audio_py310
    pause
    exit /b 1
)
echo.

REM Update Python dependencies
echo [INFO] Updating Python dependencies...
call %VENV_NAME%\Scripts\activate.bat
python -m pip install --upgrade pip -q
if exist "backend\requirements.txt" (
    pip install -r backend\requirements.txt -q
    if errorlevel 1 (
        echo [WARNING] Some Python packages may need manual installation
    )
)
call deactivate
echo [OK] Python dependencies updated
echo.

REM Update Node.js dependencies
echo [INFO] Checking Node.js dependencies...
cd frontend

if not exist "node_modules" (
    echo [INFO] Installing Node.js packages (first time)...
    call npm install
    if errorlevel 1 (
        echo [ERROR] npm install failed!
        pause
        exit /b 1
    )
)

REM Ensure critical packages
npm list sonner >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing sonner...
    call npm install sonner --save
)

if not exist ".env" (
    echo [INFO] Creating .env file...
    echo VITE_WS_URL=ws://localhost:8000/api/v1/realtime/ws > .env
    echo VITE_API_URL=http://localhost:8000 >> .env
)

cd ..
echo [OK] Frontend ready
echo.

REM Run database migration
echo [INFO] Running database migration...
call %VENV_NAME%\Scripts\activate.bat
python backend\database\migrations\001_add_missing_tables.py >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Migration may need manual run
) else (
    echo [OK] Migration complete
)
call deactivate
echo.

REM Free ports
echo [INFO] Freeing ports...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
timeout /t 2 /nobreak >nul
echo [OK] Ports cleared
echo.

echo =====================================================
echo    STARTING SERVICES
echo =====================================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173/
echo.

REM Start Backend
echo [1/2] Starting Backend (using %VENV_NAME%)...
start "Daena Backend" cmd /k START_BACKEND.bat

REM Wait for backend
echo [INFO] Waiting for backend (10s)...
timeout /t 10 /nobreak >nul

REM Check backend health
powershell -Command "try { Invoke-RestMethod -Uri 'http://localhost:8000/health' -TimeoutSec 5; exit 0 } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Backend may still be starting...
) else (
    echo [OK] Backend is responding
)

REM Start Frontend
echo [2/2] Starting Frontend...
start "Daena Frontend" cmd /k START_FRONTEND.bat

timeout /t 3 /nobreak >nul

echo.
echo =====================================================
echo    STARTUP COMPLETE!
echo =====================================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173/
echo.
echo Press any key to open browser...
pause >nul
start http://localhost:5173/
