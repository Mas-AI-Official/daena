@echo off
cd /d D:\Ideas\Daena_old_upgrade_20251213
call venv_daena_main_py310\Scripts\activate.bat
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
