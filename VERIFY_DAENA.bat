@echo off
chcp 65001 >nul
title Daena Verification Script

echo =====================================================
echo    DAENA SUPER-SYNC VERIFICATION
echo =====================================================
echo.
echo This script will verify that all components are
echo correctly installed and configured.
echo.

set VERIFICATION_PASSED=0
set VERIFICATION_FAILED=0

:: Test 1: Python
echo [TEST 1] Checking Python installation...
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo          [PASS] Python is installed
    for /f "delims=" %%v in ('python --version') do echo          Version: %%v
    set /a VERIFICATION_PASSED+=1
) else (
    echo          [FAIL] Python is not installed
    set /a VERIFICATION_FAILED+=1
)
echo.

:: Test 2: Node.js
echo [TEST 2] Checking Node.js installation...
node --version >nul 2>&1
if %errorlevel% equ 0 (
    echo          [PASS] Node.js is installed
    for /f "delims=" %%v in ('node --version') do echo          Version: %%v
    set /a VERIFICATION_PASSED+=1
) else (
    echo          [FAIL] Node.js is not installed
    set /a VERIFICATION_FAILED+=1
)
echo.

:: Test 3: Directory Structure
echo [TEST 3] Checking directory structure...
if exist "backend\" (
    echo          [PASS] backend/ directory exists
    set /a VERIFICATION_PASSED+=1
) else (
    echo          [FAIL] backend/ directory missing
    set /a VERIFICATION_FAILED+=1
)

if exist "frontend\" (
    echo          [PASS] frontend/ directory exists
    set /a VERIFICATION_PASSED+=1
) else (
    echo          [FAIL] frontend/ directory missing
    set /a VERIFICATION_FAILED+=1
)

if exist "frontend\src\services\websocket.ts" (
    echo          [PASS] WebSocket service exists
    set /a VERIFICATION_PASSED+=1
) else (
    echo          [FAIL] WebSocket service missing
    set /a VERIFICATION_FAILED+=1
)
echo.

:: Test 4: Virtual Environment
echo [TEST 4] Checking Python virtual environment...
if exist "venv_daena\Scripts\python.exe" (
    echo          [PASS] Virtual environment exists
    set /a VERIFICATION_PASSED+=1
) else (
    echo          [INFO] Virtual environment will be created on first run
    set /a VERIFICATION_PASSED+=1
)
echo.

:: Test 5: Node Modules
echo [TEST 5] Checking Node.js dependencies...
if exist "frontend\node_modules\" (
    echo          [PASS] node_modules exists
    
    :: Check for key dependencies
    if exist "frontend\node_modules\sonner\" (
        echo          [PASS] sonner package installed
        set /a VERIFICATION_PASSED+=1
    ) else (
        echo          [FAIL] sonner package missing
        set /a VERIFICATION_FAILED+=1
    )
    
    if exist "frontend\node_modules\zustand\" (
        echo          [PASS] zustand package installed
        set /a VERIFICATION_PASSED+=1
    ) else (
        echo          [INFO] zustand may be bundled
    )
) else (
    echo          [INFO] node_modules will be installed on first run
)
echo.

:: Test 6: Backend Files
echo [TEST 6] Checking backend super-sync files...
if exist "backend\routes\realtime.py" (
    echo          [PASS] realtime.py route exists
    set /a VERIFICATION_PASSED+=1
) else (
    echo          [FAIL] realtime.py route missing
    set /a VERIFICATION_FAILED+=1
)

if exist "backend\services\websocket_manager.py" (
    echo          [PASS] websocket_manager.py exists
    set /a VERIFICATION_PASSED+=1
) else (
    echo          [FAIL] websocket_manager.py missing
    set /a VERIFICATION_FAILED+=1
)

if exist "backend\services\ollama_scanner.py" (
    echo          [PASS] ollama_scanner.py exists
    set /a VERIFICATION_PASSED+=1
) else (
    echo          [FAIL] ollama_scanner.py missing
    set /a VERIFICATION_FAILED+=1
)
echo.

:: Test 7: Frontend Files
echo [TEST 7] Checking frontend super-sync files...
if exist "frontend\src\hooks\useRealtime.ts" (
    echo          [PASS] useRealtime.ts hook exists
    set /a VERIFICATION_PASSED+=1
) else (
    echo          [FAIL] useRealtime.ts hook missing
    set /a VERIFICATION_FAILED+=1
)

if exist "frontend\src\components\brain\OllamaScanner.tsx" (
    echo          [PASS] OllamaScanner.tsx component exists
    set /a VERIFICATION_PASSED+=1
) else (
    echo          [FAIL] OllamaScanner.tsx component missing
    set /a VERIFICATION_FAILED+=1
)
echo.

:: Test 8: Database Migration
echo [TEST 8] Checking database migration...
if exist "backend\database\migrations\001_add_missing_tables.py" (
    echo          [PASS] Database migration script exists
    set /a VERIFICATION_PASSED+=1
) else (
    echo          [FAIL] Database migration script missing
    set /a VERIFICATION_FAILED+=1
)
echo.

:: Test 9: Port Availability
echo [TEST 9] Checking port availability...
netstat -an | findstr ":8000" | findstr "LISTENING" >nul
if %errorlevel% neq 0 (
    echo          [PASS] Port 8000 is available
    set /a VERIFICATION_PASSED+=1
) else (
    echo          [WARN] Port 8000 is in use
)

netstat -an | findstr ":5173" | findstr "LISTENING" >nul
if %errorlevel% neq 0 (
    echo          [PASS] Port 5173 is available
    set /a VERIFICATION_PASSED+=1
) else (
    echo          [WARN] Port 5173 is in use
)
echo.

:: Summary
echo =====================================================
echo    VERIFICATION SUMMARY
echo =====================================================
echo.
echo Passed: %VERIFICATION_PASSED%
echo Failed: %VERIFICATION_FAILED%
echo.

if %VERIFICATION_FAILED% equ 0 (
    echo [SUCCESS] All critical tests passed!
    echo.
    echo You can now start Daena with: START_DAENA.bat
    echo.
) else (
    echo [WARNING] Some tests failed. Please review the issues above.
    echo.
    echo Some components may need to be installed on first run.
    echo.
)

pause
