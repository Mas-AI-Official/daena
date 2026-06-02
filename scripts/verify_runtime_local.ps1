# verify_runtime_local.ps1 -- safe local runtime smoke for Daena.
# Read-only reachability + auth-gate checks. NO secrets, NO external sends,
# NO scans, NO deploy, NO DB mutation. Founder/agent demo pre-check.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File D:\Ideas\Daena\scripts\verify_runtime_local.ps1
#
# Exit: 0 = all PASS, 1 = some WARN, 2 = some FAIL.

param(
  [string]$Backend  = "http://127.0.0.1:8000",
  [string]$Frontend = "http://localhost:5173",
  [string]$F5       = "http://127.0.0.1:9101"
)

$ErrorActionPreference = "SilentlyContinue"
$script:pass = 0; $script:warn = 0; $script:fail = 0

function Get-Status([string]$url) {
  try {
    $r = Invoke-WebRequest -Uri $url -Method GET -TimeoutSec 8 -UseBasicParsing
    return [int]$r.StatusCode
  } catch {
    if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode }
    return 0
  }
}

function Check([string]$name, [int]$got, [int[]]$okCodes, [string]$note = "") {
  if ($okCodes -contains $got) {
    Write-Host ("PASS  {0,-38} {1}  {2}" -f $name, $got, $note) -ForegroundColor Green
    $script:pass++
  } elseif ($got -eq 0) {
    Write-Host ("FAIL  {0,-38} unreachable  {1}" -f $name, $note) -ForegroundColor Red
    $script:fail++
  } else {
    Write-Host ("WARN  {0,-38} {1} (expected {2})  {3}" -f $name, $got, ($okCodes -join "/"), $note) -ForegroundColor Yellow
    $script:warn++
  }
}

Write-Host "Daena local runtime smoke (read-only; no secrets/sends/scans/deploy)" -ForegroundColor Cyan
Write-Host ("backend={0}  frontend={1}  f5={2}" -f $Backend, $Frontend, $F5)
Write-Host ""

Check "backend /api/v1/health"               (Get-Status "$Backend/api/v1/health")        @(200)     "public health"
Check "backend / (root)"                      (Get-Status "$Backend/")                     @(200,404) "404 = alive (root not a route)"
Check "frontend root"                         (Get-Status "$Frontend/")                    @(200)     "Vite binds localhost/::1"
Check "vite proxy -> backend health"          (Get-Status "$Frontend/api/v1/health")       @(200)     "frontend reaches backend"
Check "F5 /health"                            (Get-Status "$F5/health")                    @(200)     "F5 clone voice service"
Check "auth gate: /tts/defaults (no token)"   (Get-Status "$Backend/api/v1/tts/defaults")  @(401,403) "protected: rejects no-token"
Check "auth gate: /settings/user (no token)"  (Get-Status "$Backend/api/v1/settings/user") @(401,403) "protected: rejects no-token"

Write-Host ""
Write-Host ("RESULT: PASS={0} WARN={1} FAIL={2}" -f $script:pass, $script:warn, $script:fail) -ForegroundColor Cyan
Write-Host "Note: F5 WARN/FAIL just means the :9101 service is not started (voice falls back to Edge)." -ForegroundColor DarkGray
if ($script:fail -gt 0) { exit 2 } elseif ($script:warn -gt 0) { exit 1 } else { exit 0 }
