@echo off
REM ============================================================================
REM Backend Launcher Script (Safe, no nested quotes)
REM ============================================================================
REM This script is called by START_DAENA.bat to launch uvicorn safely
REM Set environment variables from parent batch file if not already set
if "%PROJECT_ROOT%"=="" set "PROJECT_ROOT=%~dp0.."
if "%PYTHON_EXE%"=="" set "PYTHON_EXE=%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe"
if not exist "%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe" if exist "%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe" set "PYTHON_EXE=%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe"
if "%BACKEND_LOG%"=="" set "BACKEND_LOG=%PROJECT_ROOT%\logs\backend_%DATE:~-4,4%%DATE:~-7,2%%DATE:~-10,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%.log"
set "BACKEND_LOG=%BACKEND_LOG: =0%"
REM ============================================================================

setlocal enabledelayedexpansion

REM Get parameters
set "PYTHON_EXE=%~1"
set "BACKEND_LOG=%~2"
set "PROJECT_ROOT=%~3"

if "%PYTHON_EXE%"=="" (
    echo ERROR: Python executable path required
    pause
    exit /b 1
)

if "%BACKEND_LOG%"=="" (
    echo ERROR: Backend log path required
    pause
    exit /b 1
)

if "%PROJECT_ROOT%"=="" (
    echo ERROR: Project root path required
    pause
    exit /b 1
)

REM Change to project root; PYTHONPATH so backend and config resolve
cd /d "%PROJECT_ROOT%"
set "PYTHONPATH=%PROJECT_ROOT%;%PROJECT_ROOT%\backend"
if errorlevel 1 (
    echo ERROR: Cannot change to project root: %PROJECT_ROOT%
    echo Current directory: %CD%
    pause
    exit /b 1
)

REM Activate virtual environment if using venv Python
if /i "%PYTHON_EXE%"=="%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe" (
    if exist "%PROJECT_ROOT%\venv_daena_main_py310\Scripts\activate.bat" (
        call "%PROJECT_ROOT%\venv_daena_main_py310\Scripts\activate.bat"
    )
)

echo ============================================================================
echo Starting Daena Backend Server
echo ============================================================================
echo Python: %PYTHON_EXE%
echo Project: %PROJECT_ROOT%
echo Log: %BACKEND_LOG%
echo.

REM Preflight check: import backend.main
echo [PREFLIGHT] Checking backend.main import...
"%PYTHON_EXE%" -c "import backend.main; print('✅ backend.main import OK')" 2>&1
if errorlevel 1 (
    echo.
    echo ============================================================================
    echo FATAL ERROR: Cannot import backend.main
    echo ============================================================================
    echo Running full import check...
    "%PYTHON_EXE%" -c "import backend.main" 2>&1
    echo.
    echo [INFO] Attempting to install missing dependencies...
    "%PYTHON_EXE%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo FATAL ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
    echo [INFO] Retrying import check...
    "%PYTHON_EXE%" -c "import backend.main; print('✅ backend.main import OK')" 2>&1
    if errorlevel 1 (
        pause
        exit /b 1
    )
)

REM Preflight check: import uvicorn
echo [PREFLIGHT] Checking uvicorn import...
"%PYTHON_EXE%" -c "import uvicorn; print('✅ uvicorn import OK')" 2>&1
if errorlevel 1 (
    echo.
    echo ============================================================================
    echo FATAL ERROR: Cannot import uvicorn
    echo ============================================================================
    echo [INFO] Installing uvicorn...
    "%PYTHON_EXE%" -m pip install uvicorn[standard]
    if errorlevel 1 (
        echo FATAL ERROR: Failed to install uvicorn
        pause
        exit /b 1
    )
    echo [INFO] Retrying import check...
    "%PYTHON_EXE%" -c "import uvicorn; print('✅ uvicorn import OK')" 2>&1
    if errorlevel 1 (
        pause
        exit /b 1
    )
)

REM Preflight check: import cryptography
echo [PREFLIGHT] Checking cryptography import...
"%PYTHON_EXE%" -c "import cryptography; print('✅ cryptography import OK')" 2>&1
if errorlevel 1 (
    echo [WARNING] cryptography not found - installing...
    "%PYTHON_EXE%" -m pip install cryptography
    if errorlevel 1 (
        echo [WARNING] Failed to install cryptography - continuing anyway
    ) else (
        echo [OK] cryptography installed
    )
)

echo.
echo [OK] Preflight checks passed
echo.
echo ============================================================================
echo Starting uvicorn server...
echo ============================================================================
echo.

REM Start uvicorn - output goes to both console and log file
echo Starting uvicorn server...
echo Output will be visible in this window AND logged to: %BACKEND_LOG%
echo.

REM Run uvicorn with output visible in console AND logged to file
REM Use PowerShell to duplicate output (fallback to direct if PowerShell fails)
"%PYTHON_EXE%" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload > "%BACKEND_LOG%" 2>&1

REM If uvicorn exits, pause so we can see the error
echo.
echo ============================================================================
echo Backend server stopped
echo ============================================================================
echo Check log file: %BACKEND_LOG%
echo.
echo Last 20 lines of log:
echo ============================================================================
powershell -Command "Get-Content '%BACKEND_LOG%' -Tail 20 -ErrorAction SilentlyContinue" 2>nul
echo ============================================================================
echo.
pause

