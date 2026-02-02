@echo off

REM Helper launcher for DAENA backend - avoids nested quotes when started from START_DAENA.bat

REM Usage: run from project root, optional arg: port (default 8000)

setlocal EnableExtensions



set "ROOT=%~dp0"

if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"



set "PORT=%~1"

if "%PORT%"=="" set "PORT=8000"



cd /d "%ROOT%"

if errorlevel 1 (

    echo [ERROR] Cannot cd to %ROOT%

    pause

    exit /b 1

)



set "PYTHONPATH=%ROOT%;%ROOT%\backend"

set "DISABLE_AUTH=1"

if defined MODELS_ROOT set "OLLAMA_MODELS=%MODELS_ROOT%\ollama"

if defined MODELS_ROOT set "TTS_HOME=%MODELS_ROOT%\xtts"

if defined HF_HOME set "TRANSFORMERS_CACHE=%HF_HOME%\transformers"

if defined QA_GUARDIAN_ENABLED set "QA_GUARDIAN_ENABLED=%QA_GUARDIAN_ENABLED%"

if defined QA_GUARDIAN_AUTO_FIX set "QA_GUARDIAN_AUTO_FIX=%QA_GUARDIAN_AUTO_FIX%"

if defined QA_GUARDIAN_KILL_SWITCH set "QA_GUARDIAN_KILL_SWITCH=%QA_GUARDIAN_KILL_SWITCH%"

REM Hands (OpenClaw Gateway): prefer DAENABOT_HANDS_*; fallback OPENCLAW_GATEWAY_*
if defined DAENABOT_HANDS_URL set "DAENABOT_HANDS_URL=%DAENABOT_HANDS_URL%"
if defined DAENABOT_HANDS_TOKEN set "DAENABOT_HANDS_TOKEN=%DAENABOT_HANDS_TOKEN%"
if defined OPENCLAW_GATEWAY_URL set "OPENCLAW_GATEWAY_URL=%OPENCLAW_GATEWAY_URL%"
if defined OPENCLAW_GATEWAY_TOKEN set "OPENCLAW_GATEWAY_TOKEN=%OPENCLAW_GATEWAY_TOKEN%"
REM Skill import path (optional): scan .py for SKILL_MANIFEST and register skills
if defined DAENA_SKILL_IMPORT_PATH set "DAENA_SKILL_IMPORT_PATH=%DAENA_SKILL_IMPORT_PATH%"

set "VENV_BACKEND="

if exist "%ROOT%\venv_daena_main_py310\Scripts\python.exe" set "VENV_BACKEND=%ROOT%\venv_daena_main_py310"

if not defined VENV_BACKEND if exist "%ROOT%\venv_daena_audio_py310\Scripts\python.exe" set "VENV_BACKEND=%ROOT%\venv_daena_audio_py310"

if not defined VENV_BACKEND (

    echo [ERROR] No Python venv found in %ROOT%

    pause

    exit /b 1

)



call "%VENV_BACKEND%\Scripts\activate.bat"

if errorlevel 1 (

    echo [ERROR] Failed to activate venv

    pause

    exit /b 1

)



echo [DAENA BACKEND] Root: %ROOT%

echo [DAENA BACKEND] Port: %PORT%

echo [DAENA BACKEND] Python: %VENV_BACKEND%
echo [DAENA BACKEND] Dashboard: http://127.0.0.1:%PORT%/ui/dashboard
echo [DAENA BACKEND] Daena Office: http://127.0.0.1:%PORT%/ui/daena-office
echo [DAENA BACKEND] Projects: http://127.0.0.1:%PORT%/ui/projects
echo [DAENA BACKEND] Councils: http://127.0.0.1:%PORT%/ui/councils
echo [DAENA BACKEND] Workspace: http://127.0.0.1:%PORT%/ui/workspace
echo [DAENA BACKEND] Analytics: http://127.0.0.1:%PORT%/ui/analytics
echo [DAENA BACKEND] Agents: http://127.0.0.1:%PORT%/ui/agents
echo [DAENA BACKEND] Control Panel: http://127.0.0.1:%PORT%/ui/control-panel
echo [DAENA BACKEND] Brain ^& API: http://127.0.0.1:%PORT%/ui/brain-settings
echo [DAENA BACKEND] Web3 / DeFi: http://127.0.0.1:%PORT%/ui/web3
echo [DAENA BACKEND] Founder: http://127.0.0.1:%PORT%/ui/founder-panel
echo [DAENA BACKEND] Wiring audit API: http://127.0.0.1:%PORT%/api/v1/ui/wiring-audit
echo [DAENA BACKEND] Set EXECUTION_TOKEN in env for execution-layer.

echo.



python -m uvicorn backend.main:app --host 127.0.0.1 --port %PORT% --reload

echo.

echo Backend stopped. Press any key to close.

pause >nul

