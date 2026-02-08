@echo off
setlocal EnableDelayedExpansion
title Daena Audio Service

echo ==========================================
echo   Starting Daena Audio Service
echo ==========================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Use the audio Python environment
echo [INFO] Activating audio Python environment...

set "VENV_AUDIO="
if exist "venv_daena_audio_py310\Scripts\activate.bat" (
    set "VENV_AUDIO=venv_daena_audio_py310"
    echo [OK] Found: venv_daena_audio_py310
    goto :activate_env
)
if exist "venv_daena_main_py310\Scripts\activate.bat" (
    set "VENV_AUDIO=venv_daena_main_py310"
    echo [WARNING] Audio env not found, using main env
    goto :activate_env
)
echo [ERROR] No virtual environment found!
echo [INFO] Expected: venv_daena_audio_py310 or venv_daena_main_py310
pause
exit /b 1

:activate_env
call "%VENV_AUDIO%\Scripts\activate.bat"
echo [OK] Activated: %VENV_AUDIO%

python --version
echo.

REM Check if audio service exists
if not exist "audio" (
    echo [INFO] Audio directory not found
    echo [INFO] Creating audio directory...
    mkdir audio
)

echo ==========================================
echo   Audio Service Starting
echo ==========================================
echo.

REM Try to start audio service with various entry points
if exist "audio\audio_service\main.py" (
    echo [INFO] Starting audio_service.main...
    python -m uvicorn audio.audio_service.main:app --host 127.0.0.1 --port 5001
    goto :check_exit
)
if exist "audio\main.py" (
    echo [INFO] Starting audio.main...
    python audio\main.py
    goto :check_exit
)
if exist "audio\audio_service.py" (
    echo [INFO] Starting audio_service.py...
    python audio\audio_service.py
    goto :check_exit
)

echo [INFO] No audio service entry point found
echo [INFO] Place audio service in one of:
echo        - audio\audio_service\main.py
echo        - audio\main.py
echo        - audio\audio_service.py
pause
exit /b 0

:check_exit
if errorlevel 1 (
    echo.
    echo [ERROR] Audio service crashed!
    pause
)

echo.
echo Audio service stopped.
pause
