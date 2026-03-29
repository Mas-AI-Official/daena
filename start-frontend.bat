@echo off
setlocal enabledelayedexpansion
title Daena Frontend
color 0B

:: ============================================================
:: Daena Frontend Launcher
:: Runs Vite dev server with HMR
:: ============================================================

:: Detect project root from bat location
set "ROOT=%~dp0"
set "ROOT=%ROOT:~0,-1%"
set "FRONTEND=%ROOT%\frontend"

echo.
echo  ============================================
echo   DAENA FRONTEND
echo  ============================================
echo.

:: Check Node.js
where node >nul 2>nul
if errorlevel 1 (
    echo  [ERROR] Node.js not found in PATH.
    echo          Install Node.js 18+ from https://nodejs.org
    pause
    exit /b 1
)

:: Show Node version
for /f "tokens=*" %%v in ('node --version') do echo  Node.js: %%v

:: Check frontend dir
if not exist "%FRONTEND%\package.json" (
    echo  [ERROR] Frontend not found at %FRONTEND%
    echo          Run setup-daena.bat first.
    pause
    exit /b 1
)

:: Check node_modules
if not exist "%FRONTEND%\node_modules" (
    echo  [WARN] node_modules not found. Running npm install...
    cd /d "%FRONTEND%"
    npm install
    if errorlevel 1 (
        echo  [ERROR] npm install failed.
        pause
        exit /b 1
    )
)

:: Start Vite dev server
echo  [1/1] Starting Vite dev server on http://localhost:5173 ...
echo.
echo  App:     http://localhost:5173
echo  API:     proxied to http://localhost:8000/api
echo  ============================================
echo.

cd /d "%FRONTEND%"
npm run dev

pause
