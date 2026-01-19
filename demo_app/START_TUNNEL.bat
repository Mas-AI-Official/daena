@echo off
REM ============================================
REM Daena Live Demo - Cloudflare Tunnel Setup
REM Exposes your local Daena instance to the internet
REM ============================================

echo.
echo  ========================================
echo   DAENA LIVE DEMO - CLOUDFLARE TUNNEL
echo  ========================================
echo.

REM Check if cloudflared is installed
where cloudflared >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] cloudflared not found!
    echo.
    echo Please install Cloudflare Tunnel:
    echo   1. Download from: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/
    echo   2. Or use: winget install Cloudflare.cloudflared
    echo.
    pause
    exit /b 1
)

REM Get the port (default 8000)
set PORT=8000
if not "%1"=="" set PORT=%1

echo [1/3] Starting Cloudflare Tunnel...
echo      Local server: http://localhost:%PORT%
echo.

REM Start tunnel (quick share mode - no account needed)
echo [INFO] Creating temporary tunnel (valid for 24 hours)
echo [INFO] Share the URL that appears below with demo attendees
echo.

cloudflared tunnel --url http://localhost:%PORT%

echo.
echo [DONE] Tunnel closed.
pause
