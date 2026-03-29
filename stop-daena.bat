@echo off
:: =============================================================
:: Daena — Stop Development Environment
:: =============================================================
:: Kills: Backend (uvicorn/python), Frontend (node), Ollama
:: =============================================================

title Daena — Shutting Down
color 0C
echo.
echo  ============================================
echo   DAENA — Stopping Development Environment
echo  ============================================
echo.

:: --- Stop Backend (uvicorn runs as python.exe) ---
echo  [1/3] Stopping backend...
for /f "tokens=2" %%a in ('tasklist /FI "WINDOWTITLE eq Daena Backend" /FO LIST 2^>NUL ^| find "PID:"') do (
    taskkill /PID %%a /T /F >NUL 2>&1
)
:: Also kill any uvicorn on port 8000
for /f "tokens=5" %%a in ('netstat -aon 2^>NUL ^| findstr ":8000.*LISTENING"') do (
    taskkill /PID %%a /F >NUL 2>&1
)
echo        Backend stopped.

:: --- Stop Frontend (node/vite) ---
echo  [2/3] Stopping frontend...
for /f "tokens=2" %%a in ('tasklist /FI "WINDOWTITLE eq Daena Frontend" /FO LIST 2^>NUL ^| find "PID:"') do (
    taskkill /PID %%a /T /F >NUL 2>&1
)
:: Also kill any vite on port 5173
for /f "tokens=5" %%a in ('netstat -aon 2^>NUL ^| findstr ":5173.*LISTENING"') do (
    taskkill /PID %%a /F >NUL 2>&1
)
echo        Frontend stopped.

:: --- Stop Ollama (optional — ask user) ---
echo  [3/3] Checking Ollama...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >NUL
if %ERRORLEVEL% EQU 0 (
    echo        Ollama is running.
    set /p STOP_OLLAMA="        Stop Ollama too? (y/N): "
    if /i "%STOP_OLLAMA%"=="y" (
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