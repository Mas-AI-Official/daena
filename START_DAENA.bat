@echo off
REM ============================================================
REM DAENA AI VP - MASTER LAUNCHER
REM ============================================================
REM When double-clicked, re-launch in a window that stays open (cmd /k)

if "%~1"=="" (
    title DAENA Launcher
    cmd /k "%~f0" keepopen
    exit /b 0
)

REM Go to script directory so all paths work
cd /d "%~dp0"
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

echo ============================================================
echo   DAENA LAUNCHER
echo   Date: %DATE% %TIME%
echo ============================================================
echo.
echo [INFO] Root: %ROOT%
echo.

REM ---- Environment Configuration ----
set "BACKEND_PORT=8000"
set "AUDIO_PORT=5001"
echo [INFO] Port: %BACKEND_PORT%
set "DISABLE_AUTH=1"
set "ENVIRONMENT=development"

REM -- BUG FIXES & CONFIGURATION --
set "PYTHONPATH=%ROOT%"
if exist "%ROOT%\venv_daena_main_py310\Lib\site-packages\playwright" set "PLAYWRIGHT_BROWSERS_PATH=%ROOT%\venv_daena_main_py310\Lib\site-packages\playwright\driver\package\.local-browsers"
set "OLLAMA_HOST=http://127.0.0.1:11434"
set "DAENA_CREATOR=Masoud"
set "DEFAULT_MODEL=deepseek-r1:8b"
set "ENABLE_LOCAL_ROUTER=true"

REM -- QA GUARDIAN CONFIGURATION (NEW) --
set "QA_GUARDIAN_ENABLED=true"
set "QA_GUARDIAN_AUTO_FIX=false"
set "QA_GUARDIAN_KILL_SWITCH=false"
set "QA_GUARDIAN_LOG_LEVEL=INFO"

REM -- EXECUTION LAYER (Skills, Tasks, Approvals): set EXECUTION_TOKEN for API + dashboard --
REM set "EXECUTION_TOKEN=your-secret-token"

REM -- HANDS (OpenClaw Gateway): preferred DAENABOT_HANDS_*; legacy OPENCLAW_GATEWAY_* --
REM set "DAENABOT_HANDS_URL=ws://127.0.0.1:18789/ws"
REM set "DAENABOT_HANDS_TOKEN=your-token"
REM set "DAENA_SKILL_IMPORT_PATH=%ROOT%\docs\2026-01-31\new files"

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
if exist "%ROOT%\venv_daena_main_py310\Scripts\python.exe" (
    set "VENV_BACKEND=%ROOT%\venv_daena_main_py310"
)
if not defined VENV_BACKEND if exist "%ROOT%\venv_daena_audio_py310\Scripts\python.exe" (
    set "VENV_BACKEND=%ROOT%\venv_daena_audio_py310"
    echo   [INFO] Using venv_daena_audio_py310 for backend (venv_daena_main_py310 not found)
)
if not defined VENV_BACKEND (
    echo   [ERROR] No Python venv found in: %ROOT%
    echo   We look for: venv_daena_main_py310 OR venv_daena_audio_py310
    echo   Create one: python -m venv venv_daena_main_py310
    echo   Then: venv_daena_main_py310\Scripts\pip.exe install -r backend\requirements.txt
    echo.
    pause
    exit /b 1
)
echo   [+] Python environment: %VENV_BACKEND%
echo.

REM ---- 4. Start Ollama (MODELS_ROOT + GPU) ----
echo [4/6] Checking Ollama...
tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | findstr /I "ollama.exe" >nul
if errorlevel 1 goto :START_OLLAMA
echo   [+] Ollama is already running
goto :OLLAMA_DONE
:START_OLLAMA
echo   [*] Starting Ollama - MODELS_ROOT=%MODELS_ROOT% - GPU-friendly
if not defined OLLAMA_NUM_GPU set "OLLAMA_NUM_GPU=1"
if not defined OLLAMA_GPU_OVERHEAD set "OLLAMA_GPU_OVERHEAD=10"
start "DAENA - OLLAMA" cmd /c "set OLLAMA_MODELS=%OLLAMA_MODELS% && set OLLAMA_NUM_GPU=%OLLAMA_NUM_GPU% && set OLLAMA_GPU_OVERHEAD=%OLLAMA_GPU_OVERHEAD% && ollama serve"
timeout /t 3 /nobreak >nul
echo   [+] Ollama started - backend will use fallback port 11435 if needed
:OLLAMA_DONE
echo.

REM ---- 5. Start Backend ----
echo [5/6] Starting Backend Service...
echo   [*] Port: %BACKEND_PORT%
echo   [*] QA Guardian: %QA_GUARDIAN_ENABLED%
echo   [*] Command: python -m uvicorn backend.main:app --host 127.0.0.1 --port %BACKEND_PORT%
echo.

REM Start backend in a new window that stays open (with QA Guardian env vars)
start "DAENA - BACKEND" cmd /k call "%~dp0_daena_backend_launcher.bat" %BACKEND_PORT%

echo   [+] Backend window opened
echo.

REM ---- 5b. Start Audio Service (Voice/TTS/STT) ----
echo [5b/6] Starting Audio Service (XTTS Voice Cloning)...
echo   [*] Port: %AUDIO_PORT%
echo   [*] Using voice sample: daena_voice.wav
echo.

REM Check if audio venv exists
if exist "%~dp0venv_daena_audio_py310\Scripts\python.exe" (
    start "DAENA - AUDIO" cmd /k call "%~dp0_daena_audio_launcher.bat" %AUDIO_PORT%
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
echo   Backend:          http://127.0.0.1:%BACKEND_PORT%
echo   Daena Office:     http://127.0.0.1:%BACKEND_PORT%/ui/daena-office
echo   API Docs:         http://127.0.0.1:%BACKEND_PORT%/docs
echo.
echo   Sidebar (VP):
echo   Dashboard:        http://127.0.0.1:%BACKEND_PORT%/ui/dashboard
echo   Daena Office:     http://127.0.0.1:%BACKEND_PORT%/ui/daena-office
echo   Projects:         http://127.0.0.1:%BACKEND_PORT%/ui/projects
echo   Councils:         http://127.0.0.1:%BACKEND_PORT%/ui/councils
echo   Workspace:        http://127.0.0.1:%BACKEND_PORT%/ui/workspace
echo   Analytics:        http://127.0.0.1:%BACKEND_PORT%/ui/analytics
echo   Agents:           http://127.0.0.1:%BACKEND_PORT%/ui/agents
echo   Control Panel:    http://127.0.0.1:%BACKEND_PORT%/ui/control-panel
echo   Brain ^& API:     http://127.0.0.1:%BACKEND_PORT%/ui/brain-settings
echo   Web3 / DeFi:      http://127.0.0.1:%BACKEND_PORT%/ui/web3
echo   Founder:         http://127.0.0.1:%BACKEND_PORT%/ui/founder-panel
echo.
echo   Other:
echo   QA Guardian:      http://127.0.0.1:%BACKEND_PORT%/api/v1/qa/ui
echo   Incident Room:    http://127.0.0.1:%BACKEND_PORT%/ui/incident-room
echo   Wiring audit:     http://127.0.0.1:%BACKEND_PORT%/api/v1/ui/wiring-audit
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

