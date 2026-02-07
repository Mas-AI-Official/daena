@echo off
chcp 65001 >nul
echo ==========================================
echo  DAENA - Super Sync Startup
echo ==========================================
echo.
echo This will start:
echo   1. Backend Server (Port 8000)
echo   2. Frontend Dev Server (Port 5173)
echo.
echo Press any key to continue...
pause >nul
cls

REM Start Backend in new window
echo [1/2] Starting Backend Server...
start "DAENA BACKEND" cmd /k "START_BACKEND.bat"

REM Wait for backend to initialize
echo [INFO] Waiting for backend (5 seconds)...
timeout /t 5 /nobreak >nul

REM Start Frontend in new window
echo [2/2] Starting Frontend Server...
start "DAENA FRONTEND" cmd /k "START_FRONTEND.bat"

echo.
echo ==========================================
echo  DAENA is starting up!
echo ==========================================
echo.
echo Frontend:  http://localhost:5173
echo Backend:   http://localhost:8000
echo WebSocket: ws://localhost:8000/api/v1/realtime/ws
echo.
echo Both servers are running in separate windows.
echo Close those windows to stop the servers.
echo.
pause
