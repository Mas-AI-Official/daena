@echo off
REM ============================================================================
REM Install Dependencies Script
REM ============================================================================
REM This script installs all required Python packages
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
    REM Already set by parent script
) else (
    REM Calculate from script location
    set "PROJECT_ROOT=%~dp0.."
    REM Normalize path
    for %%I in ("%PROJECT_ROOT%") do set "PROJECT_ROOT=%%~fI"
)
cd /d "%PROJECT_ROOT%"

echo ============================================================================
echo Installing Dependencies
echo ============================================================================
echo Project Root: %PROJECT_ROOT%
echo.

REM Find Python executable - use parent's PY_MAIN if available
if not defined PY_MAIN (
    set "PY_MAIN=%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe"
    if not exist "%PY_MAIN%" (
        echo [WARNING] venv Python not found, using system Python
        set "PY_MAIN=python"
        "%PY_MAIN%" --version >nul 2>&1
        if errorlevel 1 (
            echo FATAL ERROR: Python not found
            echo Please install Python 3.10 or later
            pause
            exit /b 1
        )
    )
)

echo [INFO] Using Python: %PY_MAIN%
"%PY_MAIN%" --version
echo.

REM Check if venv exists, if not create it
if not exist "%PROJECT_ROOT%\venv_daena_main_py310" (
    echo [INFO] Creating virtual environment...
    "%PY_MAIN%" -m venv "%PROJECT_ROOT%\venv_daena_main_py310"
    if errorlevel 1 (
        echo FATAL ERROR: Failed to create virtual environment
        pause
        exit /b 1
    )
    echo [OK] Virtual environment created
    echo.
)

REM Activate venv
echo [INFO] Activating virtual environment...
call "%PROJECT_ROOT%\venv_daena_main_py310\Scripts\activate.bat"
if errorlevel 1 (
    echo FATAL ERROR: Failed to activate virtual environment
    pause
    exit /b 1
)
echo [OK] Virtual environment activated
echo.

REM Upgrade pip
echo [INFO] Upgrading pip...
"%PY_MAIN%" -m pip install --upgrade pip --quiet
if errorlevel 1 (
    echo [WARNING] Failed to upgrade pip - continuing anyway
)
echo.

REM Install requirements
echo [INFO] Installing requirements from requirements.txt...
if exist "%PROJECT_ROOT%\requirements.txt" (
    "%PY_MAIN%" -m pip install -r "%PROJECT_ROOT%\requirements.txt"
    if errorlevel 1 (
        echo FATAL ERROR: Failed to install requirements
        pause
        exit /b 1
    )
    echo [OK] Requirements installed
) else (
    echo FATAL ERROR: requirements.txt not found
    pause
    exit /b 1
)
echo.

REM Verify critical packages (use ASCII only to avoid encoding issues)
echo [INFO] Verifying critical packages...
"%PY_MAIN%" -c "import fastapi; print('fastapi OK')" 2>nul
if errorlevel 1 (
    echo [WARNING] fastapi not found
) else (
    echo [OK] fastapi verified
)
"%PY_MAIN%" -c "import uvicorn; print('uvicorn OK')" 2>nul
if errorlevel 1 (
    echo [WARNING] uvicorn not found
) else (
    echo [OK] uvicorn verified
)
"%PY_MAIN%" -c "import cryptography; print('cryptography OK')" 2>nul
if errorlevel 1 (
    echo [WARNING] cryptography not found
) else (
    echo [OK] cryptography verified
)

REM Note: Voice packages (aiohttp, SpeechRecognition, pvporcupine, pyaudio) 
REM are installed in the audio environment (venv_daena_audio_py310)
REM They will be verified during voice environment setup
echo [INFO] Voice packages will be installed in audio environment
echo [INFO] Run: scripts\install_voice_dependencies.bat

echo.
echo ============================================================================
echo Dependencies installation complete
echo ============================================================================
echo.
echo [OK] Critical dependencies installed successfully
echo [INFO] Some optional packages may be missing (see warnings above)
echo.

REM Only pause if running standalone (not when called from parent)
if not defined PROJECT_ROOT (
    pause
)
exit /b 0

