@echo off
REM ============================================================================
REM Test Script - Verify START_DAENA.bat stays open
REM ============================================================================
echo Testing START_DAENA.bat...
echo.
echo This will launch START_DAENA.bat in a new window.
echo The window should stay open and not close automatically.
echo.
echo Press any key to launch...
pause >nul

REM Launch START_DAENA.bat in a new window
start "Daena Launcher Test" cmd /k "cd /d D:\Ideas\Daena_old_upgrade_20251213 && START_DAENA.bat"

echo.
echo START_DAENA.bat launched in new window.
echo.
echo Please check the new window:
echo   1. All phases should complete
echo   2. Monitoring loop should start
echo   3. Window should stay open
echo   4. Health checks should run every 30 seconds
echo.
echo This window will close in 10 seconds...
timeout /t 10 /nobreak >nul



