@echo off
:: =============================================================
:: Daena -- Quick Start (works from any location)
:: =============================================================
setlocal

set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"

echo.
echo  === Daena Startup ===
echo.

:: Kill old server processes
taskkill /f /im python.exe >nul 2>&1
timeout /t 2 /nobreak >nul

:: Start backend
echo  Starting backend...
cd /d "%ROOT%\backend"
if exist "%ROOT%\venv_daena\Scripts\python.exe" (
    start /b "%ROOT%\venv_daena\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
) else if exist ".venv\Scripts\python.exe" (
    start /b .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
) else (
    start /b python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
)
timeout /t 5 /nobreak >nul

:: Verify backend
curl -s http://127.0.0.1:8000/api/v1/health >nul 2>&1
if errorlevel 1 (
    echo  [!] Backend failed to start. Run setup-daena.bat first.
    pause
    exit /b 1
)
echo  Backend:  http://127.0.0.1:8000  [OK]

:: Start frontend
echo  Starting frontend...
cd /d "%ROOT%\frontend"
start /b npm run dev
timeout /t 4 /nobreak >nul

echo.
echo  ============================================
echo   DAENA IS RUNNING
echo   Backend:  http://127.0.0.1:8000
echo   Frontend: http://127.0.0.1:5173
echo  ============================================
echo.
pause
