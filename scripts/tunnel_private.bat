@echo off
REM ============================================
REM Daena Private Tunnel - Full System Access
REM Requires Cloudflare Access for authentication
REM ============================================

echo.
echo  ========================================
echo   DAENA PRIVATE TUNNEL - FULL SYSTEM
echo  ========================================
echo.
echo  WARNING: This exposes the FULL Daena system.
echo  Only use with Cloudflare Access protection!
echo.

REM Check if cloudflared is installed
where cloudflared >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] cloudflared not found!
    echo.
    echo Please install Cloudflare Tunnel:
    echo   winget install Cloudflare.cloudflared
    echo.
    pause
    exit /b 1
)

REM Get the port (default 8000)
set PORT=8000
if not "%1"=="" set PORT=%1

echo [1/3] Starting Private Cloudflare Tunnel...
echo      Local server: http://localhost:%PORT%
echo.

REM For private tunnels, you should use a named tunnel with Access
echo [INFO] For production use, create a named tunnel:
echo   cloudflared tunnel create daena-private
echo   cloudflared tunnel route dns daena-private daena.yourdomain.com
echo   Add Cloudflare Access policy to restrict access
echo.

echo [INFO] Starting quick tunnel (24h expiry)...
echo [INFO] REMINDER: Add Cloudflare Access to protect this URL!
echo.

cloudflared tunnel --url http://localhost:%PORT%

echo.
echo [DONE] Tunnel closed.
pause
