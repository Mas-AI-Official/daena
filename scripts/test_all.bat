@echo off
REM Starts backend and runs comprehensive tests. For smoke + manual verification use scripts\run_manual_steps.bat (backend must be running).
call "%~dp0run_all_tests_and_backend.bat" %*
exit /b %ERRORLEVEL%
