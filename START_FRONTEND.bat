@echo off
setlocal EnableDelayedExpansion

echo ==========================================
echo Starting Daena Frontend
echo ==========================================
echo.

cd /d "%~dp0"
cd frontend

REM Check node_modules
if not exist "node_modules" (
    echo [INFO] Installing dependencies...
    call npm install
)

REM Check critical packages
if not exist "node_modules\sonner" call npm install sonner
if not exist "node_modules\zustand" call npm install zustand

REM Create .env if missing
if not exist ".env" (
    echo VITE_WS_URL=ws://localhost:8000/api/v1/realtime/ws > .env
    echo VITE_API_URL=http://localhost:8000 >> .env
)

echo ==========================================
echo Frontend ready at http://localhost:5173/
echo ==========================================
echo.
echo Press Ctrl+C to stop
echo.

call npm run dev

echo.
echo Frontend stopped.
pause