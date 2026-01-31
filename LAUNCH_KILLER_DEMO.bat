@echo off
setlocal
cd /d "%~dp0"
echo Launching Daena Killer Demo...
call "%~dp0scripts\run_killer_demo.bat"
if errorlevel 1 (
    echo.
    echo [ERROR] Launcher failed to start the demo.
    pause
)

