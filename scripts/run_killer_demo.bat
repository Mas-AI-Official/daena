@echo off
REM Run the Daena Killer Demo using the correct virtual environment
REM This ensures database integration works for the web dashboard.

cd /d "%~dp0.."
echo Working Directory: %CD%

echo Starting Daena Killer Demo...
if exist "venv_daena_main_py310\Scripts\python.exe" (
    venv_daena_main_py310\Scripts\python.exe scripts/killer_demo.py
) else (
    echo [WARNING] Virtual environment not found. Falling back to global python.
    echo Dashboard integration may not work if dependencies (sqlalchemy) are missing.
    python scripts/killer_demo.py
)
pause
