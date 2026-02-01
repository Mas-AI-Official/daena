@echo off
title DAENA - BACKEND
REM ============================================================
REM Helper script called by START_DAENA.bat
REM ============================================================

if "%~1" NEQ "" set BACKEND_PORT=%~1

echo [BACKEND] Activating environment...
if exist "venv_daena_main_py310\Scripts\activate.bat" (
    call venv_daena_main_py310\Scripts\activate.bat
) else (
    echo [ERROR] Virtual environment not found: venv_daena_main_py310
    exit /b 1
)

echo [BACKEND] Starting Service on Port %BACKEND_PORT%...
echo [BACKEND] Mode: %ENVIRONMENT%
echo.

REM Using python -m backend.main ensures sys.path is correct
python -m backend.main

if errorlevel 1 (
    echo [ERROR] Backend crashed or exited with error.
    pause
    exit /b 1
)

pause
