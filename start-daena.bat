@echo off
setlocal enabledelayedexpansion
:: =============================================================
:: Daena — Start Development Environment
:: =============================================================
:: Starts: Ollama (if not running), Backend (run.py), Frontend (vite)
:: Opens: http://localhost:5173 in default browser
:: =============================================================

title Daena — Development Environment
color 0B
echo.
echo  ============================================
echo   DAENA — Starting Development Environment
echo  ============================================
echo.

set "ROOT=D:\Ideas\Daena"
set "VENV=%ROOT%\venv_daena"
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"
set "PORT_FILE=%BACKEND%\.daena-port"
set "BACKEND_PORT="
set "DAENA_ENV_PRECEDENCE=env_file_first"

:: --- Check venv exists ---
if not exist "%VENV%\Scripts\python.exe" (
    echo  [ERROR] Virtual environment not found at %VENV%
    echo  Run setup-daena.bat first.
    pause
    exit /b 1
)

:: --- Start Ollama if not running ---
echo  [1/4] Checking Ollama...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >NUL
if %ERRORLEVEL% NEQ 0 (
    echo        Starting Ollama...
    start "" /MIN ollama serve
    timeout /t 3 /nobreak >NUL
    echo        Ollama started.
) else (
    echo        Ollama already running.
)

:: --- Start Backend ---
echo  [2/4] Starting backend (run.py canonical path, backend\.env first)...
if exist "%PORT_FILE%" del "%PORT_FILE%" >NUL 2>NUL
start "Daena Backend" /MIN cmd /c "cd /d %BACKEND% && %VENV%\Scripts\python.exe run.py"

for /L %%I in (1,1,20) do (
    if exist "%PORT_FILE%" (
        set /p BACKEND_PORT=<"%PORT_FILE%"
        if defined BACKEND_PORT goto backend_ready
    )
    timeout /t 1 /nobreak >NUL
)

echo  [ERROR] Backend port file was not written. Frontend will not start.
echo          Canonical backend startup path is backend\run.py.
pause
exit /b 1

:backend_ready
echo        Backend port: http://localhost:!BACKEND_PORT!

:: --- Start Frontend ---
echo  [3/4] Starting frontend (vite)...
start "Daena Frontend" /MIN cmd /c "cd /d %FRONTEND% && npm run dev"
timeout /t 3 /nobreak >NUL

:: --- Open browser ---
echo  [4/4] Opening browser...
timeout /t 2 /nobreak >NUL
start "" http://localhost:5173

echo.
echo  ============================================
echo   DAENA is running!
echo  ============================================
echo.
echo   Frontend:  http://localhost:5173
echo   Backend:   http://localhost:!BACKEND_PORT!
echo   API docs:  http://localhost:!BACKEND_PORT!/docs
echo.
echo   To stop: run stop-daena.bat or close
echo   the Backend/Frontend terminal windows.
echo  ============================================
echo.
pause
