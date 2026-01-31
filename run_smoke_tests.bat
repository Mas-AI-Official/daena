@echo off
REM ============================================================================
REM Daena smoke tests launcher (project root)
REM Runs: 1) Provider smoke test  2) Control plane smoke (Execution + Proactive)
REM Backend must be running for control plane test (e.g. start backend first).
REM ============================================================================

cd /d "%~dp0"

echo.
echo [SMOKE 1/2] Running provider smoke test...
call scripts\run_provider_smoke_test.bat
set "EXIT1=%ERRORLEVEL%"
if %EXIT1% NEQ 0 (
    echo [SMOKE] Provider test failed. Skipping control plane test.
    exit /b %EXIT1%
)

echo.
echo [SMOKE 2/2] Running control plane smoke test (backend must be up)...
call scripts\run_smoke_control_plane.bat
set "EXIT2=%ERRORLEVEL%"
if %EXIT2% NEQ 0 exit /b %EXIT2%

exit /b 0
