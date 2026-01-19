@echo off
REM Bootstrap script: Create venv, upgrade pip, install dependencies, generate lockfile
setlocal enabledelayedexpansion

echo.
echo ========================================
echo    BOOTSTRAP VENV + DEPENDENCIES
echo ========================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%.."

REM Check Python
set "HOST_PY=python"
py -3.10 --version >nul 2>&1
if not errorlevel 1 (
    set "HOST_PY=py -3.10"
)

%HOST_PY% --version >nul 2>&1
if errorlevel 1 (
    echo [FATAL] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

set "VENV_MAIN=venv_daena_main_py310"

REM Step 1: Create venv if missing
echo [1/4] Checking virtual environment...
if not exist "%VENV_MAIN%\Scripts\python.exe" (
    echo   Creating venv: %VENV_MAIN%
    %HOST_PY% -m venv "%VENV_MAIN%"
    if errorlevel 1 (
        echo [FATAL] Failed to create venv
        pause
        exit /b 1
    )
    echo   [OK] Venv created
) else (
    echo   [OK] Venv already exists
)

set "PY_MAIN=%VENV_MAIN%\Scripts\python.exe"

REM Step 2: Upgrade pip tooling
echo [2/4] Upgrading pip tooling...
"%PY_MAIN%" -m pip install --upgrade pip setuptools wheel --quiet
if errorlevel 1 (
    echo [WARNING] Pip upgrade had issues, but continuing...
) else (
    echo   [OK] Pip tooling upgraded
)

REM Step 3: Install requirements
echo [3/4] Installing dependencies from requirements.txt...
if not exist "requirements.txt" (
    echo [FATAL] requirements.txt not found
    pause
    exit /b 1
)

"%PY_MAIN%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [FATAL] Failed to install dependencies
    pause
    exit /b 1
)
echo   [OK] Dependencies installed

REM Step 4: Generate lockfile
echo [4/4] Generating requirements.lock.txt...
"%PY_MAIN%" -m pip freeze > requirements.lock.txt
if errorlevel 1 (
    echo [WARNING] Failed to generate lockfile, but continuing...
) else (
    echo   [OK] Lockfile generated
)

echo.
echo ========================================
echo    BOOTSTRAP COMPLETE
echo ========================================
echo.

exit /b 0









