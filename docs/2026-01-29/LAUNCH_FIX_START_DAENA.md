# START_DAENA.bat Launch Fix (2026-01-29)

## Problem

- **Auto-close**: The launcher or backend window closed immediately when double-clicking `START_DAENA.bat`.
- **Causes**: (1) Nested double quotes in the backend `start` command broke the command string. (2) When double-clicked, Windows runs the batch with `cmd /c`, so when the script exited the window closed. (3) LF-only line endings in the batch file can cause "corrupt" behavior on Windows (batch expects CRLF). (4) PowerShell port-finding (`for /f`) could fail and cause odd behavior.

## Fixes Applied

### 1. Backend and audio launcher helpers (no nested quotes)

- **`_daena_backend_launcher.bat`** (project root): Started by `START_DAENA.bat` with `start "DAENA - BACKEND" cmd /k call "%ROOT%_daena_backend_launcher.bat" %BACKEND_PORT%. The helper uses `%~dp0` to get the project root, finds the venv (main or audio), sets `PYTHONPATH=%ROOT%;%ROOT%\backend`, activates the venv, and runs `uvicorn backend.main:app --port %PORT%`. No quotes inside the `start` string.
- **`_daena_audio_launcher.bat`** (project root): Same idea for the audio service; started with `start "DAENA - AUDIO" cmd /k call "%ROOT%_daena_audio_launcher.bat" %AUDIO_PORT%`.

### 2. Keep launcher window open when double-clicked

- At the top of `START_DAENA.bat`: when no argument is passed (double-click), re-launch with `cmd /k "%~f0" keepopen` so the script runs in a window that stays open. The user can read all output; after "Press any key...", the window remains open with the prompt.

### 3. No PowerShell port-finding

- Removed the `for /f` PowerShell port probe; use fixed `BACKEND_PORT=8000` to avoid `for /f` or PowerShell failures that could corrupt startup.

### 4. Line endings (CRLF)

- Converted `START_DAENA.bat`, `_daena_backend_launcher.bat`, and `_daena_audio_launcher.bat` to CRLF so Windows batch runs correctly (LF-only can cause "terminate batch job?" or broken parsing).

### 5. Scripts alignment

- **`scripts\start_backend.bat`**: Prefer `venv_daena_main_py310`, fallback to `venv_daena_audio_py310`; set `PYTHONPATH=%PROJECT_ROOT%;%PROJECT_ROOT%\backend` before running uvicorn.
- **`scripts\quick_start_backend.bat`** and **`scripts\simple_start_backend.bat`**: Set `PYTHONPATH=%PROJECT_ROOT%;%PROJECT_ROOT%\backend` so `config` and `backend` resolve when running from `scripts\`.

### 6. Audio venv check path

- In `START_DAENA.bat`, the audio venv check now uses `%ROOT%venv_daena_audio_py310\...` so it works when `ROOT` has a trailing backslash.

## How to run

1. Double-click **`START_DAENA.bat`** (or run from cmd in the project root).
2. The launcher window stays open and shows progress; at the end it says “Press any key to close this launcher window…” (backend and audio keep running in their own windows).
3. The **DAENA - BACKEND** window runs `_daena_backend_launcher.bat`; it stays open with `cmd /k` and shows either the uvicorn log or any Python/import error.
4. If the backend fails with **`ModuleNotFoundError: No module named 'pydantic_settings'`** (or similar), install backend deps in the venv you use:
   - `venv_daena_main_py310\Scripts\pip install -r backend\requirements.txt`
   - or use the main venv: create `venv_daena_main_py310` and install from `backend\requirements.txt` so `START_DAENA.bat` picks it first.

## Backend / frontend sync

- Backend is served from the same process (uvicorn) and serves UI routes and static files; no separate frontend build is required for the current setup.
- After changing backend or frontend, restart the backend window (or use `--reload` which is already in the launcher).
