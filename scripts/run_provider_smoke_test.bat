@echo off
REM ============================================================================
REM Provider (Moltbot-style) smoke test
REM Verifies: ToolRequest from mock message, denial when disabled/not in allowlist,
REM           health_check submit, approval mode.
REM Requires: venv with requirements.txt (httpx, pytest, pytest-asyncio)
REM ============================================================================

setlocal EnableExtensions
set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"

echo.
echo ============================================================================
echo PROVIDER SMOKE TEST
echo ============================================================================
echo.

set "PY="
if exist "%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe" set "PY=%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe"
if not defined PY if exist "%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe" set "PY=%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe"
if not defined PY set "PY=python"

echo [INFO] Python: %PY%
"%PY%" --version
echo.

echo [STEP 1] Installing test deps if needed...
"%PY%" -m pip install pytest pytest-asyncio httpx --quiet
echo.

echo [STEP 2] Running provider smoke tests...
set "PYTHONPATH=%PROJECT_ROOT%;%PROJECT_ROOT%\backend"
REM Use writable temp dir for pytest cache (avoids Permission denied on .pytest_cache)
if not defined TEMP set "TEMP=%TMP%"
if not defined TEMP set "TEMP=%USERPROFILE%"
set "PYTEST_CACHE_DIR=%TEMP%\daena_pytest_cache"
"%PY%" -m pytest "%PROJECT_ROOT%\tests\test_provider_tool_request_smoke.py" -v -s
set "EXIT_CODE=%ERRORLEVEL%"
echo.

if %EXIT_CODE% EQU 0 (
    echo ============================================================================
    echo   PROVIDER SMOKE TEST PASSED
    echo ============================================================================
) else (
    echo ============================================================================
    echo   PROVIDER SMOKE TEST FAILED (exit %EXIT_CODE%)
    echo ============================================================================
)

echo.
pause
exit /b %EXIT_CODE%
