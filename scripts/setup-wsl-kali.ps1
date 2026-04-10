# =============================================================
# Daena WSL2 + Kali Linux Setup
# =============================================================
# Run this in PowerShell as Administrator (one time only)
#
# What this does:
#   1. Enables WSL2
#   2. Installs Kali Linux
#   3. Creates setup script for inside Kali
#
# After this script:
#   - Open "Kali Linux" from Start menu
#   - Create username/password when prompted
#   - Run: bash /mnt/d/Ideas/Daena/scripts/setup-kali-inside.sh
# =============================================================

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " DAENA -- WSL2 + Kali Linux Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Enable WSL2
Write-Host "[1/3] Enabling WSL2..." -ForegroundColor Yellow
wsl --install --no-distribution 2>$null
wsl --set-default-version 2

# Step 2: Install Kali Linux
Write-Host "[2/3] Installing Kali Linux (this takes 5-10 minutes)..." -ForegroundColor Yellow
wsl --install -d kali-linux

# Step 3: Configure GPU passthrough for vLLM
Write-Host "[3/3] Configuring WSL2 for GPU access..." -ForegroundColor Yellow

$wslConfig = @"
[wsl2]
memory=16GB
processors=8
gpuSupport=true
localhostForwarding=true
"@

$wslConfigPath = "$env:USERPROFILE\.wslconfig"
if (-not (Test-Path $wslConfigPath)) {
    $wslConfig | Out-File -FilePath $wslConfigPath -Encoding UTF8
    Write-Host "  Created $wslConfigPath" -ForegroundColor Green
} else {
    Write-Host "  $wslConfigPath already exists (not overwriting)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " WSL2 + Kali Linux installed!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host " NEXT STEPS:" -ForegroundColor Cyan
Write-Host "  1. Restart your computer (required for WSL2)" -ForegroundColor White
Write-Host "  2. Open 'Kali Linux' from Start menu" -ForegroundColor White
Write-Host "  3. Create a username and password" -ForegroundColor White
Write-Host "  4. Run this command inside Kali:" -ForegroundColor White
Write-Host ""
Write-Host "     bash /mnt/d/Ideas/Daena/scripts/setup-kali-inside.sh" -ForegroundColor Yellow
Write-Host ""
Write-Host "  That script installs Python, vLLM, offensive tools," -ForegroundColor White
Write-Host "  and configures Daena's backend to run on Linux." -ForegroundColor White
Write-Host ""
