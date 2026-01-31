@echo off
REM Starts backend and runs comprehensive_test_all_phases.py. Prefer scripts\run_all_tests_and_backend.bat for the same flow.
call "%~dp0run_all_tests_and_backend.bat" %*
exit /b %ERRORLEVEL%
