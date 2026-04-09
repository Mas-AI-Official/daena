@echo off
:: =============================================================
:: Daena Setup -- Works from any drive, any folder
:: =============================================================
setlocal enabledelayedexpansion

title Daena -- Setup

:: Auto-detect where this script lives (works from any clone location)
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "BACKEND=%ROOT%\backend"
set "FRONTEND=%ROOT%\frontend"

color 0E
cls
echo.
echo       ___   ___   ___  _  _   ___
echo      ^|   \ ^/ _ \ ^| __^|^| \^| ^| ^/ _ \
echo      ^| ^|) ^|^|  _/ ^| _^ ^|^| .  ^|^| ^(_^) ^|
echo      ^|___/ ^|_^|   ^|___^|^|_^|\_^| \___/
echo.
echo      Your AI Vice President
echo      Governed Multi-Agent Orchestration Platform
echo.
echo      ============================================
echo       Installing to: %ROOT%
echo      ============================================
echo.

:: --- Check Python ---
echo  [1/6] Checking Python...
python --version >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [!] Python not found. Install Python 3.11+ from https://python.org
    echo      Make sure to check "Add to PATH" during install.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2" %%V in ('python --version 2^>^&1') do echo        Found Python %%V

:: --- Check Node ---
echo  [2/6] Checking Node.js...
node --version >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [!] Node.js not found. Install Node.js 18+ from https://nodejs.org
    echo.
    pause
    exit /b 1
)
for /f %%V in ('node --version 2^>^&1') do echo        Found Node.js %%V

:: --- Create Python virtual environment ---
echo  [3/6] Creating Python virtual environment...
set "VENV=%ROOT%\venv_daena"
if not exist "%VENV%" (
    python -m venv "%VENV%"
    echo        Created venv_daena
) else (
    echo        venv_daena already exists
)

:: --- Install backend dependencies ---
echo  [4/6] Installing backend dependencies...
call "%VENV%\Scripts\activate.bat"
pip install -e "%BACKEND%[dev]" --quiet --quiet 2>NUL
echo        Backend dependencies installed

:: --- Install Playwright browsers ---
echo  [4b/6] Installing Playwright browsers...
playwright install chromium --with-deps 2>NUL
if errorlevel 1 (
    echo        [WARN] Playwright browser install failed. Run manually:
    echo               venv_daena\Scripts\playwright install chromium
) else (
    echo        Playwright chromium installed
)

:: --- Install frontend dependencies ---
echo  [5/6] Installing frontend dependencies...
cd /d "%FRONTEND%"
call npm install --quiet 2>NUL
echo        Frontend dependencies installed

:: --- Create .env if missing ---
echo  [5/6] Setting up environment...
if not exist "%BACKEND%\.env" (
    if exist "%ROOT%\.env.example" (
        copy "%ROOT%\.env.example" "%BACKEND%\.env" >NUL
        echo        Created backend\.env from template
    ) else (
        echo        No .env.example found -- using defaults
    )
) else (
    echo        backend\.env already exists
)

:: --- Check Ollama ---
echo.
echo  Checking for Ollama...
ollama --version >NUL 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo  [Optional] Ollama not found.
    echo  For free local AI, install from: https://ollama.ai
    echo  Then run: ollama pull llama3.1:8b
    echo.
) else (
    for /f %%V in ('ollama --version 2^>^&1') do echo        Found Ollama %%V
    echo.
    echo  Recommended models (run any of these):
    echo    ollama pull llama3.1:8b          4.7 GB  General chat
    echo    ollama pull qwen2.5-coder:14b    9 GB    Coding
    echo    ollama pull deepseek-r1:14b      9 GB    Reasoning
    echo.
)

:: --- Done ---
cd /d "%ROOT%"
echo.
echo  ============================================
echo.
echo      DAENA IS READY
echo.
echo      Start backend:   cd backend
echo                        ..\venv_daena\Scripts\activate
echo                        python run.py
echo.
echo      Start frontend:  cd frontend
echo                        npm run dev
echo.
echo      Then open:        http://127.0.0.1:5173
echo.
echo  ============================================
echo.
echo  Optional: Install your tools on Daena:
echo    npm install -g @anthropic-ai/claude-code
echo    npm install -g @openai/codex
echo    npm install -g @google/gemini-cli
echo.
pause
