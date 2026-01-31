@echo off
REM Daena Windows Node - start local "hands" server (127.0.0.1:18888)
REM Optional: set WINDOWS_NODE_TOKEN=your-secret
REM Optional: set EXECUTION_WORKSPACE_ROOT=D:\Ideas\Daena_old_upgrade_20251213

set "NODEDIR=%~dp0"
set "PROJECT_ROOT=%NODEDIR%..\.."
cd /d "%NODEDIR%"
if not defined EXECUTION_WORKSPACE_ROOT set "EXECUTION_WORKSPACE_ROOT=%PROJECT_ROOT%"
set "PYTHONPATH=%PROJECT_ROOT%;%PROJECT_ROOT%\backend;%PYTHONPATH%"
echo Starting Daena Windows Node at http://127.0.0.1:18888
python -m uvicorn node_server:app --host 127.0.0.1 --port 18888
pause
