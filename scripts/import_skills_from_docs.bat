@echo off
setlocal EnableExtensions
REM Import skills from a docs folder: scan *.py for SKILL_MANIFEST or infer metadata.
REM Set DAENA_SKILL_IMPORT_PATH to override default folder (optional).

cd /d "%~dp0.."
set "PROJECT_ROOT=%CD%"
set "PYTHONPATH=%PROJECT_ROOT%"

if "%DAENA_SKILL_IMPORT_PATH%"=="" set "DAENA_SKILL_IMPORT_PATH=%PROJECT_ROOT%\docs\2026-01-31\new files"
echo DAENA_SKILL_IMPORT_PATH=%DAENA_SKILL_IMPORT_PATH%

set "PY="
if exist "%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe" set "PY=%PROJECT_ROOT%\venv_daena_main_py310\Scripts\python.exe"
if not defined PY if exist "%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe" set "PY=%PROJECT_ROOT%\venv_daena_audio_py310\Scripts\python.exe"
if not defined PY set "PY=python"

echo Running skill importer (no code execution, ast-only)...
"%PY%" -m backend.scripts.import_skills_from_docs
set "EXIT_CODE=%ERRORLEVEL%"
if %EXIT_CODE% neq 0 (
    echo Import failed. Check path and .py files.
    exit /b %EXIT_CODE%
)
echo Done.
exit /b 0
