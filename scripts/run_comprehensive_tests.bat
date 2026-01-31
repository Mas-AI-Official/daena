@echo off
setlocal EnableExtensions
REM Run tests\test_comprehensive_suite.py. Backend must be running. For smoke + manual verification use scripts\run_manual_steps.bat.

set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"

set "PY_MAIN="
if exist "%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe" set "PY_MAIN=%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe"
if not defined PY_MAIN if exist "%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe" set "PY_MAIN=%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe"
if not defined PY_MAIN set "PY_MAIN=python"
"%PY_MAIN%" --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found
    exit /b 1
)

echo [INFO] Python: %PY_MAIN%
"%PY_MAIN%" -c "import urllib.request; urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8000/health'), timeout=2)" 2>nul
if errorlevel 1 (
    echo [WARNING] Backend not running. Start: scripts\start_backend_with_env.bat
)
echo.

REM Install test dependencies if needed
echo [INFO] Checking test dependencies...
"%PY_MAIN%" -c "import httpx; import pytest" 2>nul
if errorlevel 1 (
    echo [INFO] Installing test dependencies...
    "%PY_MAIN%" -m pip install httpx pytest --quiet
    if errorlevel 1 (
        echo [WARNING] Failed to install test dependencies
    )
    echo.
)

REM Run comprehensive test suite
echo [INFO] Running comprehensive test suite...
echo.
"%PY_MAIN%" tests\test_comprehensive_suite.py

if errorlevel 1 (
    echo SOME TESTS FAILED
    exit /b 1
)
echo ALL TESTS PASSED
exit /b 0




