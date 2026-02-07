@echo off
setlocal EnableDelayedExpansion
title Daena AI - Super-Sync Startup

echo =====================================================
echo    DAENA AI - SUPER-SYNC STARTUP
echo =====================================================
echo.

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
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found! Install Python 3.10+
    pause
    exit /b 1
)
echo [OK] Python found

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js not found! Install Node.js 18+
    pause
    exit /b 1
)
echo [OK] Node.js found

REM Activate Python environment
if exist "venv_daena\Scripts\activate.bat" (
    call venv_daena\Scripts\activate.bat
    echo [OK] Activated Python environment
) else (
    echo [!] Creating Python virtual environment...
    python -m venv venv_daena
    call venv_daena\Scripts\activate.bat
)

REM Update dependencies
echo.
echo [INFO] Updating dependencies...
pip install -q --upgrade pip
pip install -q -r backend\requirements.txt
call deactivate

REM Update Node.js dependencies
cd frontend
if not exist "node_modules" (
    echo [INFO] Installing Node.js dependencies...
    call npm install
)
call npm install sonner zustand --save

if not exist ".env" (
    echo VITE_WS_URL=ws://localhost:8000/api/v1/realtime/ws > .env
    echo VITE_API_URL=http://localhost:8000 >> .env
)
cd ..

echo [OK] Dependencies updated
echo.

REM Run database migration
echo [INFO] Running database migration...
call venv_daena\Scripts\activate.bat
python -c "import sys; sys.path.insert(0, '.'); exec(open('backend/database/migrations/001_add_missing_tables.py').read())" >nul 2>&1
call deactivate

echo [OK] Migration complete
echo.

REM Free ports
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173" ^| findstr "LISTENING"') do taskkill /F /PID %%a >nul 2>&1
timeout /t 2 /nobreak >nul

echo =====================================================
echo    STARTING SERVICES
echo =====================================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173/
echo.

REM Start Backend
echo [1/2] Starting Backend...
start "Daena Backend" cmd /c START_BACKEND.bat

REM Wait for backend
echo [INFO] Waiting for backend (10s)...
timeout /t 10 /nobreak >nul

REM Start Frontend
echo [2/2] Starting Frontend...
start "Daena Frontend" cmd /c START_FRONTEND.bat

echo.
echo =====================================================
echo    STARTUP COMPLETE!
echo =====================================================
echo.
echo Press any key to open Daena in browser...
pause >nul
start http://localhost:5173/