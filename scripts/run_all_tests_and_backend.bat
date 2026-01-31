@echo off
setlocal EnableExtensions
REM Start backend and run comprehensive_test_all_phases.py. For smoke + manual verification (no backend start) use scripts\run_manual_steps.bat.

set "PROJECT_ROOT=%~dp0.."
cd /d "%PROJECT_ROOT%"

echo [STEP 1] Checking Python...
set "PY_MAIN="
if exist "%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe" set "PY_MAIN=%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe"
if not defined PY_MAIN if exist "%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe" set "PY_MAIN=%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe"
if not defined PY_MAIN set "PY_MAIN=python"
"%PY_MAIN%" --version
if errorlevel 1 (
    echo ❌ Python not found
    exit /b 1
)
echo ✅ Python OK
echo.

REM Step 2: Install test dependencies
echo [STEP 2] Installing test dependencies...
"%PY_MAIN%" -m pip install httpx websocket-client --quiet
echo ✅ Dependencies installed
echo.

REM Step 3: Check database
echo [STEP 3] Checking database...
if exist "%PROJECT_ROOT%\daena.db" (
    echo ✅ Database exists
) else (
    echo ⚠️ Database not found - will be created on first run
)
echo.

REM Step 4: Test imports
echo [STEP 4] Testing backend imports...
cd "%PROJECT_ROOT%"
"%PY_MAIN%" -c "import sys; sys.path.insert(0, '.'); from backend.database import get_db; from backend.routes import agents, council, projects, voice, system; print('✅ All imports successful')" 2>&1
if errorlevel 1 (
    echo ❌ Import test failed
    exit /b 1
)
echo.

REM Step 5: Start backend in background
echo [STEP 5] Starting backend server...
echo Starting backend on http://127.0.0.1:8000...
if exist "%PROJECT_ROOT%\scripts\start_backend.bat" (
    REM Use the proper start_backend.bat script
    start "Daena Backend" cmd /k "cd /d %PROJECT_ROOT% && scripts\start_backend.bat "%PY_MAIN%" "%PROJECT_ROOT%\logs\backend_test.log" "%PROJECT_ROOT%""
) else (
    REM Fallback: direct uvicorn launch
    start "Daena Backend" cmd /c "cd /d %PROJECT_ROOT% && %PY_MAIN% -m uvicorn backend.main:app --host 127.0.0.1 --port 8000"
)
timeout /t 5 /nobreak >nul
echo ✅ Backend started (check window for status)
echo.

REM Step 6: Wait for backend to be ready
echo [STEP 6] Waiting for backend to be ready...
set "RETRIES=0"
:WAIT_LOOP
timeout /t 2 /nobreak >nul
curl -s http://127.0.0.1:8000/api/v1/health/ >nul 2>&1
if errorlevel 1 (
    set /a RETRIES+=1
    if %RETRIES% GEQ 15 (
        echo ❌ Backend did not start after 30 seconds
        exit /b 1
    )
    echo Waiting for backend... (%RETRIES%/15)
    goto WAIT_LOOP
)
echo ✅ Backend is ready
echo.

REM Step 7: Run comprehensive tests
echo [STEP 7] Running comprehensive tests...
"%PY_MAIN%" "%PROJECT_ROOT%\scripts\comprehensive_test_all_phases.py"
set "TEST_RESULT=%ERRORLEVEL%"
echo.

REM Step 8: Summary
echo ============================================================================
echo TEST SUMMARY
echo ============================================================================
if %TEST_RESULT% EQU 0 (
    echo ✅ ALL TESTS PASSED
) else (
    echo ❌ SOME TESTS FAILED
)
echo.
echo Backend is running on http://127.0.0.1:8000
echo Press any key to stop backend and exit...
pause >nul

REM Stop backend (find and kill uvicorn process)
taskkill /FI "WINDOWTITLE eq Daena Backend*" /T /F >nul 2>&1
echo ✅ Backend stopped

exit /b %TEST_RESULT%

