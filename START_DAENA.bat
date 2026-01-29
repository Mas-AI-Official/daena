@echo off
REM ============================================================
REM DAENA AI VP - MASTER LAUNCHER (DEBUG MODE)
REM ============================================================
REM This version has extensive error handling to prevent auto-close

echo ============================================================
echo   DAENA LAUNCHER - DEBUG MODE
echo   Date: %DATE% %TIME%
echo ============================================================
echo.

REM Capture the script directory
set "ROOT=%~dp0"
echo [INFO] Root directory: %ROOT%
cd /d "%ROOT%"
if errorlevel 1 (
    echo [ERROR] Failed to change to root directory!
    pause
    exit /b 1
)

REM Enable delayed expansion
setlocal EnableExtensions EnableDelayedExpansion
if errorlevel 1 (
    echo [ERROR] Failed to enable delayed expansion!
    pause
    exit /b 1
)

REM ---- Environment Configuration ----
set "BACKEND_PORT=8000"
echo [INFO] Finding available port...
for /f "delims=" %%a in ('powershell -NoProfile -Command "$p=8000; while($p -lt 8010){try{$l=New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback,$p); $l.Start(); $l.Stop(); break}catch{$p++}}; Write-Output $p" 2^>nul') do set "BACKEND_PORT=%%a"
echo [INFO] Using Port: %BACKEND_PORT%
set "AUDIO_PORT=5001"
set "DISABLE_AUTH=1"
set "ENVIRONMENT=development"

REM -- BUG FIXES & CONFIGURATION --
set "PYTHONPATH=%ROOT%"
if exist "%ROOT%venv_daena_main_py310\Lib\site-packages\playwright" set "PLAYWRIGHT_BROWSERS_PATH=%ROOT%venv_daena_main_py310\Lib\site-packages\playwright\driver\package\.local-browsers"
set "OLLAMA_HOST=http://127.0.0.1:11434"
set "DAENA_CREATOR=Masoud"
set "DEFAULT_MODEL=deepseek-r1:8b"
set "ENABLE_LOCAL_ROUTER=true"

REM -- QA GUARDIAN CONFIGURATION (NEW) --
set "QA_GUARDIAN_ENABLED=true"
set "QA_GUARDIAN_AUTO_FIX=false"
set "QA_GUARDIAN_KILL_SWITCH=false"
set "QA_GUARDIAN_LOG_LEVEL=INFO"

REM -- MODELS_ROOT (shared brain: Ollama, XTTS, Whisper, reasoning models) --
if not defined MODELS_ROOT set "MODELS_ROOT=D:\Ideas\MODELS_ROOT"
set "OLLAMA_MODELS=%MODELS_ROOT%\ollama"
set "TTS_HOME=%MODELS_ROOT%\xtts"

REM -- HF CACHE under MODELS_ROOT --
if not defined HF_HOME set "HF_HOME=%MODELS_ROOT%\hf"
if not defined TRANSFORMERS_CACHE set "TRANSFORMERS_CACHE=%HF_HOME%\transformers"
echo [INFO] MODELS_ROOT: %MODELS_ROOT%
echo [INFO] HF Cache: %HF_HOME%

REM -- VOICE CONFIGURATION (Set your API key below) --
set "ELEVENLABS_API_KEY=your_elevenlabs_api_key_here"
REM To get an API key, visit: https://elevenlabs.io/
REM Leave as "your_elevenlabs_api_key_here" to disable voice cloning

echo [INFO] Environment configured:
echo        BACKEND_PORT=%BACKEND_PORT%
echo        AUDIO_PORT=%AUDIO_PORT%
echo        DISABLE_AUTH=%DISABLE_AUTH%
echo        CREATOR=%DAENA_CREATOR%
echo        MODEL=%DEFAULT_MODEL%
echo        QA_GUARDIAN=%QA_GUARDIAN_ENABLED%
echo.

REM ---- 1. Create directories ----
echo [1/6] Creating directories...
if not exist "logs" mkdir "logs"
if not exist "backups" mkdir "backups"
echo   [+] Directories OK
echo.

REM ---- 2. Database Check ----
echo [2/6] Checking Database...
if exist "daena.db" (
    echo   [+] Database found: daena.db
    attrib -R "daena.db" 2>nul
    if exist "daena.db-wal" del /F /Q "daena.db-wal" 2>nul
    if exist "daena.db-shm" del /F /Q "daena.db-shm" 2>nul
) else (
    echo   [WARN] No database found - will be created on first run
)
echo.

REM ---- 3. Check Python Environment (main or audio venv) ----
echo [3/6] Checking Python Environment...
set "VENV_BACKEND="
if exist "%ROOT%venv_daena_main_py310\Scripts\python.exe" (
    set "VENV_BACKEND=%ROOT%venv_daena_main_py310"
)
if not defined VENV_BACKEND if exist "%ROOT%venv_daena_audio_py310\Scripts\python.exe" (
    set "VENV_BACKEND=%ROOT%venv_daena_audio_py310"
    echo   [INFO] Using venv_daena_audio_py310 for backend (venv_daena_main_py310 not found)
)
if not defined VENV_BACKEND (
    echo   [ERROR] No Python venv found!
    echo   Create one: python -m venv venv_daena_main_py310
    echo   Then: venv_daena_main_py310\Scripts\pip.exe install -r requirements.txt
    echo.
    pause
    exit /b 1
)
echo   [+] Python environment: %VENV_BACKEND%
echo.

REM ---- 4. Start Ollama (MODELS_ROOT + GPU) ----
echo [4/6] Checking Ollama...
tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | findstr /I "ollama.exe" >nul
if %errorlevel%==0 (
    echo   [+] Ollama is already running
) else (
    echo   [*] Starting Ollama (MODELS_ROOT=%MODELS_ROOT%, GPU-friendly)...
    if not defined OLLAMA_NUM_GPU set "OLLAMA_NUM_GPU=1"
    if not defined OLLAMA_GPU_OVERHEAD set "OLLAMA_GPU_OVERHEAD=10"
    start "DAENA - OLLAMA" cmd /c "set OLLAMA_MODELS=%OLLAMA_MODELS% && set OLLAMA_NUM_GPU=%OLLAMA_NUM_GPU% && set OLLAMA_GPU_OVERHEAD=%OLLAMA_GPU_OVERHEAD% && ollama serve"
    timeout /t 3 /nobreak >nul
    echo   [+] Ollama started (daena brain: if this fails, backend will use fallback port 11435)
)
echo.

REM ---- 5. Start Backend ----
echo [5/6] Starting Backend Service...
echo   [*] Port: %BACKEND_PORT%
echo   [*] QA Guardian: %QA_GUARDIAN_ENABLED%
echo   [*] Command: python -m uvicorn backend.main:app --host 127.0.0.1 --port %BACKEND_PORT%
echo.

REM Start backend in a new window that stays open (with QA Guardian env vars)
start "DAENA - BACKEND" cmd /k "cd /d "%ROOT%" && set "PYTHONPATH=%ROOT%" && call "%VENV_BACKEND%\Scripts\activate.bat" && set DISABLE_AUTH=1 && set MODELS_ROOT=%MODELS_ROOT% && set OLLAMA_MODELS=%OLLAMA_MODELS% && set TTS_HOME=%TTS_HOME% && set QA_GUARDIAN_ENABLED=%QA_GUARDIAN_ENABLED% && set QA_GUARDIAN_AUTO_FIX=%QA_GUARDIAN_AUTO_FIX% && set QA_GUARDIAN_KILL_SWITCH=%QA_GUARDIAN_KILL_SWITCH% && set HF_HOME=%HF_HOME% && set TRANSFORMERS_CACHE=%TRANSFORMERS_CACHE% && python -m uvicorn backend.main:app --host 127.0.0.1 --port %BACKEND_PORT% --reload"

echo   [+] Backend window opened
echo.

REM ---- 5b. Start Audio Service (Voice/TTS/STT) ----
echo [5b/6] Starting Audio Service (XTTS Voice Cloning)...
echo   [*] Port: %AUDIO_PORT%
echo   [*] Using voice sample: daena_voice.wav
echo.

REM Check if audio venv exists
if exist "venv_daena_audio_py310\Scripts\python.exe" (
    start "DAENA - AUDIO" cmd /k "cd /d %ROOT% && call venv_daena_audio_py310\Scripts\activate.bat && python -m uvicorn audio.audio_service.main:app --host 127.0.0.1 --port %AUDIO_PORT%"
    echo   [+] Audio service window opened
) else (
    echo   [WARN] Audio venv not found - voice features disabled
    echo   [WARN] To enable voice: python -m venv venv_daena_audio_py310
    echo   [WARN] Then: venv_daena_audio_py310\Scripts\pip install -r requirements-audio.txt
)
echo.

REM ---- 6. Wait for Backend ----
echo [6/6] Waiting for Backend to be ready...
set /a COUNT=0

:WAIT_LOOP
set /a COUNT+=1
echo   [*] Attempt %COUNT%/30...

REM Try to connect to health endpoint
powershell -NoProfile -Command "try{$null=Invoke-WebRequest -UseBasicParsing 'http://127.0.0.1:%BACKEND_PORT%/health' -TimeoutSec 2;exit 0}catch{exit 1}" >nul 2>&1
if %errorlevel%==0 (
    echo   [+] Backend is ready!
    goto :READY
)

if %COUNT% GEQ 30 (
    echo.
    echo   [WARN] Backend did not respond after 30 attempts.
    echo   [WARN] Check the DAENA - BACKEND window for errors.
    echo.
    goto :READY
)

timeout /t 2 /nobreak >nul
goto :WAIT_LOOP

:READY
echo.
echo ============================================================
echo   DAENA STARTUP COMPLETE
echo ============================================================
echo.
echo   Main URLs:
echo   Backend URL:      http://127.0.0.1:%BACKEND_PORT%
echo   Dashboard:        http://127.0.0.1:%BACKEND_PORT%/ui/daena-office
echo   API Docs:         http://127.0.0.1:%BACKEND_PORT%/docs
echo.
echo   New Dashboards:
echo   Dashboard:        http://127.0.0.1:%BACKEND_PORT%/ui/dashboard
echo   Incident Room:    http://127.0.0.1:%BACKEND_PORT%/incident-room
echo   QA Guardian:      http://127.0.0.1:%BACKEND_PORT%/api/v1/qa/ui
echo   App Setup:        http://127.0.0.1:%BACKEND_PORT%/ui/app-setup
echo   CMP Canvas:       http://127.0.0.1:%BACKEND_PORT%/cmp-canvas
echo   Control Center:   http://127.0.0.1:%BACKEND_PORT%/control-center
echo   Voice Diagnostics: http://127.0.0.1:%BACKEND_PORT%/voice-diagnostics
echo.
echo   QA Guardian Status: %QA_GUARDIAN_ENABLED%
echo   Check the "DAENA - BACKEND" window for server logs.
echo.
echo ============================================================
echo.

REM Auto-launch Dashboard
echo   [+] Launching Dashboard...
start "" "http://127.0.0.1:%BACKEND_PORT%/ui/daena-office"

echo.
echo Press any key to close this launcher window...
echo (The backend will continue running in its own window)
pause >nul

