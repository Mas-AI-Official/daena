@echo off
REM ============================================================================
REM Setup Ollama Models in local_brain Directory
REM ============================================================================
REM This script sets the OLLAMA_MODELS environment variable and restarts Ollama
REM ============================================================================

setlocal enabledelayedexpansion

set "PROJECT_ROOT=%~dp0.."
set "MODELS_PATH=%PROJECT_ROOT%\local_brain"

echo ============================================================================
echo Setting up Ollama Models Path
echo ============================================================================
echo Project Root: %PROJECT_ROOT%
echo Models Path: %MODELS_PATH%
echo.

REM Check if models path exists
if not exist "%MODELS_PATH%" (
    echo [ERROR] Models path does not exist: %MODELS_PATH%
    echo Creating directory...
    mkdir "%MODELS_PATH%" 2>nul
    if errorlevel 1 (
        echo [ERROR] Failed to create models directory
        pause
        exit /b 1
    )
)

REM Set OLLAMA_MODELS environment variable for current session
set "OLLAMA_MODELS=%MODELS_PATH%"
echo [OK] Set OLLAMA_MODELS=%MODELS_PATH%

REM Check if Ollama is running
echo.
echo Checking Ollama service...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [WARN] Ollama is not running or not reachable
    echo Please start Ollama manually, then run this script again
    echo.
    echo To start Ollama:
    echo   1. Download from https://ollama.ai
    echo   2. Install and start the Ollama service
    echo   3. Restart Ollama with OLLAMA_MODELS set to: %MODELS_PATH%
    echo.
    pause
    exit /b 0
)

echo [OK] Ollama is running

REM Note: To make OLLAMA_MODELS persistent, you need to:
REM 1. Set it as a system/user environment variable, OR
REM 2. Restart Ollama with the environment variable set
echo.
echo ============================================================================
echo IMPORTANT: Restart Ollama with OLLAMA_MODELS set
echo ============================================================================
echo.
echo To make Ollama use the models in %MODELS_PATH%:
echo.
echo Option 1: Set system environment variable (recommended)
echo   1. Open System Properties ^> Environment Variables
echo   2. Add new variable: OLLAMA_MODELS = %MODELS_PATH%
echo   3. Restart Ollama service
echo.
echo Option 2: Start Ollama with environment variable
echo   set OLLAMA_MODELS=%MODELS_PATH%
echo   ollama serve
echo.
echo Option 3: Use PowerShell to set for current session
echo   $env:OLLAMA_MODELS = "%MODELS_PATH%"
echo   ollama serve
echo.
echo After restarting Ollama, run: python scripts\verify_models.py
echo.
pause




