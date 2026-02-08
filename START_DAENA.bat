@echo off
setlocal EnableDelayedExpansion
title Daena AI - Startup Controller
color 0B

echo.
echo  =====================================================
echo     DAENA AI - SUPER-SYNC STARTUP
echo  =====================================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM =====================================================
REM PHASE 1: Validate Environment
REM =====================================================
echo [PHASE 1] Validating Environment...
echo.

REM Check directories
if not exist "backend" (
    echo [ERROR] Backend directory not found!
    goto :error_exit
)
if not exist "frontend" (
    echo [ERROR] Frontend directory not found!
    goto :error_exit
)
echo   [OK] Directories verified

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Python not found! Install Python 3.10+
    goto :error_exit
)
for /f "delims=" %%v in ('python --version 2^>^&1') do echo   [OK] %%v

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo   [ERROR] Node.js not found! Install Node.js 18+
    goto :error_exit
)
for /f "delims=" %%v in ('node --version') do echo   [OK] Node.js %%v

REM Detect Virtual Environment
set "VENV_NAME="
if exist "venv_daena_main_py310\Scripts\activate.bat" (
    set "VENV_NAME=venv_daena_main_py310"
    echo   [OK] Python env: venv_daena_main_py310
) else if exist "venv_daena_audio_py310\Scripts\activate.bat" (
    set "VENV_NAME=venv_daena_audio_py310"
    echo   [OK] Python env: venv_daena_audio_py310 ^(fallback^)
) else (
    echo   [ERROR] No virtual environment found!
    goto :error_exit
)

echo.
echo [PHASE 1] Complete!
echo.

REM =====================================================
REM PHASE 2: Prepare Dependencies
REM =====================================================
echo [PHASE 2] Checking Dependencies...
echo.

REM Check frontend node_modules
if not exist "frontend\node_modules" (
    echo   [INFO] Installing frontend dependencies...
    cd frontend
    call npm install
    cd ..
)
echo   [OK] Frontend dependencies ready

REM Create necessary folders
if not exist "logs" mkdir logs
if not exist "data" mkdir data
if not exist "workspace" mkdir workspace

echo   [OK] Directories created

echo.
echo [PHASE 2] Complete!
echo.

REM =====================================================
REM PHASE 3: Free Ports
REM =====================================================
echo [PHASE 3] Freeing Ports...
echo.

REM Kill any process using port 8000
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
    echo   [INFO] Killed process on port 8000 ^(PID: %%a^)
)

REM Kill any process using port 5173
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173" ^| findstr "LISTENING" 2^>nul') do (
    taskkill /F /PID %%a >nul 2>&1
    echo   [INFO] Killed process on port 5173 ^(PID: %%a^)
)

timeout /t 2 /nobreak >nul
echo   [OK] Ports cleared

echo.
echo [PHASE 3] Complete!
echo.

REM =====================================================
REM PHASE 4: Launch Services
REM =====================================================
echo [PHASE 4] Launching Services...
echo.

echo  =====================================================
echo     STARTING SERVICES
echo  =====================================================
echo.
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo   Docs:     http://localhost:8000/docs
echo.

REM Start Backend in new window
echo   [1/2] Starting Backend...
start "Daena Backend" cmd /k "cd /d "%~dp0" && call %VENV_NAME%\Scripts\activate.bat && set PYTHONPATH=%~dp0 && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"

REM Wait for backend to initialize
echo   [INFO] Waiting for backend to start ^(15s^)...
timeout /t 15 /nobreak >nul

REM Check backend health
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo   [WARN] Backend may still be starting...
) else (
    echo   [OK] Backend is responding
)

REM Start Frontend in new window
echo   [2/2] Starting Frontend...
start "Daena Frontend" cmd /k "cd /d "%~dp0%frontend" && npm run dev"

timeout /t 5 /nobreak >nul

echo.
echo [PHASE 4] Complete!
echo.

REM =====================================================
REM PHASE 5: Monitoring
REM =====================================================
echo  =====================================================
echo     STARTUP COMPLETE!
echo  =====================================================
echo.
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo   API Docs: http://localhost:8000/docs
echo.
echo   [INFO] Opening Dashboard in 5 seconds...
timeout /t 5 /nobreak >nul
start http://localhost:5173

REM Keep window open for monitoring
echo.
echo  =====================================================
echo     MONITORING MODE
echo  =====================================================
echo.
echo   Services are running in separate windows.
echo   This window will auto-check health every 60 seconds.
echo   Press CTRL+C to stop monitoring.
echo.

:monitor_loop
timeout /t 60 /nobreak >nul

REM Health check
curl -s http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    echo   [%time%] [WARN] Backend not responding
) else (
    echo   [%time%] [OK] Backend healthy
)

curl -s http://localhost:5173 >nul 2>&1
if errorlevel 1 (
    echo   [%time%] [WARN] Frontend not responding
) else (
    echo   [%time%] [OK] Frontend healthy
)

goto :monitor_loop

:error_exit
echo.
echo  =====================================================
echo     STARTUP FAILED
echo  =====================================================
echo.
echo   Please fix the above errors and try again.
echo.
pause
exit /b 1
