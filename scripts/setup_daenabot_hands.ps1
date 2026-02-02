# DaenaBot Hands (OpenClaw Gateway) installer for Windows.
# Clones OpenClaw under repo, generates Windows-safe token, starts gateway,
# binds host port to 127.0.0.1 only, writes DAENABOT_HANDS_* and OPENCLAW_* to .env
# Run from Daena repo root: .\scripts\setup_daenabot_hands.ps1

param(
  [string]$OpenClawDir = ".\tools\daenabot-hands\openclaw",
  [string]$DaenaEnvPath = ".\.env",
  [int]$Port = 18789
)

$ErrorActionPreference = "Stop"

function Test-RequiredCommand {
  param([string]$Name)
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Missing required command: $Name. Install it and re-run."
  }
}

function New-HexToken([int]$bytes = 32) {
  $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
  $buf = New-Object byte[] $bytes
  $rng.GetBytes($buf)
  ($buf | ForEach-Object { $_.ToString("x2") }) -join ""
}

function Upsert-EnvLine([string]$path, [string]$key, [string]$value) {
  if (-not (Test-Path $path)) { New-Item -ItemType File -Force $path | Out-Null }
  $lines = Get-Content $path -ErrorAction SilentlyContinue
  $escapedKey = [regex]::Escape($key)
  $newLine = "$key=$value"

  if ($lines -match "^\s*$escapedKey\s*=") {
    $lines = $lines | ForEach-Object {
      if ($_ -match "^\s*$escapedKey\s*=") { $newLine } else { $_ }
    }
  } else {
    $lines += $newLine
  }

  Set-Content -Path $path -Value $lines -Encoding UTF8
}

Test-RequiredCommand -Name git
Test-RequiredCommand -Name docker

# Ensure folder exists
New-Item -ItemType Directory -Force (Split-Path -Parent $OpenClawDir) | Out-Null

# Clone OpenClaw if missing
if (-not (Test-Path $OpenClawDir)) {
  git clone https://github.com/openclaw/openclaw.git $OpenClawDir
}

Push-Location $OpenClawDir

# Generate token and write OpenClaw .env (used by docker compose)
$token = New-HexToken 32
$openclawEnv = Join-Path $OpenClawDir ".env"
Upsert-EnvLine $openclawEnv "OPENCLAW_GATEWAY_TOKEN" $token

# Build + onboard + start gateway (official manual flow)
docker build -t openclaw:local -f Dockerfile .
docker compose run --rm openclaw-cli onboard
docker compose up -d openclaw-gateway

# Lock host exposure to loopback (localhost only) by using an override compose file
$portMapping = "127.0.0.1:${Port}:${Port}"
$override = @"
services:
  openclaw-gateway:
    ports:
      - "$portMapping"
"@
$overridePath = Join-Path $OpenClawDir "docker-compose.daenabot.override.yml"
Set-Content -Path $overridePath -Value $override -Encoding UTF8

docker compose -f docker-compose.yml -f docker-compose.daenabot.override.yml up -d openclaw-gateway

Pop-Location

# Write Daena env vars (new + backward compatible)
$wsUrl = "ws://127.0.0.1:$Port/ws"
Update-EnvLine -Path $DaenaEnvPath -Key "DAENABOT_HANDS_URL" -Value $wsUrl
Update-EnvLine -Path $DaenaEnvPath -Key "DAENABOT_HANDS_TOKEN" -Value $token
Update-EnvLine -Path $DaenaEnvPath -Key "OPENCLAW_GATEWAY_URL" -Value $wsUrl
Update-EnvLine -Path $DaenaEnvPath -Key "OPENCLAW_GATEWAY_TOKEN" -Value $token

Write-Host ""
Write-Host "DaenaBot Hands is installed."
Write-Host "Control UI: http://127.0.0.1:$Port/"
Write-Host "WS URL:      $wsUrl"
Write-Host "Token saved to: $DaenaEnvPath"
Write-Host ""

# Health check (official command)
Push-Location $OpenClawDir
docker compose exec openclaw-gateway node dist/index.js health --token "$token"
Pop-Location
