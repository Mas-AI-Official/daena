# ============================================================================
# Smoke Test Script (PowerShell)
# Starts backend, waits for health, opens dashboard
# ============================================================================

$PROJECT_ROOT = "D:\Ideas\Daena_old_upgrade_20251213"
Set-Location $PROJECT_ROOT

Write-Host "============================================================================"
Write-Host "Smoke Test - Starting Backend and Testing"
Write-Host "============================================================================"
Write-Host ""

# Detect venv
$venvPath = $null
if (Test-Path "venv_daena_main_py310\Scripts\activate.ps1") {
    $venvPath = "venv_daena_main_py310"
    $pythonExe = "$venvPath\Scripts\python.exe"
} elseif (Test-Path "venv\Scripts\activate.ps1") {
    $venvPath = "venv"
    $pythonExe = "$venvPath\Scripts\python.exe"
} else {
    Write-Host "ERROR: No virtual environment found"
    exit 1
}

# Start backend in new window
Write-Host "Starting backend in new window..."
$backendWindow = Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "cd /d $PROJECT_ROOT && call $venvPath\Scripts\activate.bat && python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000" -PassThru

Write-Host "Backend window PID: $($backendWindow.Id)"
Write-Host "Waiting for backend to start (30 seconds max)..."
Write-Host ""

# Wait for health endpoint
$maxWait = 30
$waited = 0
$healthUrl = "http://127.0.0.1:8000/api/v1/health/"
$success = $false

while ($waited -lt $maxWait) {
    try {
        $response = Invoke-WebRequest -Uri $healthUrl -TimeoutSec 2 -ErrorAction Stop
        if ($response.StatusCode -eq 200) {
            Write-Host "[OK] Backend is responding!"
            $success = $true
            break
        }
    } catch {
        # Still waiting
    }
    Start-Sleep -Seconds 2
    $waited += 2
    Write-Host "  Waiting... ($waited/$maxWait seconds)"
}

if (-not $success) {
    Write-Host ""
    Write-Host "[FAIL] Backend did not respond within $maxWait seconds"
    Write-Host "Check the backend window for errors"
    exit 1
}

# Open dashboard
Write-Host ""
Write-Host "Opening dashboard..."
Start-Process "http://127.0.0.1:8000/ui/dashboard"

Write-Host ""
Write-Host "============================================================================"
Write-Host "[OK] Smoke test PASSED"
Write-Host "============================================================================"
Write-Host ""
Write-Host "Backend is running at: http://127.0.0.1:8000"
Write-Host "Dashboard: http://127.0.0.1:8000/ui/dashboard"
Write-Host ""
Write-Host "Press any key to stop backend..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

# Stop backend
Stop-Process -Id $backendWindow.Id -Force
Write-Host "Backend stopped"





