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

:: --- Check llama.cpp [replaces Ollama] ---
echo.
echo  Checking for llama.cpp llama-server...
if not exist "D:\Ideas\llama.cpp\llama-server.exe" (
    echo.
    echo  [Optional] llama-server not found at D:\Ideas\llama.cpp\
    echo  For free local AI, download the llama.cpp Windows CUDA release:
    echo    https://github.com/ggml-org/llama.cpp/releases
    echo  Extract to D:\Ideas\llama.cpp\ and the cudart zip into the same folder.
    echo.
) else (
    echo        Found llama-server.exe
    echo.
    echo  Recommended GGUF models [pull via the new downloader]:
    echo    cd "D:\Ideas\model downloader"
    echo    python download_models.py --project claude-bridge
    echo      - Qwen3-8B Q4_K_M            5.0 GB  general + coding   [fits 8GB VRAM]
    echo      - Qwen2.5-Coder-7B Q4_K_M    4.7 GB  code-specialized   [fits 8GB VRAM]
    echo      - Gemma 4 E4B Q4_K_M         4.8 GB  Google, 128K ctx   [fits 8GB VRAM]
    echo.
    echo  Launch llama-server [example]:
    echo    D:\Ideas\llama.cpp\llama-server.exe -m ^<gguf^> -c 16384 -ngl 999 ^
    echo      --host 127.0.0.1 --port 8080 --jinja --parallel 1
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
