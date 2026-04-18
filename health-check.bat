@echo off
setlocal enabledelayedexpansion
title Daena Health Check
color 0F

:: ============================================================
:: Daena Health Check
:: Checks: Backend, Frontend, Ollama, WSL2, CLI models, GPU
:: ============================================================

echo.
echo  ============================================
echo   DAENA HEALTH CHECK
echo  ============================================
echo.

set "HEALTHY=0"
set "TOTAL=6"

:: Read actual backend port
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "BPORT=8000"
if exist "%ROOT%\backend\.daena-port" (
    set /p BPORT=<"%ROOT%\backend\.daena-port"
)

:: ── 1. Backend ──
echo  [1/6] Backend (http://localhost:!BPORT!/health)
curl -s -o nul -w "%%{http_code}" http://localhost:!BPORT!/health > "%TEMP%\daena_hc_backend.txt" 2>nul
set /p BACKEND_STATUS=<"%TEMP%\daena_hc_backend.txt"
del "%TEMP%\daena_hc_backend.txt" 2>nul

if "!BACKEND_STATUS!"=="200" (
    echo        [OK]   Backend is healthy
    set /a HEALTHY+=1
) else (
    echo        [FAIL] Backend not responding
    echo               Run start-backend.bat
)

:: ── 2. Frontend ──
echo  [2/6] Frontend (http://localhost:5173)
curl -s -o nul -w "%%{http_code}" http://localhost:5173 > "%TEMP%\daena_hc_frontend.txt" 2>nul
set /p FRONTEND_STATUS=<"%TEMP%\daena_hc_frontend.txt"
del "%TEMP%\daena_hc_frontend.txt" 2>nul

if "!FRONTEND_STATUS!"=="200" (
    echo        [OK]   Frontend is serving
    set /a HEALTHY+=1
) else (
    echo        [FAIL] Frontend not responding
    echo               Run start-frontend.bat
)

:: ── 3. Ollama ──
echo  [3/6] Ollama (http://localhost:11434)
curl -s -o nul -w "%%{http_code}" http://localhost:11434/api/tags > "%TEMP%\daena_hc_ollama.txt" 2>nul
set /p OLLAMA_STATUS=<"%TEMP%\daena_hc_ollama.txt"
del "%TEMP%\daena_hc_ollama.txt" 2>nul

if "!OLLAMA_STATUS!"=="200" (
    echo        [OK]   Ollama is running
    set /a HEALTHY+=1
    for /f "skip=1 tokens=1" %%m in ('ollama list 2^>nul') do (
        echo          - %%m
    )
) else (
    echo        [FAIL] Ollama not responding
    echo               Run start-ollama.bat
)

:: ── 4. WSL2 kali-linux ──
echo  [4/6] WSL2 kali-linux
wsl -d kali-linux -- echo "ok" >NUL 2>NUL
if %ERRORLEVEL% EQU 0 (
    echo        [OK]   WSL2 kali-linux available
    set /a HEALTHY+=1
    :: Check security tools
    for /f "delims=" %%t in ('wsl -d kali-linux -- bash -c "echo -n \"nmap:\"; which nmap 2>/dev/null && echo OK || echo MISSING; echo -n \"sqlmap:\"; which sqlmap 2>/dev/null && echo OK || echo MISSING; echo -n \"nikto:\"; which nikto 2>/dev/null && echo OK || echo MISSING" 2^>nul') do (
        echo          %%t
    )
) else (
    echo        [FAIL] WSL2 kali-linux not available
    echo               Run: wsl --install kali-linux
)

:: ── 5. CLI Models ──
echo  [5/6] CLI Models (powerful LLMs)
set "CLI_COUNT=0"
where claude >nul 2>nul
if not errorlevel 1 (
    echo        [OK]   Claude Code CLI
    set /a CLI_COUNT+=1
)
where codex >nul 2>nul
if not errorlevel 1 (
    echo        [OK]   Codex CLI
    set /a CLI_COUNT+=1
)
where gemini >nul 2>nul
if not errorlevel 1 (
    echo        [OK]   Gemini CLI
    set /a CLI_COUNT+=1
)
if !CLI_COUNT! GTR 0 (
    echo        !CLI_COUNT! CLI model(s) available
    set /a HEALTHY+=1
) else (
    echo        [WARN] No CLI models found
    echo               Install claude, codex, or gemini CLI
)

:: ── 6. GPU ──
echo  [6/6] GPU
wsl -d kali-linux -- bash -c "nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader 2>/dev/null || echo 'No GPU'" > "%TEMP%\daena_hc_gpu.txt" 2>nul
set /p GPU_INFO=<"%TEMP%\daena_hc_gpu.txt"
del "%TEMP%\daena_hc_gpu.txt" 2>nul

if not "!GPU_INFO!"=="No GPU" (
    echo        [OK]   !GPU_INFO!
    set /a HEALTHY+=1
) else (
    echo        [WARN] No GPU detected from WSL2
)

:: ── Summary ──
echo.
echo  ============================================
if !HEALTHY! equ !TOTAL! (
    color 0A
    echo   ALL SYSTEMS HEALTHY  (!HEALTHY!/!TOTAL!)
) else if !HEALTHY! gtr 3 (
    color 0E
    echo   MOSTLY HEALTHY: !HEALTHY!/!TOTAL! systems running
) else if !HEALTHY! gtr 0 (
    color 0E
    echo   PARTIAL: !HEALTHY!/!TOTAL! systems running
) else (
    color 0C
    echo   ALL SYSTEMS DOWN  (0/!TOTAL!)
)
echo  ============================================
echo.
echo  Dashboard: http://localhost:5173
echo  API Docs:  http://localhost:!BPORT!/docs
echo  Ollama:    http://localhost:11434
echo.

pause
