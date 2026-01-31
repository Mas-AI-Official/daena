@echo off
REM Smoke (API) + 5 manual UI verification steps. Backend must be running.
REM Set EXECUTION_TOKEN in env for execution-layer checks.
python "%~dp0smoke_and_manual_ui.py" %*
if %ERRORLEVEL% neq 0 exit /b %ERRORLEVEL%
REM Optional: also run control-plane smoke
call "%~dp0run_smoke_control_plane.bat" %*
exit /b %ERRORLEVEL%
