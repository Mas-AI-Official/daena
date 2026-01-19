@echo off
REM Verify All - Quick verification script
setlocal EnableExtensions

cd /d "%~dp0.."

echo ============================================================================
echo VERIFYING ALL COMPONENTS
echo ============================================================================
echo.

set "PY_MAIN=venv_daena_main_py310\Scripts\python.exe"

echo [1/5] Checking Python...
if not exist "%PY_MAIN%" (
    echo [ERROR] Python venv not found
    exit /b 1
)
"%PY_MAIN%" --version
echo [OK] Python found
echo.

echo [2/5] Checking backend imports...
"%PY_MAIN%" -c "import backend.main; print('[OK] Backend imports')" 2>&1 | findstr /C:"OK" /C:"Error" /C:"Traceback"
if errorlevel 1 (
    echo [ERROR] Backend import failed
    exit /b 1
)
echo.

echo [3/5] Checking database...
if exist "daena.db" (
    for %%A in ("daena.db") do echo [OK] Database exists: %%~zA bytes
) else (
    echo [WARNING] Database not found
)
echo.

echo [4/5] Checking routes...
"%PY_MAIN%" -c "from backend.routes.council import router; print('[OK] Council router')" 2>&1 | findstr /C:"OK" /C:"Error"
"%PY_MAIN%" -c "from backend.routes.intelligence import router; print('[OK] Intelligence router')" 2>&1 | findstr /C:"OK" /C:"Error"
echo.

echo [5/5] Checking backend health (if running)...
python -c "import httpx; r = httpx.get('http://127.0.0.1:8000/api/v1/health/', timeout=2); print('[OK] Backend is running')" 2>&1 | findstr /C:"OK" /C:"Error" || echo [INFO] Backend not running (start with: scripts\quick_start_backend.bat)
echo.

echo ============================================================================
echo VERIFICATION COMPLETE
echo ============================================================================
echo.
echo Next: Start backend and run tests
echo   1. scripts\quick_start_backend.bat
echo   2. python scripts\comprehensive_test_all_phases.py
echo.

pause



