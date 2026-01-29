@echo off
title Daena - XTTS Server (MODELS_ROOT)
color 0D

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
if not defined MODELS_ROOT set "MODELS_ROOT=D:\Ideas\MODELS_ROOT"
set "TTS_HOME=%MODELS_ROOT%\xtts"
set "XTTS_PATH=%TTS_HOME%"
set "COQUI_TOS_AGREED=1"
set "TORCHAUDIO_BACKEND=soundfile"

echo ========================================
echo   Daena XTTS Server (MODELS_ROOT)
echo ========================================
echo   MODELS_ROOT: %MODELS_ROOT%
echo   TTS_HOME:    %TTS_HOME%
echo ========================================
echo.

REM Prefer audio venv if present
if exist "%ROOT%\venv_daena_audio_py310\Scripts\python.exe" (
    set "VENV_PYTHON=%ROOT%\venv_daena_audio_py310\Scripts\python.exe"
) else if exist "%ROOT%\venv_daena_main_py310\Scripts\python.exe" (
    set "VENV_PYTHON=%ROOT%\venv_daena_main_py310\Scripts\python.exe"
) else (
    set "VENV_PYTHON=python"
)

echo [1/2] Checking TTS...
"%VENV_PYTHON%" -c "import TTS" >nul 2>&1
if %errorlevel% neq 0 (
    echo TTS not found. Install with: pip install TTS
    pause
    exit /b 1
)
echo TTS OK.
echo.

echo [2/2] Starting XTTS Server on port 8020...
echo.
if exist "%XTTS_PATH%\config.json" (
    "%VENV_PYTHON%" -m TTS.server.server --model_path "%XTTS_PATH%" --config_path "%XTTS_PATH%\config.json" --port 8020 --use_cuda false
) else (
    "%VENV_PYTHON%" -m TTS.server.server --model_path "%XTTS_PATH%" --port 8020 --use_cuda false
)
if %errorlevel% neq 0 (
    echo Server stopped with error.
    pause
)
exit /b 0
