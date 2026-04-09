@echo off
setlocal enabledelayedexpansion
title Daena Backend
color 0A

:: ============================================================
:: Daena Backend Launcher
:: Canonical dev backend entry: backend\run.py
:: ============================================================

:: Detect project root from bat location
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "BACKEND=%ROOT%\backend"
set "VENV=%ROOT%\venv_daena"
set "PORT_FILE=%BACKEND%\.daena-port"
set "DAENA_ENV_PRECEDENCE=env_file_first"

echo.
echo  ============================================
echo   DAENA BACKEND
echo  ============================================
echo.

:: Check venv exists (try venv_daena first, then backend/.venv)
if not exist "%VENV%\Scripts\python.exe" (
    set "VENV=%BACKEND%\.venv"
)
if not exist "%VENV%\Scripts\python.exe" (
    echo  [ERROR] Virtual environment not found.
    echo          Checked: %ROOT%\venv_daena and %BACKEND%\.venv
    echo  Run setup-daena.bat first to create it.
    pause
    exit /b 1
)
echo  Using venv: %VENV%

:: Check backend dir
if not exist "%BACKEND%\app\main.py" (
    echo  [ERROR] Backend not found at %BACKEND%
    pause
    exit /b 1
)

:: Start via run.py (single canonical backend contract)
echo  [1/1] Starting backend via run.py with backend\.env precedence...
echo.
echo  The actual backend port is written to:
echo          %PORT_FILE%
echo  ============================================
echo.

cd /d "%BACKEND%"
if exist "%PORT_FILE%" del "%PORT_FILE%" >NUL 2>NUL
"%VENV%\Scripts\python.exe" run.py

pause
