@echo off
setlocal EnableDelayedExpansion

echo ==========================================
echo Starting Daena Audio Service
echo ==========================================
echo.

REM Change to script directory
cd /d "%~dp0"

REM Use the audio Python environment
echo [INFO] Activating audio Python environment...

if exist "venv_daena_audio_py310\Scripts\activate.bat" (
    call venv_daena_audio_py310\Scripts\activate.bat
    echo [OK] Activated: venv_daena_audio_py310
) else if exist "venv_daena_main_py310\Scripts\activate.bat" (
    echo [WARNING] Audio env not found, using main env
    call venv_daena_main_py310\Scripts\activate.bat
    echo [OK] Activated: venv_daena_main_py310
) else (
    echo [ERROR] No virtual environment found!
    echo [INFO] Expected: venv_daena_audio_py310 or venv_daena_main_py310
    pause
    exit /b 1
)

python --version
echo.

REM Check if audio service exists
if not exist "audio\audio_service.py" (
    echo [WARNING] Audio service not found at audio\audio_service.py
    echo [INFO] Looking for alternative audio scripts...
    dir /b audio\*.py 2>nul
)

echo.
echo ==========================================
echo Audio Service Starting
echo ==========================================
echo.

REM Try to start audio service
if exist "audio\audio_service.py" (
    python audio\audio_service.py
) else if exist "audio\main.py" (
    python audio\main.py
) else (
    echo [INFO] No audio service to start
    echo [INFO] Place audio service in 'audio\audio_service.py'
    pause
)

if errorlevel 1 (
    echo.
    echo [ERROR] Audio service crashed!
    pause
)

echo.
echo Audio service stopped.
pause
