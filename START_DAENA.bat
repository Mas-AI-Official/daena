@echo off
REM ============================================================
REM DAENA AI VP - MASTER LAUNCHER v2.5
REM ============================================================
if "%~1"=="" (
    title DAENA Launcher
    cmd /k "%~f0" keepopen
    exit /b 0
)

setlocal EnableDelayedExpansion
cd /d "%~dp0"
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo ============================================================
echo   DAENA V2.5 - MODULAR AI OS
echo   Date: %DATE% %TIME%
echo ============================================================
echo.

REM ---- Environment Configuration ----
set "BACKEND_PORT=8000"
set "AUDIO_PORT=5001"
set "FRONTEND_PORT=5173"
set "DISABLE_AUTH=1"
set "ENVIRONMENT=development"
set "MODELS_ROOT=D:\Ideas\MODELS_ROOT"
set "PYTHONPATH=%ROOT%"

echo [INFO] MODELS_ROOT: %MODELS_ROOT%
echo [INFO] Ports: Backend:%BACKEND_PORT% Audio:%AUDIO_PORT% Frontend:%FRONTEND_PORT%
echo.

REM ---- 1. Environment Doctor ----
echo [1/5] Running Environment Doctor...
if exist "scripts\environment_doctor.py" (
    venv_daena_main_py310\Scripts\python.exe scripts\environment_doctor.py
) else (
    echo   [WARN] Environment Doctor script not found.
)
echo.

REM ---- 2. Check Database ----
echo [2/5] Checking Database...
if not exist "daena.db" (
    echo   [WARN] Database not found - creating...
) else (
    echo   [+] Database OK
)
echo.

REM ---- 3. Start Services ----
echo [3/5] Launching Core Services...

REM 3a. Backend (FastAPI)
echo   [*] Launching Backend...
start "DAENA - BACKEND" cmd /k call "%~dp0_daena_backend_launcher.bat" %BACKEND_PORT%

REM 3b. Audio Service (Coqui/ElevenLabs)
echo   [*] Launching Audio Service...
if exist "venv_daena_audio_py310\Scripts\python.exe" (
    start "DAENA - AUDIO" cmd /k call "%~dp0_daena_audio_launcher.bat" %AUDIO_PORT%
) else (
    echo     [SKIP] Audio venv not found.
)

REM 3c. Frontend (React/Vite)
echo   [*] Launching Frontend...
start "DAENA - FRONTEND" cmd /k "cd frontend && npm run dev -- --port %FRONTEND_PORT%"
echo.

REM ---- 4. Wait for Neural Link ----
echo [4/5] Establishing Neural Link...
set /a COUNT=0
:WAIT_LOOP
set /a COUNT+=1
powershell -NoProfile -Command "try{$null=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:%BACKEND_PORT%/health' -TimeoutSec 1;exit 0}catch{exit 1}" >nul 2>&1
if !errorlevel!==0 (
    echo   [+] Backend Ready on port %BACKEND_PORT%
    goto :READY
)
if %COUNT% GEQ 20 (
    echo   [WARN] Backend taking too long. Check the Backend window.
    goto :READY
)
timeout /t 1 /nobreak >nul
goto :WAIT_LOOP

:READY
echo.

REM ---- 5. Launch Dashboard ----
echo [5/5] Launching DAENA OS Dashboard...
start "" "http://localhost:%FRONTEND_PORT%"

echo.
echo ============================================================
echo   STARTUP COMPLETE - DAENA OS IS LIVE
echo ============================================================
echo.
pause
