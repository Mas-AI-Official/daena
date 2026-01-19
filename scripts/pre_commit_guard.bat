@echo off
REM Pre-commit guard: runs verify scripts and blocks if they fail
REM This prevents committing/launching with truncation or duplicates

setlocal

echo ========================================
echo   PRE-COMMIT GUARD - Daena Code Quality
echo ========================================
echo.

set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%\.."

REM Check for Python
set "PY_MAIN=venv_daena_main_py310\Scripts\python.exe"
if not exist "%PY_MAIN%" (
    echo [WARNING] venv not found, using system python
    set "PY_MAIN=python"
)

REM Run truncation check
echo [1/2] Checking for truncation markers...
"%PY_MAIN%" scripts\verify_no_truncation.py
if errorlevel 1 (
    echo.
    echo [FATAL] Truncation markers detected! Fix before proceeding.
    echo.
    pause
    exit /b 1
)
echo [OK] No truncation markers found
echo.

REM Run duplicate check
echo [2/2] Checking for duplicate modules...
"%PY_MAIN%" scripts\verify_no_duplicates.py
if errorlevel 1 (
    echo.
    echo [FATAL] Duplicate modules detected! Fix before proceeding.
    echo.
    pause
    exit /b 1
)
echo [OK] No duplicate modules found
echo.

echo ========================================
echo   ✅ ALL GUARDRAILS PASSED
echo ========================================
echo.

endlocal
exit /b 0









