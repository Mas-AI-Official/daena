# Open browser tabs for UI spot checks (Verification Checklist §5).
# Usage: .\scripts\open_ui_spot_checks.ps1 [-Port 8000] [-StartBackend]
# Backend must be running unless you use -StartBackend (starts backend on $Port, waits for health, then opens browser).
# Use -Port 8001 if you usually start with run_all_tests.ps1 -StartBackend.

param(
    [int]$Port = 8000,
    [switch]$StartBackend
)

$BaseUrl = "http://127.0.0.1:$Port"
$healthUrl = "$BaseUrl/health"

# Optional: start backend on $Port and wait for health
$BackendJob = $null
if ($StartBackend) {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    # Free port so our backend can bind
    try {
        $lines = & cmd /c "netstat -ano | findstr :$Port | findstr LISTENING" 2>$null
        foreach ($line in $lines) {
            $parts = $line -split '\s+'
            if ($parts.Count -ge 5 -and $parts[-1] -match '^\d+$') {
                Stop-Process -Id $parts[-1] -Force -ErrorAction SilentlyContinue
                Start-Sleep -Seconds 2
                break
            }
        }
    } catch {}
    $Py = "python"
    if (Test-Path (Join-Path $ProjectRoot "venv_daena_main_py310\Scripts\python.exe")) {
        $Py = (Join-Path $ProjectRoot "venv_daena_main_py310\Scripts\python.exe")
    }
    $env:EXECUTION_TOKEN = "manual-verify-token"
    $env:PYTHONPATH = $ProjectRoot
    Write-Host "Starting backend on port $Port..." -ForegroundColor Cyan
    $BackendJob = Start-Job -ScriptBlock {
        param($Root, $Python, $PortNum)
        $env:PYTHONPATH = $Root
        $env:EXECUTION_TOKEN = "manual-verify-token"
        Set-Location $Root
        & $Python -m uvicorn backend.main:app --host 127.0.0.1 --port $PortNum 2>&1
    } -ArgumentList $ProjectRoot, $Py, $Port -Name DaenaSpotBackend
    $deadline = [DateTime]::UtcNow.AddSeconds(60)
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5
            if ($r.StatusCode -eq 200) { break }
        } catch {}
        Start-Sleep -Seconds 3
    }
    try {
        $r = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5
        if ($r.StatusCode -ne 200) { throw "Health failed" }
    } catch {
        Write-Host "ERROR: Backend did not become ready on port $Port within 60s." -ForegroundColor Red
        Write-Host "  Start the backend manually in another terminal, then run without -StartBackend:" -ForegroundColor Yellow
        Write-Host "    scripts\start_backend_with_env.bat" -ForegroundColor Gray
        Write-Host "    .\scripts\open_ui_spot_checks.ps1 -Port 8000" -ForegroundColor Gray
        if ($BackendJob) {
            $out = Receive-Job $BackendJob 2>&1
            if ($out) { Write-Host "  Job output: $out" -ForegroundColor Gray }
            Stop-Job $BackendJob -ErrorAction SilentlyContinue; Remove-Job $BackendJob -Force -ErrorAction SilentlyContinue
        }
        exit 1
    }
    Write-Host "Backend is up on port $Port." -ForegroundColor Green
}

# Check backend is reachable before opening browser
try {
    $r = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5
    if ($r.StatusCode -ne 200) { throw "Health returned $($r.StatusCode)" }
} catch {
    Write-Host "ERROR: Backend not reachable at $healthUrl" -ForegroundColor Red
    Write-Host "  Start the backend first, e.g.:" -ForegroundColor Yellow
    Write-Host "    scripts\start_backend_with_env.bat" -ForegroundColor Gray
    Write-Host "  Or run with -StartBackend to start it now:" -ForegroundColor Yellow
    Write-Host "    .\scripts\open_ui_spot_checks.ps1 -Port $Port -StartBackend" -ForegroundColor Gray
    if ($BackendJob) { Stop-Job $BackendJob -ErrorAction SilentlyContinue; Remove-Job $BackendJob -Force -ErrorAction SilentlyContinue }
    exit 1
}

# Control plane: dashboard, control-plane, skills, execution, tasks+runbook+approvals (condensed)
$pages = @(
    "$BaseUrl/ui/dashboard",
    "$BaseUrl/ui/control-plane",
    "$BaseUrl/ui/control-plane#skills",
    "$BaseUrl/ui/control-plane#execution",
    "$BaseUrl/ui/control-plane#tasks-runbook-approvals"
)
Write-Host "Opening UI spot-check pages on port $Port..." -ForegroundColor Cyan
foreach ($url in $pages) {
    Start-Process $url
    Start-Sleep -Milliseconds 600
}
Write-Host "Done. Use Verification Checklist §5: token gating, Skills run, Execution, Tasks & Runbook & Approvals, Lockdown." -ForegroundColor Gray
if ($BackendJob) {
    Write-Host "Backend is running in a job. To stop it: Get-Job DaenaSpotBackend | Stop-Job; Get-Job DaenaSpotBackend | Remove-Job -Force" -ForegroundColor Gray
}
