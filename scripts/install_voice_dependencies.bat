@echo off
REM ============================================================================
REM Install Voice Dependencies Script
REM ============================================================================
REM This script installs all voice-related dependencies in the voice environment
REM ============================================================================

setlocal EnableExtensions
setlocal EnableDelayedExpansion

REM UTF-8 console (use proper error handling)
chcp 65001 >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Failed to set UTF-8 encoding
)

REM Get project root - handle being called from parent script
if defined PROJECT_ROOT (
    REM Already set by parent script - use as-is
    REM Ensure we're in project root
    cd /d "%PROJECT_ROOT%" 2>nul
) else (
    REM Calculate from script location
    set "SCRIPT_DIR=%~dp0"
    REM Remove trailing backslash if present
    if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
    REM Go up one level
    for %%I in ("%SCRIPT_DIR%\..") do set "PROJECT_ROOT=%%~fI"
    REM Navigate to project root
    if defined PROJECT_ROOT (
        cd /d "%PROJECT_ROOT%" 2>nul
    )
)

echo ============================================================================
echo Installing Voice Dependencies
echo ============================================================================
echo Project Root: %PROJECT_ROOT%
echo.

REM Find voice environment
set "VOICE_VENV=%PROJECT_ROOT%\venv_daena_audio_py310"
if not exist "%VOICE_VENV%" (
    echo [INFO] Creating voice virtual environment...
    if exist "%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe" (
        "%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe" -m venv "%VOICE_VENV%"
    ) else (
        python -m venv "%VOICE_VENV%"
    )
    if errorlevel 1 (
        echo [WARNING] Failed to create voice virtual environment - continuing anyway
        echo [INFO] Voice features will be limited
        goto :VOICE_SKIP
    )
    echo [OK] Voice virtual environment created
    echo.
)

REM Find Python executable in voice environment
set "PY_VOICE=%VOICE_VENV%\Scripts\python.exe"
if not exist "%PY_VOICE%" (
    echo [WARNING] Voice environment Python not found at: %PY_VOICE%
    echo [INFO] Voice features will be limited
    goto :VOICE_SKIP
)

echo [INFO] Using Voice Python: %PY_VOICE%
"%PY_VOICE%" --version
if errorlevel 1 (
    echo [WARNING] Voice Python not working - continuing anyway
    goto :VOICE_SKIP
)
echo.

REM Activate voice venv (only if running standalone, not when called from parent)
REM When called from parent, we use PY_VOICE directly, so activation is not needed
if not defined PROJECT_ROOT (
    REM Running standalone - activate environment
    echo [INFO] Activating voice virtual environment...
    call "%VOICE_VENV%\Scripts\activate.bat"
    if errorlevel 1 (
        echo [WARNING] Failed to activate voice virtual environment - continuing anyway
        echo [INFO] Voice features will be limited
        goto :VOICE_SKIP
    )
    echo [OK] Voice virtual environment activated
    echo.
) else (
    REM Called from parent - skip activation, use PY_VOICE directly
    echo [INFO] Using voice Python directly (called from parent script)
    echo.
)

REM Upgrade pip
echo [INFO] Upgrading pip...
"%PY_VOICE%" -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo [WARNING] Failed to upgrade pip - continuing anyway
)
echo.

REM Install from requirements-audio.txt if it exists
if exist "%PROJECT_ROOT%\requirements-audio.txt" (
    echo [INFO] Installing from requirements-audio.txt...
    "%PY_VOICE%" -m pip install -r "%PROJECT_ROOT%\requirements-audio.txt"
    if errorlevel 1 (
        echo [WARNING] Some packages from requirements-audio.txt failed to install
    ) else (
        echo [OK] Requirements from requirements-audio.txt installed
    )
    echo.
) else (
    echo [WARNING] requirements-audio.txt not found at %PROJECT_ROOT%\requirements-audio.txt
    echo [INFO] Will install critical packages manually
    echo.
)

REM Install critical voice dependencies
echo [INFO] Installing critical voice dependencies...
echo.

REM 1. aiohttp (for voice cloning/ElevenLabs API)
echo [1/4] Installing aiohttp...
"%PY_VOICE%" -m pip install "aiohttp>=3.9.0,<4.0.0"
if errorlevel 1 (
    echo [WARNING] Failed to install aiohttp
) else (
    echo [OK] aiohttp installed
)
echo.

REM 2. SpeechRecognition
echo [2/4] Installing SpeechRecognition...
"%PY_VOICE%" -m pip install "SpeechRecognition>=3.10.0"
if errorlevel 1 (
    echo [WARNING] Failed to install SpeechRecognition
) else (
    echo [OK] SpeechRecognition installed
)
echo.

REM 3. PyAudio (may require special handling on Windows)
echo [3/4] Installing PyAudio...
echo [INFO] Note: PyAudio may require Visual C++ Build Tools on Windows
"%PY_VOICE%" -m pip install pyaudio
if errorlevel 1 (
    echo [WARNING] PyAudio installation failed - trying alternative method...
    echo [INFO] Attempting to install via pipwin...
    "%PY_VOICE%" -m pip install pipwin
    if not errorlevel 1 (
        "%PY_VOICE%" -m pipwin install pyaudio
        if errorlevel 1 (
            echo [WARNING] PyAudio installation failed - you may need to install manually
            echo [INFO] Download wheel from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
        ) else (
            echo [OK] PyAudio installed via pipwin
        )
    ) else (
        echo [WARNING] pipwin not available - PyAudio installation skipped
        echo [INFO] Install manually: pip install pipwin && pipwin install pyaudio
    )
) else (
    echo [OK] PyAudio installed
)
echo.

REM 4. pvporcupine (for wake word detection)
echo [4/4] Installing pvporcupine...
"%PY_VOICE%" -m pip install "pvporcupine>=3.0.0"
if errorlevel 1 (
    echo [WARNING] pvporcupine installation failed
    echo [INFO] Note: pvporcupine requires an access key from Picovoice
    echo [INFO] You can continue without it - wake word detection will be disabled
) else (
    echo [OK] pvporcupine installed
)
echo.

REM Verify installations
echo [INFO] Verifying voice dependencies...
echo.

set "VERIFY_ERROR=0"

"%PY_VOICE%" -c "import aiohttp; print('aiohttp OK')" 2>nul
if errorlevel 1 (
    echo [WARNING] aiohttp NOT available
    set "VERIFY_ERROR=1"
) else (
    echo [OK] aiohttp available
)

"%PY_VOICE%" -c "import speech_recognition; print('SpeechRecognition OK')" 2>nul
if errorlevel 1 (
    echo [WARNING] SpeechRecognition NOT available
    set "VERIFY_ERROR=1"
) else (
    echo [OK] SpeechRecognition available
)

"%PY_VOICE%" -c "import pyaudio; print('PyAudio OK')" 2>nul
if errorlevel 1 (
    echo [WARNING] PyAudio NOT available (optional - may need manual installation)
    echo [INFO] PyAudio is optional - speech recognition may work without it
) else (
    echo [OK] PyAudio available
)

"%PY_VOICE%" -c "import pvporcupine; print('pvporcupine OK')" 2>nul
if errorlevel 1 (
    echo [WARNING] pvporcupine NOT available (optional - wake word detection disabled)
    echo [INFO] pvporcupine is optional - requires Picovoice access key
) else (
    echo [OK] pvporcupine available
)

echo.
echo ============================================================================
echo Voice dependencies installation complete
echo ============================================================================
echo.

REM Download Voice Models
echo [INFO] Downloading Voice Models...
"%PY_VOICE%" "%PROJECT_ROOT%\scripts\download_models.py"
if errorlevel 1 (
    echo [WARNING] Model download failed - you may need to run scripts\download_voice_models.bat manually
) else (
    echo [OK] Voice models downloaded
)
echo.
if defined VOICE_VENV (
    echo [INFO] Voice environment: %VOICE_VENV%
    echo [INFO] To activate manually: call "%VOICE_VENV%\Scripts\activate.bat"
) else (
    echo [INFO] Voice environment setup skipped
)
echo.

:VOICE_SKIP
REM Always exit with success (0) - optional packages don't cause failure
REM Critical packages (aiohttp, SpeechRecognition) should be installed
REM Optional packages (pyaudio, pvporcupine) are nice-to-have

REM Only pause if running standalone (not when called from parent)
if not defined PROJECT_ROOT (
    pause
)
exit /b 0

