# check-google-oauth.ps1
# Operator-facing one-shot probe for Daena's Google OAuth + Gmail draft state.
#
# Usage:
#   pwsh.exe -NoProfile -ExecutionPolicy Bypass -File scripts\check-google-oauth.ps1
#
# Prints (in order):
#   - backend reachable?
#   - dev token mintable?
#   - google-setup-status (client + both accounts)
#   - registered controlled-execution tools (gmail.create_draft + send_existing_draft expected)
#   - send rate limit
#
# This script NEVER edits anything. Read-only.

$ErrorActionPreference = 'Stop'
$BackendUrl = 'http://127.0.0.1:8000'
$RepoRoot = Split-Path -Parent $PSScriptRoot

Write-Host ""
Write-Host " === Daena Google OAuth state probe ==="
Write-Host ""

# 1. Backend reachable?
try {
    $health = Invoke-RestMethod -Uri "$BackendUrl/api/v1/health/detailed" -Method Get -TimeoutSec 5
    Write-Host (" [OK] backend healthy   uptime={0} seedings={1}" -f $health.uptime, $health.seedings.seed_phase)
} catch {
    Write-Host " [ERR] backend not reachable on $BackendUrl"
    Write-Host " run scripts\start-daena-local.bat first"
    exit 1
}

# 2. Mint a dev token
try {
    $venvPython = Join-Path $RepoRoot 'backend\.venv\Scripts\python.exe'
    $mintScript = Join-Path $RepoRoot 'backend\scripts\_mint_dev_token.py'
    Push-Location (Join-Path $RepoRoot 'backend')
    $token = & $venvPython $mintScript 2>$null
    Pop-Location
    if (-not $token -or $token.Length -lt 40) { throw "mint returned empty" }
    Write-Host " [OK] dev token minted (length=$($token.Length))"
} catch {
    Write-Host " [ERR] cannot mint dev token: $_"
    exit 1
}

$headers = @{ Authorization = "Bearer $token" }

# 3. google-setup-status
try {
    $g = Invoke-RestMethod -Uri "$BackendUrl/api/v1/connections/google-setup-status" -Headers $headers -Method Get -TimeoutSec 5
    Write-Host ""
    Write-Host " --- google-setup-status ---"
    Write-Host (" client_configured     : {0}" -f $g.client_configured)
    Write-Host (" client_id_present     : {0}" -f $g.client_id_present)
    Write-Host (" client_secret_present : {0}" -f $g.client_secret_present)
    Write-Host ""
    $fInst = if ($g.founder_account.instance_id) { $g.founder_account.instance_id } else { '<none>' }
    $aInst = if ($g.agent_account.instance_id) { $g.agent_account.instance_id } else { '<none>' }
    Write-Host (" founder ({0})" -f $g.founder_account.email)
    Write-Host ("   connected           : {0}" -f $g.founder_account.connected)
    Write-Host ("   instance_id         : {0}" -f $fInst)
    Write-Host ("   connected_services  : {0}" -f ($g.founder_account.connected_services -join ', '))
    Write-Host ""
    Write-Host (" agent ({0})" -f $g.agent_account.email)
    Write-Host ("   connected           : {0}" -f $g.agent_account.connected)
    Write-Host ("   instance_id         : {0}" -f $aInst)
    Write-Host ("   connected_services  : {0}" -f ($g.agent_account.connected_services -join ', '))
    Write-Host ""
    Write-Host (" READY                 : {0}" -f $g.ready)
} catch {
    Write-Host " [ERR] google-setup-status probe failed: $_"
}

# 4. Registered controlled-execution tools
try {
    $tools = Invoke-RestMethod -Uri "$BackendUrl/api/v1/integrations/controlled-execution/registered-tools" -Headers $headers -Method Get -TimeoutSec 5
    Write-Host ""
    Write-Host " --- controlled-execution registered tools ---"
    foreach ($t in $tools.tools) { Write-Host "   $t" }
} catch {
    Write-Host " [ERR] registered-tools probe failed: $_"
}

# 5. Send rate limit
try {
    $rl = Invoke-RestMethod -Uri "$BackendUrl/api/v1/opportunities/send-rate-limit" -Headers $headers -Method Get -TimeoutSec 5
    Write-Host ""
    Write-Host " --- send rate limit ---"
    Write-Host (" today={0} used={1} cap={2} remaining={3}" -f $rl.today_utc, $rl.used, $rl.cap, $rl.remaining)
} catch {
    Write-Host " [ERR] send-rate-limit probe failed: $_"
}

Write-Host ""
Write-Host " === done ==="
Write-Host ""
