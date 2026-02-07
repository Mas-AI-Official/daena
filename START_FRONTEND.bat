@echo off
chcp 65001 >nul
echo ==========================================
echo  DAENA FRONTEND - Super Sync Mode
echo ==========================================
echo.

cd frontend

REM Check if node_modules exists
if not exist "node_modules" (
    echo [INFO] Installing dependencies...
    call npm install
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies!
        pause
        exit /b 1
    )
)

echo [INFO] Checking for missing dependencies...
call npm list sonner >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing sonner package...
    call npm install sonner
)

echo.
echo [INFO] Starting Frontend Development Server...
echo [INFO] URL: http://localhost:5173
echo [INFO] WebSocket: Connected to ws://localhost:8000
echo.
echo Press Ctrl+C to stop
echo.

npm run dev

if errorlevel 1 (
    echo.
    echo [ERROR] Frontend failed to start!
    echo [INFO] Common fixes:
    echo 1. Ensure Node.js 18+ is installed
    echo 2. Delete node_modules and run: npm install
    echo 3. Check if port 5173 is available
    pause
)
