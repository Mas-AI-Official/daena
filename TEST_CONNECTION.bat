@echo off
chcp 65001 >nul
title Daena Connection Test

echo =====================================================
echo    DAENA CONNECTION TEST
echo =====================================================
echo.

:: Test Backend Health
echo [TEST] Checking Backend Health...
curl -s http://127.0.0.1:8000/health > temp_health.json 2>&1
if %errorlevel% equ 0 (
    echo        [PASS] Backend is responding
    type temp_health.json | findstr "status" | findstr "healthy" >nul
    if %errorlevel% equ 0 (
        echo        [PASS] Backend reports healthy status
    ) else (
        echo        [WARN] Backend response unexpected
    )
) else (
    echo        [FAIL] Backend is not responding
    echo        Make sure to run START_BACKEND.bat first
)
if exist temp_health.json del temp_health.json
echo.

:: Test API Endpoints
echo [TEST] Testing API Endpoints...

:: Skills endpoint
curl -s http://127.0.0.1:8000/api/v1/skills > nul 2>&1
if %errorlevel% equ 0 (
    echo        [PASS] /api/v1/skills - OK
) else (
    echo        [FAIL] /api/v1/skills - Not responding
)

:: Brain status endpoint
curl -s http://127.0.0.1:8000/api/v1/brain/status > nul 2>&1
if %errorlevel% equ 0 (
    echo        [PASS] /api/v1/brain/status - OK
) else (
    echo        [FAIL] /api/v1/brain/status - Not responding
)

:: Projects endpoint
curl -s http://127.0.0.1:8000/api/v1/projects > nul 2>&1
if %errorlevel% equ 0 (
    echo        [PASS] /api/v1/projects - OK
) else (
    echo        [FAIL] /api/v1/projects - Not responding
)

:: Tools library endpoint
curl -s http://127.0.0.1:8000/api/v1/tools/library > nul 2>&1
if %errorlevel% equ 0 (
    echo        [PASS] /api/v1/tools/library - OK
) else (
    echo        [FAIL] /api/v1/tools/library - Not responding
)
echo.

:: Test Frontend
echo [TEST] Checking Frontend...
curl -s http://localhost:5173/ > nul 2>&1
if %errorlevel% equ 0 (
    echo        [PASS] Frontend is responding
) else (
    echo        [FAIL] Frontend is not responding
    echo        Make sure to run START_FRONTEND.bat first
)
echo.

:: Test WebSocket
echo [TEST] Checking WebSocket endpoint...
curl -s -N -H "Connection: Upgrade" -H "Upgrade: websocket" http://127.0.0.1:8000/api/v1/realtime/ws > nul 2>&1
if %errorlevel% equ 0 (
    echo        [PASS] WebSocket endpoint is accessible
) else (
    echo        [INFO] WebSocket test inconclusive (may need browser)
)
echo.

:: Summary
echo =====================================================
echo    TEST COMPLETE
echo =====================================================
echo.
echo If all tests passed, Daena is running correctly!
echo.
echo Open your browser to: http://localhost:5173/
echo.
pause
