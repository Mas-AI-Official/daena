@echo off
setlocal enabledelayedexpansion
title Daena - Health Check
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
    echo               Run start-daena.bat
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
    echo               Run start-daena.bat
)

:: -- 3. llama.cpp llama-server [replaces Ollama] --
echo  [3/6] llama-server (http://127.0.0.1:8080)
curl -s -o nul -w "%%{http_code}" http://127.0.0.1:8080/health > "%TEMP%\daena_hc_llama.txt" 2>nul
set /p LLAMA_STATUS=<"%TEMP%\daena_hc_llama.txt"
del "%TEMP%\daena_hc_llama.txt" 2>nul

if "!LLAMA_STATUS!"=="200" (
    echo        [OK]   llama-server is running
    set /a HEALTHY+=1
    curl -s http://127.0.0.1:8080/v1/models 2>nul ^| python -c "import sys,json; d=json.load(sys.stdin); [print('         -',m['id']) for m in d.get('data',[])]" 2>nul
) else (
    echo        [FAIL] llama-server not responding
    echo               Start: D:\Ideas\llama.cpp\llama-server.exe -m [gguf] -c 16384 -ngl 999 --port 8080
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
echo  llama-server: http://127.0.0.1:8080
echo.

pause
