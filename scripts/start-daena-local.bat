@echo off
setlocal enabledelayedexpansion
:: ============================================================
:: Daena - One-Click Local Start (Sprint-7 PR-1, 2026-05-04)
:: ============================================================
:: PURPOSE
::   ONE command to take Masoud from "laptop powered on" to
::   "Daena ready in browser". Wraps the existing safe launchers:
::
::     1) cleanup-stale-dev.ps1  (path-scoped cleanup; never kills
::        unrelated python.exe / node.exe outside this repo)
::     2) start-backend-dev.bat  (uvicorn no-reload, .venv pinned)
::     3) start-frontend-dev.bat (Vite, path-scoped Node cleanup)
::     4) Poll /health and / 5173 for up to ~30s each
::     5) Print URLs + next-action hints
::
:: WHAT THIS SCRIPT DOES NOT DO
::   * Does NOT run pip install / npm install (use setup-daena.bat)
::   * Does NOT touch .env, vault, or production deploy targets
::   * Does NOT use uvicorn --reload (Windows worker bug)
::   * Does NOT kill processes outside this repo's process tree
::   * Does NOT modify connector config, DB, or governance state
::   * Does NOT auto-OAuth or auto-install MCPs
::
:: USAGE
::   Double-click  scripts\start-daena-local.bat
::   or            scripts\start-daena-local.bat   from a shell
:: ============================================================

title Daena One-Click Local Start
color 0A

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
pushd "%SCRIPT_DIR%\.." >NUL
for %%I in (.) do set "ROOT=%%~fI"
popd >NUL

echo.
echo  ============================================
echo   DAENA - ONE-CLICK LOCAL START
echo  ============================================
echo   Repo: %ROOT%
echo  ============================================
echo.

:: --- Step 1: Path-scoped cleanup of stale Daena dev processes ---
echo  [1/5] Cleaning stale Daena dev processes (path-scoped)...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%\cleanup-stale-dev.ps1"
echo.

:: --- Step 2: Start backend in its own window ---
echo  [2/5] Starting backend in a new window...
start "Daena Backend" cmd /c ""%SCRIPT_DIR%\start-backend-dev.bat""
:: Settle so the new window has a chance to print its banner before
:: we start spamming health probes from this window.
ping -n 4 127.0.0.1 >NUL

:: --- Step 3: Start frontend in its own window ---
echo  [3/5] Starting frontend in a new window...
start "Daena Frontend" cmd /c ""%SCRIPT_DIR%\start-frontend-dev.bat""
ping -n 3 127.0.0.1 >NUL

:: --- Step 4: Wait for backend /health (poll up to ~30s) ---
echo.
echo  [4/5] Waiting for backend /health on 127.0.0.1:8000 (up to ~30s)...
set "BACKEND_OK=0"
for /l %%i in (1,1,15) do (
    curl -s -f -o NUL http://127.0.0.1:8000/health >NUL 2>&1
    if !ERRORLEVEL! EQU 0 (
        set "BACKEND_OK=1"
        goto :backend_done
    )
    ping -n 3 127.0.0.1 >NUL
)
:backend_done
if "!BACKEND_OK!"=="1" (
    echo        Backend healthy.
) else (
    echo        [WARN] Backend did not respond on /health within ~30s.
)

:: --- Step 5: Wait for frontend (poll up to ~30s) ---
echo.
echo  [5/5] Waiting for frontend on 127.0.0.1:5173 (up to ~30s)...
set "FRONTEND_OK=0"
for /l %%i in (1,1,15) do (
    curl -s -f -o NUL http://127.0.0.1:5173 >NUL 2>&1
    if !ERRORLEVEL! EQU 0 (
        set "FRONTEND_OK=1"
        goto :frontend_done
    )
    ping -n 3 127.0.0.1 >NUL
)
:frontend_done
if "!FRONTEND_OK!"=="1" (
    echo        Frontend reachable.
) else (
    echo        [WARN] Frontend did not respond within ~30s.
)

echo.
echo  ============================================
echo   DAENA LOCAL START - SUMMARY
echo  ============================================
if "!BACKEND_OK!"=="1" if "!FRONTEND_OK!"=="1" (
    echo   Status: READY
    echo.
    echo   URLs:
    echo     Backend:        http://127.0.0.1:8000
    echo     Health:         http://127.0.0.1:8000/health
    echo     Self-diagnostic: http://127.0.0.1:8000/api/v1/system/self-diagnostic ^(auth required^)
    echo     OpenAPI:        http://127.0.0.1:8000/docs
    echo     Frontend:       http://127.0.0.1:5173
    echo     Connections:    http://127.0.0.1:5173/connections
    echo.
    echo   Next: open http://127.0.0.1:5173/connections to begin.
) else (
    echo   Status: PARTIAL - one or more services did not come up
    echo.
    if "!BACKEND_OK!"=="0" (
        echo   * Backend is NOT responding. Check the "Daena Backend" window for errors.
        echo     Common causes:
        echo       - Port 8000 still held -- rerun:
        echo           powershell -File scripts\cleanup-stale-dev.ps1
        echo       - .venv missing dependencies -- run:
        echo           cd backend ^&^& .venv\Scripts\python.exe -m pip install -r requirements.txt
        echo       - DB migrations needed -- run:
        echo           cd backend ^&^& .venv\Scripts\python.exe -m alembic upgrade head
    )
    if "!FRONTEND_OK!"=="0" (
        echo   * Frontend is NOT responding. Check the "Daena Frontend" window for errors.
        echo     Common causes:
        echo       - npm install needed: cd frontend ^&^& npm install
        echo       - Port 5173 held by another Vite project (cleanup-stale-dev.ps1
        echo         only touches THIS repo's frontend; cross-repo Vite needs
        echo         manual stop in its own dev window).
    )
)
echo  ============================================
echo.

exit /b 0
