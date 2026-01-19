# ============================================================================
# Daena Backend Launcher (PowerShell)
# ============================================================================
# This script launches uvicorn with proper quoting and error handling
# ============================================================================

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectRoot,
    
    [Parameter(Mandatory=$true)]
    [string]$PythonExe,
    
    [Parameter(Mandatory=$false)]
    [int]$Port = 8000,
    
    [Parameter(Mandatory=$true)]
    [string]$LogPath
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Validate Python executable exists
if (-not (Test-Path $PythonExe)) {
    Write-Host "============================================================================" -ForegroundColor Red
    Write-Host "FATAL ERROR: Python executable not found" -ForegroundColor Red
    Write-Host "============================================================================" -ForegroundColor Red
    Write-Host "Expected: $PythonExe" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Change to project root
try {
    Set-Location -Path $ProjectRoot -ErrorAction Stop
    # Normalize paths for comparison (remove trailing backslashes, resolve to absolute)
    $currentPath = (Resolve-Path (Get-Location).Path).Path.TrimEnd('\')
    $expectedPath = (Resolve-Path $ProjectRoot).Path.TrimEnd('\')
    if ($currentPath -ne $expectedPath) {
        throw "Directory change failed: current path '$currentPath' does not match expected '$expectedPath'"
    }
} catch {
    Write-Host "============================================================================" -ForegroundColor Red
    Write-Host "FATAL ERROR: Cannot change to project root" -ForegroundColor Red
    Write-Host "============================================================================" -ForegroundColor Red
    Write-Host "Expected: $ProjectRoot" -ForegroundColor Red
    Write-Host "Current: $(Get-Location)" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Verify backend/main.py exists
if (-not (Test-Path "backend\main.py")) {
    Write-Host "============================================================================" -ForegroundColor Red
    Write-Host "FATAL ERROR: Backend entry point not found" -ForegroundColor Red
    Write-Host "============================================================================" -ForegroundColor Red
    Write-Host "Missing: backend\main.py" -ForegroundColor Red
    Write-Host "Current directory: $(Get-Location)" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Ensure log directory exists
$logDir = Split-Path -Parent $LogPath
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

Write-Host "============================================================================" -ForegroundColor Green
Write-Host "Starting Daena Backend Server" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host "Python: $PythonExe" -ForegroundColor Cyan
Write-Host "Project: $ProjectRoot" -ForegroundColor Cyan
Write-Host "Port: $Port" -ForegroundColor Cyan
Write-Host "Log: $LogPath" -ForegroundColor Cyan
Write-Host ""

# Preflight: Verify backend.main can be imported
Write-Host "[PREFLIGHT] Checking backend.main import..." -ForegroundColor Yellow
$importCheck = & $PythonExe -c "import backend.main; print('OK')" 2>&1
$importExitCode = $LASTEXITCODE
if ($importExitCode -ne 0) {
    Write-Host "============================================================================" -ForegroundColor Red
    Write-Host "FATAL ERROR: Cannot import backend.main" -ForegroundColor Red
    Write-Host "============================================================================" -ForegroundColor Red
    Write-Host $importCheck -ForegroundColor Red
    Write-Host ""
    Write-Host "Check the error above. Common causes:" -ForegroundColor Yellow
    Write-Host "  - Missing dependencies (run: python scripts\setup_env.py)" -ForegroundColor Yellow
    Write-Host "  - Syntax error in backend code" -ForegroundColor Yellow
    Write-Host "  - Wrong Python environment" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "[OK] backend.main import verified" -ForegroundColor Green
Write-Host ""

# Start uvicorn
Write-Host "============================================================================" -ForegroundColor Green
Write-Host "Starting uvicorn server..." -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""

# Run uvicorn and redirect output to log file
$uvicornArgs = @(
    "-m", "uvicorn",
    "backend.main:app",
    "--host", "127.0.0.1",
    "--port", $Port.ToString(),
    "--reload"
)

# CRITICAL: Change error handling to keep window open
$ErrorActionPreference = "Continue"

Write-Host "Starting uvicorn (output visible in this window)..." -ForegroundColor Cyan
Write-Host "Log file: $LogPath" -ForegroundColor Cyan
Write-Host ""

# Run uvicorn directly - output goes to console AND log file
# CRITICAL: Run uvicorn in THIS window so errors are visible
Write-Host "Starting uvicorn server..." -ForegroundColor Cyan
Write-Host "Log file: $LogPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Green
Write-Host "UVICORN OUTPUT (errors will appear here)" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""

# Change error handling to continue on errors
$ErrorActionPreference = "Continue"

try {
    # Run uvicorn directly - output goes to both console AND log file
    & $PythonExe -m uvicorn backend.main:app --host 127.0.0.1 --port $Port --reload 2>&1 | Tee-Object -FilePath $LogPath
    
    # If we get here, uvicorn exited
    $exitCode = $LASTEXITCODE
    Write-Host ""
    Write-Host "============================================================================" -ForegroundColor Yellow
    Write-Host "Uvicorn exited with code: $exitCode" -ForegroundColor Yellow
    Write-Host "============================================================================" -ForegroundColor Yellow
    
    if ($exitCode -ne 0) {
        Write-Host "ERROR: Backend crashed!" -ForegroundColor Red
        Write-Host ""
        Write-Host "Last 50 lines of log:" -ForegroundColor Yellow
        if (Test-Path $LogPath) {
            Get-Content $LogPath -Tail 50 -ErrorAction SilentlyContinue
        }
    }
} catch {
    Write-Host ""
    Write-Host "============================================================================" -ForegroundColor Red
    Write-Host "FATAL ERROR: Exception starting uvicorn" -ForegroundColor Red
    Write-Host "============================================================================" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Stack: $($_.ScriptStackTrace)" -ForegroundColor Red
    Write-Host ""
    if (Test-Path $LogPath) {
        Write-Host "Log file contents:" -ForegroundColor Yellow
        Get-Content $LogPath -Tail 50 -ErrorAction SilentlyContinue
    }
}

# ALWAYS keep window open so user can see what happened
Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "Backend stopped. Press Enter to close this window..." -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
try {
    Read-Host
} catch {
    # If Read-Host fails, wait a bit before closing
    Start-Sleep -Seconds 5
}


