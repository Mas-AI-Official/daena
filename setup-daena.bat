@echo off
:: =============================================================
:: Daena — First-Time Setup
:: =============================================================
:: Creates venv, installs Python + Node dependencies, copies .env
:: =============================================================

title Daena — First-Time Setup
color 0E
echo.
echo  ============================================
echo   DAENA — First-Time Setup
echo  ============================================
echo.

set "ROOT=D:\Ideas\Daena"
set "VENV=%ROOT%\venv_daena"
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"

:: --- Check Python ---
echo  [1/6] Checking Python...
python --version >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  [ERROR] Python is not installed or not in PATH.
    echo  Install Python 3.10+ from https://python.org
    pause
    exit /b 1
)
python --version

:: --- Check Node.js ---
echo  [2/6] Checking Node.js...
node --version >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  [ERROR] Node.js is not installed or not in PATH.
    echo  Install Node.js 18+ from https://nodejs.org
    pause
    exit /b 1
)
node --version

:: --- Create virtual environment ---
echo  [3/6] Creating Python virtual environment...
if not exist "%VENV%\Scripts\python.exe" (
    python -m venv "%VENV%"
    echo        Created: %VENV%
) else (
    echo        Already exists: %VENV%
)

:: --- Install Python dependencies ---
echo  [4/6] Installing Python dependencies...
cd /d "%BACKEND%"
"%VENV%\Scripts\pip.exe" install -r requirements.txt 2>NUL
if %ERRORLEVEL% NEQ 0 (
    echo        Trying pyproject.toml install...
    "%VENV%\Scripts\pip.exe" install -e ".[dev]" 2>NUL
    if %ERRORLEVEL% NEQ 0 (
        "%VENV%\Scripts\pip.exe" install -e . 2>NUL
    )
)
echo        Python dependencies installed.

:: --- Copy .env if missing ---
echo  [5/6] Checking .env...
if not exist "%BACKEND%\.env" (
    if exist "%BACKEND%\.env.example" (
        copy "%BACKEND%\.env.example" "%BACKEND%\.env" >NUL
        echo        Copied .env.example to .env
    ) else (
        echo        [WARNING] No .env or .env.example found.
        echo        You may need to create backend\.env manually.
    )
) else (
    echo        .env already exists.
)

:: --- Install Node dependencies ---
echo  [6/6] Installing frontend dependencies...
cd /d "%FRONTEND%"
call npm install
echo        Frontend dependencies installed.

echo.
echo  ============================================
echo   SETUP COMPLETE!
echo  ============================================
echo.
echo   Next steps:
echo   1. Edit backend\.env with your API keys (optional)
echo   2. Install Ollama from https://ollama.com (for local LLM)
echo   3. Run: start-daena.bat
echo.
echo  ============================================
echo.
pause