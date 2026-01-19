@echo off
REM ============================================================================
REM Backend Diagnostic Script
REM Runs uvicorn in foreground and pauses on error
REM ============================================================================

setlocal EnableExtensions

set "PROJECT_ROOT=D:\Ideas\Daena_old_upgrade_20251213"
cd /d "%PROJECT_ROOT%"

echo ============================================================================
echo Backend Diagnostic - Running uvicorn in foreground
echo ============================================================================
echo.

REM Detect venv
if exist "venv_daena_main_py310\Scripts\activate.bat" (
    call venv_daena_main_py310\Scripts\activate.bat
    set "PYTHON_EXE=venv_daena_main_py310\Scripts\python.exe"
) else if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    set "PYTHON_EXE=venv\Scripts\python.exe"
) else (
    echo ERROR: No virtual environment found
    echo Please create venv first
    pause
    exit /b 1
)

echo Python: %PYTHON_EXE%
echo.

REM Test import first
echo Testing imports...
%PYTHON_EXE% -c "import backend; import backend.main; print('IMPORT_OK')"
if errorlevel 1 (
    echo.
    echo ============================================================================
    echo IMPORT FAILED - Check error above
    echo ============================================================================
    pause
    exit /b 1
)

echo.
echo ============================================================================
echo Starting uvicorn (press CTRL+C to stop)
echo ============================================================================
echo.

REM Run uvicorn in foreground - errors will be visible
%PYTHON_EXE% -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

REM If we get here, uvicorn exited
echo.
echo ============================================================================
echo Uvicorn stopped
echo ============================================================================
pause





