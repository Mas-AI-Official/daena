# Run Daena smoke tests (and optionally E2E). Optionally start backend first.
# Usage:
#   .\run_all_tests.ps1                    # Run smoke only (backend must be up)
#   .\run_all_tests.ps1 -StartBackend     # Start backend, wait for health, run smoke
#   .\run_all_tests.ps1 -StartBackend -RunE2E  # Also run E2E after smoke

param(
    [switch]$StartBackend,
    [switch]$RunE2E,
    [string]$BaseUrl = "http://localhost:8000",
    [string]$Token = $env:EXECUTION_TOKEN
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Py = "python"
if (Test-Path "venv_daena_main_py310\Scripts\python.exe") {
    $Py = "venv_daena_main_py310\Scripts\python.exe"
}

if (-not $Token) {
    $Token = "manual-verify-token"
    Write-Host "[INFO] EXECUTION_TOKEN not set; using manual-verify-token (matches start_backend_with_env.bat default)." -ForegroundColor Gray
}

$BackendJob = $null
$BackendProcess = $null

function Wait-ForBackend {
    param([int]$MaxWaitSec = 90)
    $base = $BaseUrl.TrimEnd("/")
    $deadline = [DateTime]::UtcNow.AddSeconds($MaxWaitSec)
    while ([DateTime]::UtcNow -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri "$base/health" -UseBasicParsing -TimeoutSec 5
            if ($r.StatusCode -eq 200) { return $true }
        } catch {}
        Start-Sleep -Seconds 3
    }
    return $false
}

try {
    if ($StartBackend) {
        # Free port 8001 (test backend) so we don't hit a stale process
        try {
            $lines = & cmd /c "netstat -ano | findstr :8001 | findstr LISTENING" 2>$null
            foreach ($line in $lines) {
                $parts = $line -split '\s+'
                if ($parts.Count -ge 5) {
                    $pid = $parts[-1]
                    if ($pid -match '^\d+$') {
                        Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                        Start-Sleep -Seconds 2
                        break
                    }
                }
            }
        } catch {}
        $TestPort = 8001
        $BaseUrl = "http://127.0.0.1:$TestPort"
        $env:EXECUTION_TOKEN = $Token
        $env:PYTHONPATH = $ProjectRoot
        Write-Host "Starting backend in-job on port $TestPort (EXECUTION_TOKEN=$Token)..." -ForegroundColor Cyan
        $BackendJob = Start-Job -ScriptBlock {
            param($Root, $Python, $Tok, $Port)
            $env:PYTHONPATH = $Root
            $env:EXECUTION_TOKEN = $Tok
            Set-Location $Root
            & $Python -m uvicorn backend.main:app --host 127.0.0.1 --port $Port 2>&1
        } -ArgumentList $ProjectRoot, $Py, $Token, $TestPort -Name DaenaBackend
        if (-not (Wait-ForBackend)) {
            Write-Host "ERROR: Backend did not become ready within 90s." -ForegroundColor Red
            if ($BackendJob) { Stop-Job $BackendJob -ErrorAction SilentlyContinue; Remove-Job $BackendJob -Force -ErrorAction SilentlyContinue }
            exit 1
        }
        Write-Host "Backend is up." -ForegroundColor Green
    }

    Write-Host "Running smoke tests..." -ForegroundColor Cyan
    & $Py scripts/smoke_control_plane.py --base $BaseUrl --token $Token
    $SmokeExit = $LASTEXITCODE

    if ($SmokeExit -ne 0) {
        Write-Host "Smoke tests failed (exit $SmokeExit)." -ForegroundColor Red
        exit $SmokeExit
    }

    Write-Host "Smoke tests passed." -ForegroundColor Green

    Write-Host "Running manual verification steps (API equivalents)..." -ForegroundColor Cyan
    $env:DAENA_BASE_URL = $BaseUrl
    $env:EXECUTION_TOKEN = $Token
    & $Py scripts/manual_verification_steps.py
    $ManualExit = $LASTEXITCODE
    if ($ManualExit -ne 0) {
        Write-Host "Manual verification had $ManualExit failures." -ForegroundColor Red
        exit $ManualExit
    }
    Write-Host "Manual verification passed." -ForegroundColor Green

    if ($RunE2E) {
        Write-Host "Running E2E UI flows..." -ForegroundColor Cyan
        & $Py scripts/daena_ui_e2e_flows.py --base-url $BaseUrl --token $Token
        $E2EExit = $LASTEXITCODE
        if ($E2EExit -ne 0) {
            Write-Host "E2E flows failed (exit $E2EExit)." -ForegroundColor Red
            exit $E2EExit
        }
        Write-Host "E2E flows passed." -ForegroundColor Green
    }
} finally {
    if ($BackendJob) {
        Write-Host "Stopping backend job..." -ForegroundColor Gray
        Stop-Job $BackendJob -ErrorAction SilentlyContinue
        Remove-Job $BackendJob -Force -ErrorAction SilentlyContinue
    }
    if ($BackendProcess -and -not $BackendProcess.HasExited) {
        Write-Host "Stopping backend (PID $($BackendProcess.Id))..." -ForegroundColor Gray
        Stop-Process -Id $BackendProcess.Id -Force -ErrorAction SilentlyContinue
    }
}

exit 0
