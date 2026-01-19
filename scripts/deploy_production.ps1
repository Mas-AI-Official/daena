# Daena AI Production Deployment Script (PowerShell)
# Windows-compatible version

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Daena AI Production Deployment" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$ENVIRONMENT = if ($env:ENVIRONMENT) { $env:ENVIRONMENT } else { "production" }
$BACKUP_DIR = ".\backups\$(Get-Date -Format 'yyyyMMdd_HHmmss')"
$LOG_FILE = ".\logs\deployment_$(Get-Date -Format 'yyyyMMdd_HHmmss').log"

# Create directories
New-Item -ItemType Directory -Force -Path backups, logs, governance_artifacts | Out-Null
New-Item -ItemType Directory -Force -Path $BACKUP_DIR | Out-Null

Write-Host "Step 1: Pre-Deployment Checks" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow

# Check Python
Write-Host "Checking Python version..."
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ Python not found" -ForegroundColor Red
    exit 1
}

# Check database
Write-Host "Checking database..."
if (Test-Path "daena.db") {
    Write-Host "✓ Database file exists" -ForegroundColor Green
    Copy-Item "daena.db" "$BACKUP_DIR\daena.db.backup"
    Write-Host "✓ Database backed up to $BACKUP_DIR" -ForegroundColor Green
} else {
    Write-Host "⚠ Database file not found, will be created" -ForegroundColor Yellow
}

# Check environment variables
Write-Host "Checking environment variables..."
if (-not $env:DAENA_MEMORY_AES_KEY) {
    Write-Host "⚠ Warning: DAENA_MEMORY_AES_KEY not set" -ForegroundColor Yellow
    Write-Host "Generating new encryption key..."
    $key = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 32 | ForEach-Object {[char]$_})
    $env:DAENA_MEMORY_AES_KEY = $key
    Write-Host "✓ Generated encryption key" -ForegroundColor Green
}

Write-Host ""
Write-Host "Step 2: Database Setup" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow

# Recreate database
Write-Host "Recreating database schema..."
python backend\scripts\recreate_database.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Database recreation failed" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Database schema recreated" -ForegroundColor Green

# Seed structure
Write-Host "Seeding 8×6 council structure..."
python backend\scripts\seed_6x8_council.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Seeding failed" -ForegroundColor Red
    exit 1
}
Write-Host "✓ 8×6 structure seeded" -ForegroundColor Green

# Verify structure
Write-Host "Verifying structure..."
python Tools\verify_structure.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Structure verification failed" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Structure verified" -ForegroundColor Green

Write-Host ""
Write-Host "Step 3: Operational Rehearsal" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow

# Cutover verification
Write-Host "Running cutover verification..."
python Tools\daena_cutover.py --verify-only | Tee-Object -FilePath $LOG_FILE -Append
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Cutover verification failed" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Cutover verification passed" -ForegroundColor Green

# DR drill
Write-Host "Running disaster recovery drill..."
python Tools\daena_drill.py | Tee-Object -FilePath $LOG_FILE -Append
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ DR drill failed" -ForegroundColor Red
    exit 1
}
Write-Host "✓ DR drill completed" -ForegroundColor Green

# Generate governance artifacts
Write-Host "Generating governance artifacts..."
python Tools\generate_governance_artifacts.py | Tee-Object -FilePath $LOG_FILE -Append
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Governance artifacts generation failed" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Governance artifacts generated" -ForegroundColor Green

Write-Host ""
Write-Host "Step 4: Service Configuration" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow

# Set production flags
$env:DAENA_READ_MODE = "nbmf"
$env:DAENA_DUAL_WRITE = "false"
$env:DAENA_CANARY_PERCENT = "100"
$env:DAENA_NBMF_ENABLED = "true"
$env:DAENA_TRACING_ENABLED = "true"

Write-Host "✓ Production flags set" -ForegroundColor Green

Write-Host ""
Write-Host "Step 5: Start Services" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow

# Check if server is already running
$existingProcess = Get-Process | Where-Object { $_.CommandLine -like "*uvicorn*main:app*" } -ErrorAction SilentlyContinue
if ($existingProcess) {
    Write-Host "Stopping existing services..."
    Stop-Process -Id $existingProcess.Id -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# Start FastAPI server
Write-Host "Starting FastAPI server..."
$job = Start-Job -ScriptBlock {
    Set-Location $using:PWD
    uvicorn backend.main:app --host 0.0.0.0 --port 8000
}

Write-Host "Server started (Job ID: $($job.Id))"
Write-Host "Waiting for server to start..."
Start-Sleep -Seconds 5

# Health check
Write-Host "Performing health check..."
for ($i = 1; $i -le 10; $i++) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 2 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Host "✓ Server is healthy" -ForegroundColor Green
            break
        }
    } catch {
        if ($i -eq 10) {
            Write-Host "✗ Health check failed after 10 attempts" -ForegroundColor Red
            exit 1
        }
        Start-Sleep -Seconds 2
    }
}

Write-Host ""
Write-Host "Step 6: Verification" -ForegroundColor Yellow
Write-Host "----------------------------------------" -ForegroundColor Yellow

# Test endpoints
$endpoints = @(
    "/monitoring/memory",
    "/api/v1/analytics/summary",
    "/api/v1/departments/",
    "/api/v1/agents/",
    "/command-center"
)

foreach ($endpoint in $endpoints) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:8000$endpoint" -TimeoutSec 5 -ErrorAction Stop
        Write-Host "✓ $endpoint working" -ForegroundColor Green
    } catch {
        Write-Host "✗ $endpoint failed" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "✅ Deployment Complete!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Server running on: http://localhost:8000"
Write-Host "Command Center: http://localhost:8000/command-center"
Write-Host "API Docs: http://localhost:8000/docs"
Write-Host "Monitoring: http://localhost:8000/monitoring/memory"
Write-Host ""
Write-Host "Logs: $LOG_FILE"
Write-Host "Backup: $BACKUP_DIR"
Write-Host "Governance Artifacts: governance_artifacts\"
Write-Host ""
Write-Host "Job ID: $($job.Id)"
Write-Host "To stop: Stop-Job -Id $($job.Id); Remove-Job -Id $($job.Id)"
Write-Host ""

