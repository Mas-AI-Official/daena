@echo off
echo === Daena Startup ===

:: Kill all Python processes (old servers)
taskkill /f /im python.exe >nul 2>&1
timeout /t 3 /nobreak >nul

:: Start backend on port 8005
echo Starting backend on port 8005...
cd /d D:\Ideas\Daena\backend
start /b D:\Ideas\Daena\venv_daena\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8005
timeout /t 6 /nobreak >nul

:: Verify backend is up
curl -s http://localhost:8005/api/v1/health >nul 2>&1
if errorlevel 1 (
    echo ERROR: Backend failed to start!
    pause
    exit /b 1
)
echo Backend: OK

:: Start frontend proxying to 8005
echo Starting frontend on port 5173...
cd /d D:\Ideas\Daena\frontend
set DAENA_BACKEND_PORT=8005
start /b npm run dev

timeout /t 4 /nobreak >nul
echo.
echo === Daena Ready ===
echo Backend:  http://localhost:8005
echo Frontend: http://localhost:5173
echo Login:    masoud.masoori@mas-ai.co
echo.
pause
