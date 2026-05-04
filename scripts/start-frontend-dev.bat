@echo off
setlocal enabledelayedexpansion
:: ============================================================
:: Daena - Dev Frontend Launcher (Windows, path-scoped cleanup)
:: ============================================================
:: PURPOSE
::   Starts the Vite dev server cleanly. Before launching it kills
::   ONLY stale Vite/Node processes scoped to THIS repo's frontend
::   directory (D:\Ideas\Daena\frontend). It will NOT kill unrelated
::   node.exe processes (contentops dashboards, MCP servers, llama
::   bridges, other Vite projects) -- the path-scoped helper checks
::   the process CommandLine for the repo path before killing.
::
:: SCOPE (intentionally narrow)
::   - Frontend ONLY. Does NOT touch backend.
::   - Does NOT modify .env or any persistent state.
::   - Does NOT install dependencies (run setup-daena.bat for that).
:: ============================================================

title Daena Dev Frontend [path-scoped]
color 0E

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
pushd "%SCRIPT_DIR%\.." >NUL
for %%I in (.) do set "ROOT=%%~fI"
popd >NUL

set "FRONTEND=%ROOT%\frontend"
set "PORT=5173"

echo.
echo  ============================================
echo   DAENA DEV FRONTEND (Windows, path-scoped)
echo  ============================================
echo   Repo:     %ROOT%
echo   Frontend: %FRONTEND%
echo   Port:     %PORT%
echo  ============================================
echo.

if not exist "%FRONTEND%\package.json" (
    echo  [ERROR] No package.json at %FRONTEND%
    echo          Cannot find the frontend project.
    exit /b 1
)

:: --- 1. Path-scoped cleanup of stale Vite ---
echo  [1/3] Releasing port %PORT% if held by stale Vite for THIS repo...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%\_dev_kill_frontend.ps1"
ping -n 3 127.0.0.1 >NUL

:: --- 2. Verify npm available ---
echo  [2/3] Verifying npm...
where npm >NUL 2>NUL
if !ERRORLEVEL! NEQ 0 (
    echo  [ERROR] npm not found on PATH.
    echo          Install Node.js from https://nodejs.org/
    exit /b 1
)

:: --- 3. Launch Vite dev server ---
echo  [3/3] Starting Vite dev server...
echo  ============================================
echo.

cd /d "%FRONTEND%"
call npm run dev
set "EXIT_CODE=!ERRORLEVEL!"

echo.
echo  ============================================
echo   Vite exited with code !EXIT_CODE!
echo  ============================================
exit /b !EXIT_CODE!
