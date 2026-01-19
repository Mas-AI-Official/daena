@echo off
setlocal EnableExtensions EnableDelayedExpansion
set "PROJECT_ROOT=%~dp0..\"
cd /d "%PROJECT_ROOT%"

if not exist "logs" mkdir "logs"
for /f "delims=" %%I in ('powershell -NoProfile -Command "Get-Date -Format yyyyMMdd_HHmmss"') do set "TS=%%I"
set "VOICE_LOG=%PROJECT_ROOT%logs\voice_%TS%.log"

REM Choose your voice env folder name:
set "VOICE_VENV=%PROJECT_ROOT%venv_daena_audio_py310"
set "PY_VOICE=%VOICE_VENV%\Scripts\python.exe"

if not exist "%VOICE_VENV%\Scripts\activate.bat" (
  echo [INFO] Creating voice venv...
  py -3.10 -m venv "%VOICE_VENV%" >> "%VOICE_LOG%" 2>&1
)

call "%VOICE_VENV%\Scripts\activate.bat" >> "%VOICE_LOG%" 2>&1

REM Install voice deps if you have a voice requirements file
if exist "requirements_voice.txt" (
  echo [INFO] Installing voice requirements...
  "%PY_VOICE%" -m pip install -r "requirements_voice.txt" >> "%VOICE_LOG%" 2>&1
) else (
  echo [WARNING] requirements_voice.txt not found (skipping)
)

echo [OK] Voice env ready. Log: %VOICE_LOG%
pause
