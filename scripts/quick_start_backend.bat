@echo off
REM Preferred: use scripts\start_backend_with_env.bat (sets PYTHONPATH and EXECUTION_TOKEN).
call "%~dp0start_backend_with_env.bat" %*
exit /b %ERRORLEVEL%
