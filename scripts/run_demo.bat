@echo off
REM Daena Demo Runner
REM Captures screenshots and optional screen recording.
REM
REM Usage: scripts\run_demo.bat [screenshots|record|both]
REM   screenshots - Headless Playwright screenshots only (default)
REM   record      - Headed browser with screen recording
REM   both        - Screenshots first, then recording

setlocal
set MODE=%1
if "%MODE%"=="" set MODE=screenshots

echo ============================================
echo  Daena Demo: %MODE%
echo ============================================
echo.

REM Check backend
curl -s -o nul http://127.0.0.1:8000/api/v1/health >nul 2>&1
if %errorlevel% neq 0 (
    echo [preflight] Backend: NOT RUNNING
    echo Start it first: start-backend.bat
    exit /b 1
)
echo [preflight] Backend: OK

REM Check frontend (try multiple addresses)
curl -s -o nul http://localhost:5173 >nul 2>&1
if %errorlevel% neq 0 (
    curl -s -o nul http://127.0.0.1:5173 >nul 2>&1
    if %errorlevel% neq 0 (
        echo [preflight] Frontend: NOT RUNNING
        echo Start it first: cd frontend ^&^& npm run dev
        exit /b 1
    )
)
echo [preflight] Frontend: OK
echo.

if "%MODE%"=="screenshots" goto do_screenshots
if "%MODE%"=="record" goto do_record
if "%MODE%"=="both" goto do_both
echo Unknown mode: %MODE%
exit /b 1

:do_screenshots
echo Running screenshot capture...
python D:\Ideas\Daena\scripts\demo_scenario.py
goto done

:do_record
echo Running screen recording + browser automation...
python D:\Ideas\Daena\scripts\record_demo.py
goto done

:do_both
echo Phase 1: Screenshots...
python D:\Ideas\Daena\scripts\demo_scenario.py
echo.
echo Phase 2: Screen recording...
python D:\Ideas\Daena\scripts\record_demo.py
goto done

:done
echo.
echo Output locations:
echo   Screenshots: D:\Ideas\Daena\Doc\demo\screenshots\
echo   Recording:   D:\Ideas\Daena\Doc\demo\
echo.
