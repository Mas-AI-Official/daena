@echo off
REM Run the Daena Killer Demo using the correct virtual environment
REM This ensures database integration works for the web dashboard.

cd /d "%~dp0.."
echo Working Directory: %CD%

echo Starting Daena Killer Demo...
if exist "venv_daena_main_py310\Scripts\python.exe" (
    echo Using dedicated venv...
    "venv_daena_main_py310\Scripts\python.exe" scripts/killer_demo.py
    if errorlevel 1 (
        echo.
        echo [ERROR] Demo crashed with exit code %errorlevel%
        pause
    )
) else (
    echo [WARNING] Virtual environment not found. Falling back to global python.
    python scripts/killer_demo.py
    if errorlevel 1 (
        echo.
        echo [ERROR] Demo crashed with exit code %errorlevel%
        pause
    )
)

echo.
echo Demo finished.
pause
