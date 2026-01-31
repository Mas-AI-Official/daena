@echo off
title Content OPS AI - Model Setup
color 0A

set ROOT=D:\Ideas\contentops-core
set VENV_PYTHON=%ROOT%\venv\Scripts\python.exe

echo ========================================
echo   Content OPS AI - Comprehensive Setup
echo ========================================
echo.

if not exist "%VENV_PYTHON%" (
    echo [ERROR] Virtual environment not found at %VENV_PYTHON%
    echo Please run launch.bat first to initialize the environment.
    pause
    exit /b 1
)

echo [INFO] Starting comprehensive model verification and download...
echo [INFO] This will check Ollama, XTTS, and LTX models.
echo.

"%VENV_PYTHON%" "%ROOT%\setup_all_models.py"

echo.
echo ========================================
echo   Setup Completed!
echo ========================================
echo.
pause
