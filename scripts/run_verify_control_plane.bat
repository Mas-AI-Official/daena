@echo off
REM Run automated API + UI checks. Backend must be at http://localhost:8000
setlocal
set "ROOT=%~dp0.."
cd /d "%ROOT%"
if not defined PYTHONPATH set "PYTHONPATH=%ROOT%"
set "PY=%ROOT%\venv_daena_audio_py310\Scripts\python.exe"
if not exist "%PY%" set "PY=python"
echo Running verification (health, capabilities, ping-hands, control-panel, command-center)...
"%PY%" "%ROOT%\scripts\verify_control_plane_and_api.py"
exit /b %ERRORLEVEL%
