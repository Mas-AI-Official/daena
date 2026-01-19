@echo off
REM ============================================================
REM DAENA PRODUCTION DEPLOYMENT (Windows)
REM ============================================================

echo ============================================================
echo   DAENA PRODUCTION DEPLOYMENT
echo ============================================================
echo.

REM Step 1: Pre-deployment checks
echo [1/7] Pre-deployment Checks
echo --------------------------------
python --version
if errorlevel 1 (
    echo ERROR: Python not found
    pause
    exit /b 1
)

if exist "venv_daena_main_py310\Scripts\python.exe" (
    echo   [+] Virtual environment found
) else (
    echo   [ERROR] Virtual environment not found
    echo   Run: python -m venv venv_daena_main_py310
    pause
    exit /b 1
)

if exist "daena.db" (
    echo   [+] Database found
) else (
    echo   [WARN] Database not found - will be created
)

REM Step 2: Install dependencies
echo.
echo [2/7] Installing Dependencies
echo --------------------------------
call venv_daena_main_py310\Scripts\activate.bat
pip install -r requirements.txt --quiet
echo   [+] Dependencies installed

REM Step 3: Run tests
echo.
echo [3/7] Running Production Tests
echo --------------------------------
python scripts\test_production_ready.py
if errorlevel 1 (
    echo   [ERROR] Tests failed - deployment aborted
    pause
    exit /b 1
)
echo   [+] All tests passed

REM Step 4: Create backup
echo.
echo [4/7] Creating Backup
echo --------------------------------
set timestamp=%DATE:~-4,4%%DATE:~-7,2%%DATE:~-10,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%
set timestamp=%timestamp: =0%
set backup_dir=backups\pre_deployment_%timestamp%
mkdir "%backup_dir%"

if exist "daena.db" (
    copy daena.db "%backup_dir%\" >nul
    echo   [+] Database backed up
)

if exist "backend\config\settings.py" (
    copy backend\config\settings.py "%backup_dir%\" >nul
    echo   [+] Configuration backed up
)

echo   [+] Backup created: %backup_dir%

REM Step 5: Environment configuration
echo.
echo [5/7] Environment Configuration
echo --------------------------------
if exist ".env" (
    echo   [+] .env file found
) else (
    echo   [*] Creating .env template...
    (
        echo # Daena Production Configuration
        echo ENVIRONMENT=production
        echo DISABLE_AUTH=0
        echo BACKEND_PORT=8000
        echo AUDIO_PORT=5001
        echo OLLAMA_HOST=http://127.0.0.1:11434
        echo DEFAULT_MODEL=deepseek-r1:8b
        echo DAENA_CREATOR=Masoud
        echo.
        echo # Database
        echo DATABASE_URL=sqlite:///./daena.db
        echo.
        echo # Security (CHANGE THESE!)
        echo SECRET_KEY=your-secret-key-here
        echo JWT_SECRET=your-jwt-secret-here
    ) > .env
    echo   [+] .env created - UPDATE SECRET KEYS!
)

REM Step 6: Database initialization
echo.
echo [6/7] Database Initialization
echo --------------------------------
python -c "from backend.database import init_db; init_db(); print('[+] Database initialized')" 2>nul
if errorlevel 1 (
    echo   [WARN] Database already initialized or error
)

REM Step 7: Start services
echo.
echo [7/7] Starting Services
echo --------------------------------
echo.
echo Starting Daena...
echo.
echo Dashboard available at:
echo   - http://localhost:8000/ui/daena-office
echo   - API Docs: http://localhost:8000/docs
echo.
echo Press Ctrl+C to stop
echo.

REM Start the application
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --log-level info

echo.
echo ============================================================
echo   Deployment Complete!
echo ============================================================
pause
