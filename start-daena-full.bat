@echo off
setlocal enabledelayedexpansion
:: =============================================================
:: Daena -- Full Stack Start (Frontend on Windows + Backend on Kali)
:: =============================================================
:: This is the PRODUCTION start script.
:: Backend runs on WSL2 Kali (real tools, vLLM, offensive mode)
:: Frontend runs on Windows (React + Vite)
:: Both share localhost.
:: =============================================================

title Daena -- Full Stack (Kali Backend)
color 0B
echo.
echo  ============================================
echo   DAENA -- Full Stack Launch
echo   Backend: WSL2 Kali Linux (offensive mode)
echo   Frontend: Windows (React + Vite)
echo  ============================================
echo.

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "FRONTEND=%ROOT%\frontend"

:: --- Check WSL2 is available ---
echo  [1/4] Checking WSL2...
wsl --status >NUL 2>NUL
if %ERRORLEVEL% NEQ 0 (
    echo  [ERROR] WSL2 not installed.
    echo          Run: scripts\setup-wsl-kali.ps1 as Administrator
    pause
    exit /b 1
)
echo        WSL2 available.

:: --- Start Ollama (local models, fallback) ---
echo  [2/4] Checking Ollama...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I "ollama.exe" >NUL
if %ERRORLEVEL% NEQ 0 (
    echo        Starting Ollama (fallback models)...
    start "" /MIN ollama serve
    timeout /t 2 /nobreak >NUL
) else (
    echo        Ollama already running.
)

:: --- Start Backend on Kali ---
echo  [3/4] Starting backend on Kali Linux...
start "Daena Backend (Kali)" wsl bash /mnt/d/Ideas/Daena/scripts/start-backend-kali.sh
timeout /t 5 /nobreak >NUL

:: --- Start Frontend on Windows ---
echo  [4/4] Starting frontend...
start "Daena Frontend" /MIN cmd /c "cd /d %FRONTEND% && npm run dev"
timeout /t 3 /nobreak >NUL

:: --- Open browser ---
start "" http://localhost:5173

echo.
echo  ============================================
echo   DAENA IS RUNNING (FULL OFFENSIVE MODE)
echo  ============================================
echo.
echo   Frontend:  http://localhost:5173
echo   Backend:   http://localhost:8000 (Kali Linux)
echo   API docs:  http://localhost:8000/docs
echo   Missions:  http://localhost:8000/docs#/missions
echo.
echo   Tools available: nmap, nuclei, sqlmap, gobuster,
echo   subfinder, httpx, tor, proxychains, and more.
echo.
echo   To stop: close terminal windows or run stop-daena.bat
echo  ============================================
echo.
pause
