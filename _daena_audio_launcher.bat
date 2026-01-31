@echo off

REM Helper launcher for DAENA audio service - avoids nested quotes when started from START_DAENA.bat

setlocal EnableExtensions



set "ROOT=%~dp0"

if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"



cd /d "%ROOT%"

if errorlevel 1 (

    echo [ERROR] Cannot cd to %ROOT%

    pause

    exit /b 1

)



set "AUDIO_PORT=%~1"

if "%AUDIO_PORT%"=="" set "AUDIO_PORT=5001"



if not exist "%ROOT%\venv_daena_audio_py310\Scripts\python.exe" (

    echo [ERROR] Audio venv not found: %ROOT%\venv_daena_audio_py310

    pause

    exit /b 1

)



call "%ROOT%\venv_daena_audio_py310\Scripts\activate.bat"

echo [DAENA AUDIO] Port: %AUDIO_PORT%

python -m uvicorn audio.audio_service.main:app --host 127.0.0.1 --port %AUDIO_PORT%

echo.

pause >nul

