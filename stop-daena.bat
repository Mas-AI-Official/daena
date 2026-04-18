@echo off
setlocal enabledelayedexpansion
:: =============================================================
:: Daena — Stop Development Environment
:: =============================================================
:: Kills: Backend (Linux or Windows), Frontend (node), Ollama
:: =============================================================

title Daena — Shutting Down
color 0C
echo.
echo  ============================================
echo   DAENA — Stopping Development Environment
echo  ============================================
echo.

:: --- Stop Backend (Linux WSL2) ---
echo  [1/4] Stopping Linux backend...
wsl -d kali-linux -- bash -c "pkill -f 'uvicorn|run.py' 2>/dev/null" >NUL 2>NUL
echo        Linux backend stopped.

:: --- Stop Backend (Windows, if running) ---
echo  [2/4] Stopping Windows backend...
for /f "tokens=2" %%a in ('tasklist /FI "WINDOWTITLE eq Daena Backend*" /FO LIST 2^>NUL ^| find "PID:"') do (
    taskkill /PID %%a /T /F >NUL 2>&1
)
:: Also kill any uvicorn on port 8000
for /f "tokens=5" %%a in ('netstat -aon 2^>NUL ^| findstr ":8000.*LISTENING"') do (
    taskkill /PID %%a /F >NUL 2>&1
)
echo        Windows backend stopped.

:: --- Stop Frontend (node/vite) ---
echo  [3/4] Stopping frontend...
for /f "tokens=2" %%a in ('tasklist /FI "WINDOWTITLE eq Daena Frontend*" /FO LIST 2^>NUL ^| find "PID:"') do (
    taskkill /PID %%a /T /F >NUL 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon 2^>NUL ^| findstr ":5173.*LISTENING"') do (
    taskkill /PID %%a /F >NUL 2>&1
)
echo        Frontend stopped.

:: --- Stop Ollama (optional) ---
echo  [4/4] Checking Ollama...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >NUL
if %ERRORLEVEL% EQU 0 (
    echo        Ollama is running.
    set /p STOP_OLLAMA="        Stop Ollama too? (y/N): "
    if /i "!STOP_OLLAMA!"=="y" (
        taskkill /IM ollama.exe /F >NUL 2>&1
        echo        Ollama stopped.
    ) else (
        echo        Ollama left running.
    )
) else (
    echo        Ollama not running.
)

echo.
echo  ============================================
echo   DAENA stopped. All services shut down.
echo  ============================================
echo.
pause
