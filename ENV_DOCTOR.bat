@echo off
REM ============================================================
REM DAENA ENVIRONMENT DOCTOR
REM ============================================================
REM Verifies all dependencies and environment setup
REM Run this before START_DAENA.bat if you encounter issues

echo ============================================================
echo   DAENA ENVIRONMENT DOCTOR
echo   Date: %DATE% %TIME%
echo ============================================================
echo.

setlocal EnableExtensions EnableDelayedExpansion

set "ROOT=%~dp0"
cd /d "%ROOT%"

set ISSUES_FOUND=0
set WARNINGS_FOUND=0

echo [1/8] Python Environment Check
echo ──────────────────────────────
if exist "venv_daena_main_py310\Scripts\python.exe" (
    for /f "delims=" %%v in ('venv_daena_main_py310\Scripts\python.exe --version 2^>^&1') do set PYTHON_VER=%%v
    echo   ✓ Main Python: !PYTHON_VER!
) else (
    echo   ✗ Main Python venv not found: venv_daena_main_py310
    echo     FIX: python -m venv venv_daena_main_py310
    set /a ISSUES_FOUND+=1
)

if exist "venv_daena_audio_py310\Scripts\python.exe" (
    for /f "delims=" %%v in ('venv_daena_audio_py310\Scripts\python.exe --version 2^>^&1') do set AUDIO_VER=%%v
    echo   ✓ Audio Python: !AUDIO_VER!
) else (
    echo   ⚠ Audio Python venv not found (voice features disabled)
    echo     FIX: python -m venv venv_daena_audio_py310
    set /a WARNINGS_FOUND+=1
)
echo.

echo [2/8] Node.js Check
echo ──────────────────────────────
where node >nul 2>&1
if %errorlevel%==0 (
    for /f "delims=" %%v in ('node --version 2^>^&1') do set NODE_VER=%%v
    echo   ✓ Node.js: !NODE_VER!
) else (
    echo   ⚠ Node.js not found (some frontend features may be limited)
    set /a WARNINGS_FOUND+=1
)
echo.

echo [3/8] Port Availability Check
echo ──────────────────────────────
for %%p in (8000 5001 11434) do (
    netstat -ano | findstr ":%%p " | findstr "LISTENING" >nul 2>&1
    if !errorlevel!==0 (
        echo   ⚠ Port %%p is already in use
        set /a WARNINGS_FOUND+=1
    ) else (
        echo   ✓ Port %%p available
    )
)
echo.

echo [4/8] Required Environment Variables
echo ──────────────────────────────
set REQUIRED_VARS=PYTHONPATH
for %%v in (%REQUIRED_VARS%) do (
    if defined %%v (
        echo   ✓ %%v is set
    ) else (
        echo   ⚠ %%v not set (will be set by launcher)
    )
)

REM Check for backslash issues in env vars
echo.
echo   Checking for invalid paths...
if defined PYTHONPATH (
    echo !PYTHONPATH! | findstr /C:"\default-key" >nul 2>&1
    if !errorlevel!==0 (
        echo   ✗ PYTHONPATH contains invalid path: \default-key
        echo     FIX: Remove invalid path from PYTHONPATH
        set /a ISSUES_FOUND+=1
    )
)
echo.

echo [5/8] Model Paths Check
echo ──────────────────────────────
if defined HF_HOME (
    echo   ✓ HF_HOME: %HF_HOME%
) else (
    echo   ⚠ HF_HOME not set, will use default: %USERPROFILE%\.cache\huggingface
)

if defined TRANSFORMERS_CACHE (
    echo   ✓ TRANSFORMERS_CACHE: %TRANSFORMERS_CACHE%
) else (
    echo   ⚠ TRANSFORMERS_CACHE not set, will use default
)
echo.

echo [6/8] Database Check
echo ──────────────────────────────
if exist "daena.db" (
    for %%F in (daena.db) do set DB_SIZE=%%~zF
    set /a DB_SIZE_KB=!DB_SIZE!/1024
    echo   ✓ Database found: !DB_SIZE_KB! KB
) else (
    echo   ⚠ Database not found (will be created on first run)
)
echo.

echo [7/8] Ollama Check
echo ──────────────────────────────
where ollama >nul 2>&1
if %errorlevel%==0 (
    echo   ✓ Ollama installed
    
    REM Check if Ollama is running
    tasklist /FI "IMAGENAME eq ollama.exe" 2>nul | findstr /I "ollama.exe" >nul
    if !errorlevel!==0 (
        echo   ✓ Ollama is running
    ) else (
        echo   ⚠ Ollama not running (will be started by launcher)
    )
) else (
    echo   ⚠ Ollama not installed
    echo     Get it from: https://ollama.ai
    set /a WARNINGS_FOUND+=1
)
echo.

echo [8/8] Dependencies Check
echo ──────────────────────────────
if exist "requirements.txt" (
    echo   ✓ requirements.txt found
) else (
    echo   ✗ requirements.txt not found
    set /a ISSUES_FOUND+=1
)

if exist "package.json" (
    echo   ✓ package.json found
) else (
    echo   ⚠ package.json not found (Node features limited)
)

if exist "pyproject.toml" (
    echo   ✓ pyproject.toml found
)

REM Check for DaenaAgent framework (Claude integration)
if exist "backend\services\daena_agent.py" (
    echo   ✓ DaenaAgent framework installed (VP Interface Mode)
) else (
    echo   ⚠ DaenaAgent framework not found - run Claude integration
)
echo.

echo ============================================================
echo   ENVIRONMENT DOCTOR SUMMARY
echo ============================================================
echo.

if %ISSUES_FOUND%==0 if %WARNINGS_FOUND%==0 (
    echo   ✓ All checks passed! Your environment is ready.
    echo.
    echo   Run START_DAENA.bat to start the system.
) else (
    if %ISSUES_FOUND% GTR 0 (
        echo   ✗ Found %ISSUES_FOUND% critical issue(s) - please fix before running
    )
    if %WARNINGS_FOUND% GTR 0 (
        echo   ⚠ Found %WARNINGS_FOUND% warning(s) - system may run with limited features
    )
)
echo.
echo ============================================================
echo.
pause
