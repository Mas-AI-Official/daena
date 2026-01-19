@echo off
REM ============================================================================
REM START_OLLAMA.bat - Ollama Brain Launcher with Health Check
REM Project: Daena AI VP
REM ============================================================================
setlocal EnableExtensions

set "PROJECT_ROOT=D:\Ideas\Daena_old_upgrade_20251213"
set "OLLAMA_PORT=11434"
set "OLLAMA_BASE_URL=http://127.0.0.1:11434"

REM UTF-8 console
chcp 65001 >nul 2>&1

echo.
echo ============================================================================
echo DAENA BRAIN - OLLAMA LAUNCHER
echo ============================================================================
echo.

REM Check if Ollama is already running
echo [INFO] Checking if Ollama is already running...
powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop; exit 0 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    echo [OK] Ollama is already running
    echo.
    goto :VERIFY_MODEL
)

REM Start Ollama
echo [INFO] Starting Ollama service...
start "Ollama Service" ollama serve
timeout /t 3 /nobreak >nul

REM Health check loop
set "HEALTH_COUNT=0"
set "MAX_HEALTH=15"

:HEALTH_LOOP
timeout /t 1 /nobreak >nul
set /a HEALTH_COUNT+=1

powershell -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop; exit 0 } catch { exit 1 }" >nul 2>&1
if not errorlevel 1 (
    echo [OK] Ollama is healthy
    echo.
    goto :VERIFY_MODEL
)

if %HEALTH_COUNT% GEQ %MAX_HEALTH% (
    echo [ERROR] Ollama did not start within %MAX_HEALTH% seconds
    echo.
    echo Troubleshooting:
    echo   1. Check if Ollama is installed: ollama --version
    echo   2. Try starting manually: ollama serve
    echo   3. Check port %OLLAMA_PORT% is not in use
    echo.
    pause
    exit /b 1
)

echo [WAIT] Waiting for Ollama... (%HEALTH_COUNT%/%MAX_HEALTH%)
goto :HEALTH_LOOP

:VERIFY_MODEL
echo [INFO] Verifying Daena brain model...
ollama list | findstr /C:"qwen2.5:7b-instruct" >nul 2>&1
if errorlevel 1 (
    echo [WARNING] qwen2.5:7b-instruct not found
    echo.
    echo Would you like to download it? (Y/N)
    set /p "DOWNLOAD="
    if /i "%DOWNLOAD%"=="Y" (
        echo [INFO] Downloading qwen2.5:7b-instruct (this may take several minutes)...
        ollama pull qwen2.5:7b-instruct
        if errorlevel 1 (
            echo [ERROR] Failed to download model
            pause
            exit /b 1
        )
        echo [OK] Model downloaded
    ) else (
        echo [WARNING] Model not downloaded - brain may not function
    )
) else (
    echo [OK] qwen2.5:7b-instruct is available
)

echo.
echo ============================================================================
echo OLLAMA BRAIN - READY
echo ============================================================================
echo   Base URL: %OLLAMA_BASE_URL%
echo   Model:    qwen2.5:7b-instruct
echo   Status:   Running
echo ============================================================================
echo.
echo Press any key to close this window (Ollama will keep running in background)
pause >nul
