@echo off
title DAENA - AUDIO (XTTS)
REM ============================================================
REM Helper script called by START_DAENA.bat
REM Starts XTTS server for voice cloning
REM ============================================================

set PORT=%1
if "%PORT%"=="" set PORT=5001

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
if not defined MODELS_ROOT set "MODELS_ROOT=D:\Ideas\MODELS_ROOT"
set "TTS_HOME=%MODELS_ROOT%\xtts"

echo [AUDIO] Activating Audio Environment...
if exist "venv_daena_audio_py310\Scripts\python.exe" (
    set "VENV_PYTHON=venv_daena_audio_py310\Scripts\python.exe"
) else (
    echo [ERROR] Audio venv not found.
    pause
    exit /b 1
)

echo [AUDIO] Starting XTTS Server on Port %PORT%...
echo [AUDIO] Home: %TTS_HOME%

REM Check if TTS module exists
"%VENV_PYTHON%" -c "import TTS" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] TTS module not found in audio venv.
    echo Please run: venv_daena_audio_py310\Scripts\pip install -r requirements-audio.txt
    pause
    exit /b 1
)

REM Run Server
"%VENV_PYTHON%" -m TTS.server.server --model_path "%TTS_HOME%" --config_path "%TTS_HOME%\config.json" --port %PORT% --use_cuda true

if %errorlevel% neq 0 (
    echo [ERROR] Audio Service Failed to start.
    echo Trying without config.json...
    "%VENV_PYTHON%" -m TTS.server.server --model_path "%TTS_HOME%" --port %PORT% --use_cuda true
)

if %errorlevel% neq 0 (
    echo [ERROR] Audio Service Crashed.
    pause
)
