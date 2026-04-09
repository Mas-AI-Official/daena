@echo off
setlocal enabledelayedexpansion
:: =============================================================
:: Daena -- Quick Start (works from any location)
:: =============================================================

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"
set "PORT_FILE=%BACKEND%\.daena-port"
set "DAENA_ENV_PRECEDENCE=env_file_first"

title Daena -- Quick Start
color 0B
echo.
echo  ============================================
echo   DAENA -- Quick Start
echo  ============================================
echo.

:: --- Find Python venv ---
set "PYTHON="
if exist "%ROOT%\venv_daena\Scripts\python.exe" (
    set "PYTHON=%ROOT%\venv_daena\Scripts\python.exe"
) else if exist "%BACKEND%\.venv\Scripts\python.exe" (
    set "PYTHON=%BACKEND%\.venv\Scripts\python.exe"
) else (
    echo  [ERROR] No Python venv found.
    echo          Expected: venv_daena\Scripts\python.exe
    echo          Or:       backend\.venv\Scripts\python.exe
    echo          Run setup-daena.bat first.
    pause
    exit /b 1
)
echo  Python: %PYTHON%

:: --- Start Ollama if not running ---
echo  [1/4] Checking Ollama...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >NUL
if %ERRORLEVEL% NEQ 0 (
    echo        Starting Ollama...
    start "" /MIN ollama serve
    timeout /t 3 /nobreak >NUL
) else (
    echo        Already running.
)

:: --- Start Backend via run.py ---
echo  [2/4] Starting backend...
if exist "%PORT_FILE%" del "%PORT_FILE%" >NUL 2>NUL
start "Daena Backend" /MIN cmd /c "cd /d %BACKEND% && "%PYTHON%" run.py"

:: Wait for port file (run.py writes it on startup)
set "BACKEND_PORT="
for /L %%I in (1,1,20) do (
    if exist "%PORT_FILE%" (
        set /p BACKEND_PORT=<"%PORT_FILE%"
        if defined BACKEND_PORT goto :port_ready
    )
    timeout /t 1 /nobreak >NUL
)
echo  [ERROR] Backend did not start in 20 seconds.
echo          Check the backend window for errors.
pause
exit /b 1

:port_ready
echo        Backend: http://localhost:!BACKEND_PORT!

:: --- Start Frontend ---
echo  [3/4] Starting frontend...
start "Daena Frontend" /MIN cmd /c "cd /d %FRONTEND% && npm run dev"
timeout /t 3 /nobreak >NUL

:: --- Open browser ---
echo  [4/4] Opening browser...
timeout /t 2 /nobreak >NUL
start "" http://localhost:5173

echo.
echo  ============================================
echo   DAENA IS RUNNING
echo  ============================================
echo.
echo   Frontend:  http://localhost:5173
echo   Backend:   http://localhost:!BACKEND_PORT!
echo   API docs:  http://localhost:!BACKEND_PORT!/docs
echo.
echo   To stop: run stop-daena.bat
echo  ============================================
echo.
pause
