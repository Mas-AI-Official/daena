@echo off
REM ============================================================================
REM Run Comprehensive Test Suite
REM ============================================================================
REM This script runs the comprehensive test suite for Daena AI VP System
REM ============================================================================

setlocal EnableExtensions
setlocal EnableDelayedExpansion

REM UTF-8 console
chcp 65001 >nul 2>&1

set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"

echo ============================================================================
echo COMPREHENSIVE TEST SUITE - DAENA AI VP SYSTEM
echo ============================================================================
echo.

REM Find Python executable
set "PY_MAIN=%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe"
if not exist "%PY_MAIN%" (
    echo [WARNING] venv Python not found, using system Python
    set "PY_MAIN=python"
    "%PY_MAIN%" --version >nul 2>&1
    if errorlevel 1 (
        echo FATAL ERROR: Python not found
        pause
        exit /b 1
    )
)

echo [INFO] Using Python: %PY_MAIN%
"%PY_MAIN%" --version
echo.

REM Check if backend is running
echo [INFO] Checking if backend is running...
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/api/v1/health/' -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop; exit 0 } catch { exit 1 }" 2>nul
if errorlevel 1 (
    echo [WARNING] Backend does not appear to be running
    echo [INFO] Please start the backend first using START_DAENA.bat
    echo [INFO] Continuing anyway - some tests may fail
    echo.
)

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
    echo.
    echo ============================================================================
    echo SOME TESTS FAILED
    echo ============================================================================
    echo.
    echo Check the output above for details.
    pause
    exit /b 1
) else (
    echo.
    echo ============================================================================
    echo ALL TESTS PASSED
    echo ============================================================================
    echo.
)

pause
exit /b 0




