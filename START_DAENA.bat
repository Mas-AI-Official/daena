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
echo [INFO] Finding available port...
for /f "delims=" %%a in ('powershell -Command "$p=8000; while($true){try{$l=New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Loopback,$p); $l.Start(); $l.Stop(); break}catch{$p++}}; Write-Output $p"') do set BACKEND_PORT=%%a
echo [INFO] Using Port: %BACKEND_PORT%
set "AUDIO_PORT=5001"
set "DISABLE_AUTH=1"
set "ENVIRONMENT=development"

REM -- BUG FIXES & CONFIGURATION --
set "PYTHONPATH=%ROOT%"
set "PLAYWRIGHT_BROWSERS_PATH=%ROOT%venv_daena_main_py310\Lib\site-packages\playwright\driver\package\.local-browsers"
set "OLLAMA_HOST=http://127.0.0.1:11434"
set "DAENA_CREATOR=Masoud"
set "DEFAULT_MODEL=deepseek-r1:8b"
set "ENABLE_LOCAL_ROUTER=true"

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

REM ---- 3. Check Python Environment ----
echo [3/6] Checking Python Environment...
if not exist "venv_daena_main_py310\Scripts\python.exe" (
    echo   [ERROR] Python environment not found!
    echo   Expected: venv_daena_main_py310\Scripts\python.exe
    echo.
    echo   Please run: python -m venv venv_daena_main_py310
    echo   Then: venv_daena_main_py310\Scripts\pip.exe install -r requirements.txt
    echo.
    pause
    exit /b 1
)
echo   [+] Python environment found
echo.

REM ---- 4. Start Ollama ----
echo [4/6] Checking Ollama...
tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | findstr /I "ollama.exe" >nul
if %errorlevel%==0 (
    echo   [+] Ollama is already running
) else (
    echo   [*] Starting Ollama...
    start "DAENA - OLLAMA" cmd /c "ollama serve"
    timeout /t 3 /nobreak >nul
    echo   [+] Ollama started
)
echo.

REM ---- 5. Start Backend ----
echo [5/6] Starting Backend Service...
echo   [*] Port: %BACKEND_PORT%
echo   [*] Command: python -m uvicorn backend.main:app --host 127.0.0.1 --port %BACKEND_PORT%
echo.

REM Start backend in a new window that stays open
start "DAENA - BACKEND" cmd /k "cd /d %ROOT% && call venv_daena_main_py310\Scripts\activate.bat && set DISABLE_AUTH=1 && python -m uvicorn backend.main:app --host 127.0.0.1 --port %BACKEND_PORT% --reload"

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
echo   Backend URL: http://127.0.0.1:%BACKEND_PORT%
echo   Dashboard:   http://127.0.0.1:%BACKEND_PORT%/ui/daena-office
echo   API Docs:    http://127.0.0.1:%BACKEND_PORT%/docs
echo.
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
