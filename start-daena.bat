@echo off
setlocal enabledelayedexpansion
:: =============================================================
:: Daena - Start Development Environment
:: =============================================================

title Daena - Development Environment
color 0B
chcp 65001 >NUL 2>NUL
echo.
echo  ============================================
echo   DAENA - Starting Development Environment
echo   Backend: WSL2 Linux  /  Frontend: Windows
echo  ============================================
echo.

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"
set "PORT_FILE=%BACKEND%\.daena-port"

:: --- Check WSL2 kali-linux is available ---
echo  [1/5] Checking WSL2 kali-linux...
wsl -d kali-linux -- echo "ok" >NUL 2>NUL
if !ERRORLEVEL! NEQ 0 (
    echo        [ERROR] WSL2 kali-linux not available.
    echo        Run:  wsl --install kali-linux
    echo.
    echo        Falling back to Windows backend...
    goto :windows_backend
)
echo        WSL2 kali-linux ready.

:: --- Start Ollama on Windows (accessible from Linux via localhost) ---
echo  [2/5] Checking Ollama...
set "OLLAMA_RUNNING=0"
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | findstr /I /C:"ollama.exe" >NUL 2>NUL && set "OLLAMA_RUNNING=1"
if "!OLLAMA_RUNNING!"=="0" (
    echo        Starting Ollama...
    start "" /MIN ollama serve
    timeout /t 3 /nobreak >NUL
    echo        Ollama started [localhost:11434].
) else (
    echo        Ollama already running.
)

:: --- Start Backend on Linux ---
echo  [3/5] Starting backend on Linux...
if exist "%PORT_FILE%" del "%PORT_FILE%" >NUL 2>NUL
start "Daena Backend [Linux]" cmd /k "wsl -d kali-linux -- bash /mnt/d/Ideas/Daena/backend/start-linux.sh"

:: Wait for port file
set "BACKEND_PORT="
for /L %%I in (1,1,30) do (
    if exist "%PORT_FILE%" (
        set /p BACKEND_PORT=<"%PORT_FILE%"
        if defined BACKEND_PORT goto :backend_ready
    )
    timeout /t 1 /nobreak >NUL
)

echo  [WARN] Backend port file not written after 30s.
echo         Check the Linux backend window for errors.
echo         Continuing with default port 8000...
set "BACKEND_PORT=8000"

:backend_ready
echo        Backend: http://localhost:!BACKEND_PORT! [Linux]

:: --- Start Frontend on Windows ---
echo  [4/5] Starting frontend [Vite]...
start "Daena Frontend" cmd /k "cd /d %FRONTEND% && npm run dev"
timeout /t 3 /nobreak >NUL

:: --- Open browser ---
echo  [5/5] Opening browser...
timeout /t 2 /nobreak >NUL
start "" http://localhost:5173

echo.
echo  ============================================
echo   DAENA IS RUNNING
echo  ============================================
echo.
echo   Frontend:  http://localhost:5173     [Windows]
echo   Backend:   http://localhost:!BACKEND_PORT!     [Linux]
echo   API docs:  http://localhost:!BACKEND_PORT!/docs
echo   Ollama:    http://localhost:11434    [Windows]
echo.
echo   Ollama runs on Windows with GPU.
echo   Backend on Linux calls Ollama via localhost.
echo.
echo   To stop: run stop-daena.bat
echo  ============================================
echo.
pause
exit /b 0

:: == Fallback: Windows backend (if WSL2 unavailable) ==========
:windows_backend
set "VENV=%ROOT%\venv_daena"
if not exist "%VENV%\Scripts\python.exe" set "VENV=%BACKEND%\.venv"
if not exist "%VENV%\Scripts\python.exe" (
    echo  [ERROR] No Python venv found. Run setup-daena.bat first.
    pause
    exit /b 1
)

echo  [2/5] Checking Ollama...
set "OLLAMA_RUNNING=0"
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | findstr /I /C:"ollama.exe" >NUL 2>NUL && set "OLLAMA_RUNNING=1"
if "!OLLAMA_RUNNING!"=="0" (
    start "" /MIN ollama serve
    timeout /t 3 /nobreak >NUL
)

echo  [3/5] Starting backend on Windows [fallback]...
if exist "%PORT_FILE%" del "%PORT_FILE%" >NUL 2>NUL
start "Daena Backend" cmd /k "cd /d %BACKEND% && %VENV%\Scripts\python.exe run.py"

set "BACKEND_PORT="
for /L %%I in (1,1,20) do (
    if exist "%PORT_FILE%" (
        set /p BACKEND_PORT=<"%PORT_FILE%"
        if defined BACKEND_PORT goto :win_backend_ready
    )
    timeout /t 1 /nobreak >NUL
)
set "BACKEND_PORT=8000"

:win_backend_ready
echo        Backend: http://localhost:!BACKEND_PORT! [Windows fallback]

echo  [4/5] Starting frontend...
start "Daena Frontend" cmd /k "cd /d %FRONTEND% && npm run dev"
timeout /t 3 /nobreak >NUL

echo  [5/5] Opening browser...
timeout /t 2 /nobreak >NUL
start "" http://localhost:5173

echo.
echo  ============================================
echo   DAENA IS RUNNING [Windows fallback mode]
echo  ============================================
echo.
echo   Frontend:  http://localhost:5173
echo   Backend:   http://localhost:!BACKEND_PORT!
echo   NOTE: Running without Linux security tools.
echo         Set up WSL2 for full power mode.
echo  ============================================
echo.
pause
