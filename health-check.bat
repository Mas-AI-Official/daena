@echo off
setlocal enabledelayedexpansion
title Daena Health Check
color 0F

:: ============================================================
:: Daena Health Check
:: Checks if backend, frontend, and Ollama are responding
:: ============================================================

echo.
echo  ============================================
echo   DAENA HEALTH CHECK
echo  ============================================
echo.

set "HEALTHY=0"
set "TOTAL=3"

:: Read actual backend port
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "BPORT=8000"
if exist "%ROOT%\backend\.daena-port" (
    set /p BPORT=<"%ROOT%\backend\.daena-port"
)

:: ── Backend ──
echo  [1/3] Backend (http://localhost:!BPORT!/health)
curl -s -o nul -w "%%{http_code}" http://localhost:!BPORT!/health > "%TEMP%\daena_hc_backend.txt" 2>nul
set /p BACKEND_STATUS=<"%TEMP%\daena_hc_backend.txt"
del "%TEMP%\daena_hc_backend.txt" 2>nul

if "!BACKEND_STATUS!"=="200" (
    echo        [OK]   Backend is healthy
    set /a HEALTHY+=1
) else (
    echo        [FAIL] Backend not responding
    echo               Run start-backend.bat or check logs
)

:: ── Frontend ──
echo  [2/3] Frontend (http://localhost:5173)
curl -s -o nul -w "%%{http_code}" http://localhost:5173 > "%TEMP%\daena_hc_frontend.txt" 2>nul
set /p FRONTEND_STATUS=<"%TEMP%\daena_hc_frontend.txt"
del "%TEMP%\daena_hc_frontend.txt" 2>nul

if "!FRONTEND_STATUS!"=="200" (
    echo        [OK]   Frontend is serving
    set /a HEALTHY+=1
) else (
    echo        [FAIL] Frontend not responding
    echo               Run start-frontend.bat or check logs
)

:: ── Ollama ──
echo  [3/3] Ollama  (http://localhost:11434)
curl -s -o nul -w "%%{http_code}" http://localhost:11434/api/tags > "%TEMP%\daena_hc_ollama.txt" 2>nul
set /p OLLAMA_STATUS=<"%TEMP%\daena_hc_ollama.txt"
del "%TEMP%\daena_hc_ollama.txt" 2>nul

if "!OLLAMA_STATUS!"=="200" (
    echo        [OK]   Ollama is running
    set /a HEALTHY+=1
    :: Show available models
    echo.
    echo        Available models:
    for /f "skip=1 tokens=1" %%m in ('ollama list 2^>nul') do (
        echo          - %%m
    )
) else (
    echo        [FAIL] Ollama not responding
    echo               Run start-ollama.bat or: ollama serve
)

:: ── Summary ──
echo.
echo  ============================================
if !HEALTHY! equ !TOTAL! (
    color 0A
    echo   ALL SERVICES HEALTHY  (!HEALTHY!/!TOTAL!)
) else if !HEALTHY! gtr 0 (
    color 0E
    echo   PARTIAL: !HEALTHY!/!TOTAL! services running
) else (
    color 0C
    echo   ALL SERVICES DOWN  (0/!TOTAL!)
)
echo  ============================================
echo.
echo  Dashboard: http://localhost:5173
echo  API Docs:  http://localhost:!BPORT!/docs
echo  Ollama:    http://localhost:11434
echo.

pause
