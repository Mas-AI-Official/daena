@echo off
setlocal
set "ROOT=%~dp0.."
cd /d "%ROOT%"

echo [INFO] Checking for Audio Venv...
if not exist "venv_daena_audio_py310\Scripts\activate.bat" (
    echo [ERROR] Audio venv not found. Please run scripts\install_voice_dependencies.bat first.
    pause
    exit /b 1
)

echo [INFO] Activating Audio Venv...
call venv_daena_audio_py310\Scripts\activate.bat

echo [INFO] Downloading Voice Models (XTTS-v2 and Faster-Whisper)...
python scripts\download_models.py

echo.
echo [SUCCESS] Models downloaded.
pause
