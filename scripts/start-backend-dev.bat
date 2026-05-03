@echo off
setlocal enabledelayedexpansion
:: ============================================================
:: Daena - Dev Backend Launcher (Windows, .venv-pinned, no reload)
:: ============================================================
:: PURPOSE
::   Starts the FastAPI backend on Windows in a way that AVOIDS
::   uvicorn's --reload worker bug, which on Windows can spawn the
::   worker through C:\PythonXX\python.exe (system Python) instead
::   of .venv\Scripts\python.exe. Symptoms when that bug fires:
::     - Worker can't import sqlalchemy / pydantic
::     - Routes silently don't load
::     - Prior worker keeps serving stale code
::     - "I changed code but the API never updates" with no error
::
::   This launcher pins the .venv interpreter and runs uvicorn
::   directly with NO reloader -- the verified-working pattern from
::   the Phase 2 live smoke (see DEV_BACKEND_LAUNCHER_STABILITY_REPORT.md).
::
:: SCOPE (intentionally narrow)
::   - Backend ONLY. Does NOT start frontend, llama-server, or WSL.
::   - Does NOT touch production deploy files.
::   - Does NOT modify .env, vault, or any persistent state.
::   - Does NOT change runtime behavior of the backend itself --
::     only how the process is launched.
::
:: ALTERNATIVES (still supported, unchanged)
::   - start-daena.bat       full dev env (WSL backend + frontend + llama)
::   - backend\run.py        legacy entrypoint (uses settings.debug -> reload)
:: ============================================================

title Daena Dev Backend [.venv pinned, no-reload]
color 0B

:: --- Resolve repo root (this script lives in <repo>\scripts\) ---
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
pushd "%SCRIPT_DIR%\.." >NUL
for %%I in (.) do set "ROOT=%%~fI"
popd >NUL

set "BACKEND=%ROOT%\backend"
set "VENV_PY=%BACKEND%\.venv\Scripts\python.exe"
set "PORT=8000"
set "PORT_FILE=%BACKEND%\.daena-port"

echo.
echo  ============================================
echo   DAENA DEV BACKEND (Windows, .venv pinned)
echo  ============================================
echo   Repo:    %ROOT%
echo   Backend: %BACKEND%
echo   Python:  %VENV_PY%
echo   Port:    %PORT%
echo  ============================================
echo.

:: --- 1. Sanity check the venv ---
if not exist "%VENV_PY%" (
    echo  [ERROR] .venv interpreter not found at:
    echo          %VENV_PY%
    echo.
    echo          Run setup-daena.bat first, or recreate the venv:
    echo          cd "%BACKEND%" ^&^& py -m venv .venv ^&^& .venv\Scripts\python.exe -m pip install -r requirements.txt
    exit /b 1
)

:: --- 2. Release port 8000 if a stale uvicorn / python still owns it ---
:: Two-pass kill is required:
::   Pass A: kill ANY python.exe whose CommandLine references
::           "uvicorn app.main:app". On Windows venvs the LISTENING
::           socket is owned by the venv-launcher parent (which
::           re-exec'd the base interpreter); netstat reports the
::           CHILD PID. Killing only the netstat PID leaves the
::           parent holding the socket and the next bind fails with
::           WinError 10048.
::   Pass B: backstop -- kill anything still holding :%PORT% by netstat.
::
:: Sleep idiom: ping -n N 127.0.0.1 (waits ~N-1 seconds). We use ping
:: because Windows `timeout.exe` collides on PATH with GNU coreutils
:: `timeout` when this script is invoked via WSL / Git-bash shells.
echo  [1/3] Releasing port %PORT% if held...
:: Pass A: PowerShell helper kills any python.exe whose CommandLine
:: references "uvicorn app.main:app" (parent venv-launcher AND child
:: base-interpreter). Helper file avoids the cmd quoting hell that
:: silently breaks inline -Command in `for /f`.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT_DIR%\_dev_kill_uvicorn.ps1"
:: Pass B: backstop -- anything still listening on %PORT%.
set "KILLED_ANY=0"
for /f "tokens=5" %%a in ('netstat -aon 2^>NUL ^| findstr ":%PORT%.*LISTENING"') do (
    echo        Pass B backstop kill PID %%a (still held :%PORT%)
    taskkill /PID %%a /F /T >NUL 2>&1
    set "KILLED_ANY=1"
)
:: Always settle ~2s so Windows fully releases the socket before bind.
:: Use ping idiom; Windows `timeout.exe` is shadowed by GNU coreutils
:: when this script is invoked from WSL / Git-bash shells.
ping -n 3 127.0.0.1 >NUL

:: Clear stale .daena-port file so the frontend / health-check
:: cannot follow it to a dead listener.
if exist "%PORT_FILE%" (
    del "%PORT_FILE%" >NUL 2>NUL
    echo        Cleared stale %PORT_FILE%
)

:: --- 3. Launch uvicorn directly (no reloader, single process) ---
echo  [2/3] Starting uvicorn (no-reload, single process)...
echo.
echo        Command:
echo          "%VENV_PY%" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT% --no-access-log
echo.
echo        Tip: edit-then-restart loop. No auto-reload by design.
echo  [3/3] Handing off to uvicorn; live logs follow.
echo  ============================================
echo.

cd /d "%BACKEND%"
"%VENV_PY%" -m uvicorn app.main:app --host 127.0.0.1 --port %PORT% --no-access-log
set "EXIT_CODE=!ERRORLEVEL!"

echo.
echo  ============================================
echo   uvicorn exited with code !EXIT_CODE!
echo  ============================================
exit /b !EXIT_CODE!
