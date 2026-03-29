@echo off
REM ==============================================================
REM Daena Local Docker Deployment
REM ==============================================================
REM Builds and starts all services locally using Docker Compose.
REM ==============================================================

echo [Daena] Starting local Docker deployment...

cd /d "%~dp0.."

REM Check Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo [Daena] ERROR: Docker is not running. Start Docker Desktop first.
    exit /b 1
)

REM Check .env.production exists
if not exist ".env.production" (
    echo [Daena] WARNING: .env.production not found. Copying from example...
    copy ".env.production.example" ".env.production"
    echo [Daena] IMPORTANT: Edit .env.production with real secrets before production use.
)

REM Build and start
echo [Daena] Building Docker image (multi-stage: frontend + backend)...
docker compose build --no-cache

echo [Daena] Starting services...
docker compose up -d

REM Wait for health check
echo [Daena] Waiting for health check...
set RETRIES=0
:healthloop
if %RETRIES% GEQ 30 (
    echo [Daena] ERROR: Health check failed after 30 attempts.
    docker compose logs daena
    exit /b 1
)
timeout /t 2 /nobreak >nul
curl -sf http://localhost:8000/health >nul 2>&1
if errorlevel 1 (
    set /a RETRIES+=1
    echo [Daena] Waiting... (attempt %RETRIES%/30)
    goto healthloop
)

echo.
echo ============================================
echo [Daena] All services running!
echo [Daena] App:      http://localhost:8000
echo [Daena] Health:   http://localhost:8000/health
echo [Daena] Postgres: localhost:5432
echo [Daena] Redis:    localhost:6379
echo ============================================
echo.
echo To stop: docker compose down
echo To view logs: docker compose logs -f daena
