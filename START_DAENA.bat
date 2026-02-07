@echo off
chcp 65001 >nul
title Daena Startup Script

echo =====================================================
echo    DAENA AI - STARTUP SEQUENCE
echo =====================================================
echo.
echo Starting Daena with Super-Sync features...
echo.

:: Check if we're in the right directory
if not exist "backend" (
    echo [ERROR] Not in Daena root directory
    echo Please run this script from the Daena folder
    pause
    exit /b 1
)

if not exist "frontend" (
    echo [ERROR] Frontend directory not found
    echo Please ensure you're in the correct Daena directory
    pause
    exit /b 1
)

echo [✓] Directory check passed
echo.

:: Check system requirements
echo [INFO] Checking system requirements...

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed. Please install Python 3.11+
    pause
    exit /b 1
)
echo   - Python: OK

:: Check Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js is not installed. Please install Node.js 18+
    pause
    exit /b 1
)
echo   - Node.js: OK

:: Check Git
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARNING] Git not found. Some features may not work.
) else (
    echo   - Git: OK
)

echo.

:: Run database migration first
echo [INFO] Running database migration...
if exist "venv_daena\Scripts\python.exe" (
    call venv_daena\Scripts\activate.bat
    python backend\database\migrations\001_add_missing_tables.py
    call venv_daena\Scripts\deactivate.bat
) else (
    python backend\database\migrations\001_add_missing_tables.py
)
if %errorlevel% neq 0 (
    echo [WARNING] Migration may have had issues, continuing anyway...
)
echo.

:: Check for existing processes on required ports
echo [INFO] Checking for existing processes...

:: Check port 8000 (backend)
netstat -an | findstr ":8000" | findstr "LISTENING" >nul
if %errorlevel% equ 0 (
    echo [WARNING] Port 8000 is in use. Attempting to free it...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
        taskkill /F /PID %%a >nul 2>&1
        echo   - Stopped process on port 8000
    )
    timeout /t 2 /nobreak >nul
)

:: Check port 5173 (frontend)
netstat -an | findstr ":5173" | findstr "LISTENING" >nul
if %errorlevel% equ 0 (
    echo [WARNING] Port 5173 is in use. Attempting to free it...
    for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173" ^| findstr "LISTENING"') do (
        taskkill /F /PID %%a >nul 2>&1
        echo   - Stopped process on port 5173
    )
    timeout /t 2 /nobreak >nul
)

echo [✓] Port check complete
echo.

:: Display startup info
echo =====================================================
echo    STARTUP INFORMATION
echo =====================================================
echo.
echo Backend will start at: http://127.0.0.1:8000
echo Frontend will start at: http://localhost:5173/
echo.
echo API Documentation: http://127.0.0.1:8000/docs
echo Health Check: http://127.0.0.1:8000/health
echo.
echo Features enabled:
echo   - Real-time WebSocket sync
echo   - Model management (Ollama)
echo   - Skill operators
echo   - Project management
echo   - Tools library
echo.
echo =====================================================
echo.

:: Start Backend in new window
echo [1/2] Starting Backend Server...
start "Daena Backend" cmd /k START_BACKEND.bat

:: Wait for backend to initialize
echo [INFO] Waiting for backend to initialize (8 seconds)...
timeout /t 8 /nobreak >nul

:: Quick health check
echo [INFO] Checking backend health...
curl -s http://127.0.0.1:8000/health >nul 2>&1
if %errorlevel% equ 0 (
    echo [✓] Backend is healthy and responding
) else (
    echo [WARNING] Backend may still be starting up...
    echo [WARNING] Frontend will start anyway
)
echo.

:: Start Frontend in new window
echo [2/2] Starting Frontend Server...
start "Daena Frontend" cmd /k START_FRONTEND.bat

echo.
echo =====================================================
echo    STARTUP COMPLETE
echo =====================================================
echo.
echo Both servers are starting in separate windows.
echo.
echo Access Daena at: http://localhost:5173/
echo.
echo Press any key to show running processes...
echo.
pause >nul

:: Show running processes
echo.
echo =====================================================
echo    RUNNING PROCESSES
echo =====================================================
echo.
netstat -an | findstr ":8000" | findstr "LISTENING"
netstat -an | findstr ":5173" | findstr "LISTENING"
echo.

:: Option to view logs
echo Options:
echo   [1] View Backend Logs (backend.log)
echo   [2] View Frontend Logs (frontend.log)
echo   [3] Open Daena in Browser
echo   [4] Exit
echo.
set /p choice="Select option (1-4): "

if "%choice%"=="1" (
    if exist "backend.log" (
        type backend.log | more
    ) else (
        echo No backend.log file found
    )
    pause
)

if "%choice%"=="2" (
    if exist "frontend.log" (
        type frontend.log | more
    ) else (
        echo No frontend.log file found
    )
    pause
)

if "%choice%"=="3" (
    start http://localhost:5173/
)

if "%choice%"=="4" (
    echo.
    echo To stop Daena:
    echo   - Close the Backend and Frontend windows
    echo   - Or run: taskkill /F /IM node.exe /IM python.exe
    echo.
    echo Goodbye!
    timeout /t 3 /nobreak >nul
)
