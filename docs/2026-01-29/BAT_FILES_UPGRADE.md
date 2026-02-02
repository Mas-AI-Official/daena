# Batch Files Upgrade (2026-01-29)

## Changes

### START_DAENA.bat
- **Port fallback**: Default `BACKEND_PORT=8000` if PowerShell port finder fails; port finder limited to 8000–8009.
- **Dual venv**: Uses `venv_daena_main_py310` if present, otherwise `venv_daena_audio_py310` for backend. Sets `VENV_BACKEND` and uses it in the backend start command.
- **PLAYWRIGHT**: Path set only if `venv_daena_main_py310\Lib\site-packages\playwright` exists.
- **Backend start**: Uses `call "%VENV_BACKEND%\Scripts\activate.bat"`, `PYTHONPATH=%ROOT%`, and quoted `%ROOT%` in `cd /d`.
- **URLs**: Startup message now lists Dashboard, Incident Room, App Setup, QA Guardian, CMP Canvas, Control Center, Voice Diagnostics.

### start_xtts.bat
- **ROOT**: Trailing backslash removed only when present (`if "%ROOT:~-1%"=="\"`).
- **TTS server**: If `config.json` is missing under `XTTS_PATH`, starts server without `--config_path`.

### scripts/START_OLLAMA.bat
- **PROJECT_ROOT**: Set from script location (`%~dp0` → `cd ..` → `%CD%`) so it works from any drive/folder.

### scripts/start_backend.bat
- **BACKEND_LOG**: Spaces in `%TIME%` replaced with `0` so log path has no spaces.

### scripts/quick_start_backend.bat, scripts/simple_start_backend.bat
- **Dual venv**: Try `venv_daena_main_py310` first, then `venv_daena_audio_py310`.
- **PYTHONPATH**: Set to project root so `backend.main` imports correctly.
- **PROJECT_ROOT**: Set explicitly after `cd /d "%~dp0.."`.

## Usage

- Run **START_DAENA.bat** from the project root. It will start Ollama (if not running), backend, and optionally audio; then open the dashboard.
- Run **start_xtts.bat** from project root for XTTS voice server (optional).
- Run **scripts\START_OLLAMA.bat** from anywhere to start Ollama with MODELS_ROOT.
- Run **scripts\quick_start_backend.bat** or **scripts\simple_start_backend.bat** for backend-only start (from scripts folder or project root).
