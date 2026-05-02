@echo off
setlocal enabledelayedexpansion
:: =============================================================
:: Daena - Stop Development Environment
:: =============================================================
:: Stops, in reverse start order:
::   [1/4] Frontend (Vite on :5173)
::   [2/4] Backend (Linux WSL2 OR Windows fallback)
::   [3/4] llama-server.exe (CUDA, :8080) -- mirrors start-daena.bat
::   [4/4] Ollama (only if running; optional, deprecated)
:: =============================================================

title Daena - Shutting Down
color 0C
echo.
echo  ============================================
echo   DAENA - Stopping Development Environment
echo  ============================================
echo.

:: --- Stop Frontend (node/vite) ---
echo  [1/4] Stopping frontend...
for /f "tokens=2" %%a in ('tasklist /FI "WINDOWTITLE eq Daena Frontend*" /FO LIST 2^>NUL ^| find "PID:"') do (
    taskkill /PID %%a /T /F >NUL 2>&1
)
for /f "tokens=5" %%a in ('netstat -aon 2^>NUL ^| findstr ":5173.*LISTENING"') do (
    taskkill /PID %%a /F >NUL 2>&1
)
echo        Frontend stopped.

:: --- Stop Backend (Linux WSL2) ---
echo  [2/4] Stopping backend (Linux + Windows fallback)...
wsl -d kali-linux -- bash -c "pkill -f 'uvicorn|run.py' 2>/dev/null" >NUL 2>NUL

:: Windows fallback backend window + any uvicorn on the bound port file
for /f "tokens=2" %%a in ('tasklist /FI "WINDOWTITLE eq Daena Backend*" /FO LIST 2^>NUL ^| find "PID:"') do (
    taskkill /PID %%a /T /F >NUL 2>&1
)
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "BPORT=8000"
if exist "%ROOT%\backend\.daena-port" (
    set /p BPORT=<"%ROOT%\backend\.daena-port"
)
for /f "tokens=5" %%a in ('netstat -aon 2^>NUL ^| findstr ":!BPORT!.*LISTENING"') do (
    taskkill /PID %%a /F >NUL 2>&1
)
:: Also clear the port file so health-check + start-daena rebuild it cleanly.
if exist "%ROOT%\backend\.daena-port" del "%ROOT%\backend\.daena-port" >NUL 2>NUL
echo        Backend stopped.

:: --- Stop llama-server (started by start-daena.bat) ---
echo  [3/4] Stopping llama-server...
tasklist /FI "IMAGENAME eq llama-server.exe" 2>NUL | find /I "llama-server.exe" >NUL
if %ERRORLEVEL% EQU 0 (
    taskkill /IM llama-server.exe /F >NUL 2>&1
    :: Backstop: kill anything still listening on :8080.
    for /f "tokens=5" %%a in ('netstat -aon 2^>NUL ^| findstr ":8080.*LISTENING"') do (
        taskkill /PID %%a /F >NUL 2>&1
    )
    echo        llama-server stopped.
) else (
    echo        llama-server not running.
)

:: --- Stop Ollama (deprecated; only present on legacy installs) ---
echo  [4/4] Checking Ollama (deprecated -- llama-server is canonical)...
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
