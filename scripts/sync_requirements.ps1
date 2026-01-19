# ============================================================================
# Sync Requirements Script
# Automatically installs/updates dependencies
# ============================================================================

$PROJECT_ROOT = "D:\Ideas\Daena_old_upgrade_20251213"
Set-Location $PROJECT_ROOT

Write-Host "============================================================================"
Write-Host "Syncing Requirements"
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
    Write-Host "Please create venv first"
    exit 1
}

Write-Host "Using Python: $pythonExe"
Write-Host ""

# Activate venv
& "$venvPath\Scripts\Activate.ps1"

# Upgrade pip
Write-Host "Upgrading pip, setuptools, wheel..."
& $pythonExe -m pip install --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to upgrade pip"
    exit 1
}

# Install requirements if exists
if (Test-Path "requirements.txt") {
    Write-Host ""
    Write-Host "Installing from requirements.txt..."
    & $pythonExe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: Some packages failed to install"
    }
} else {
    Write-Host "WARNING: requirements.txt not found"
}

# Freeze to lock file
Write-Host ""
Write-Host "Freezing to requirements-lock.txt..."
& $pythonExe -m pip freeze > requirements-lock.txt
if ($LASTEXITCODE -eq 0) {
    Write-Host "Requirements locked to requirements-lock.txt"
} else {
    Write-Host "WARNING: Failed to freeze requirements"
}

Write-Host ""
Write-Host "============================================================================"
Write-Host "Requirements sync complete"
Write-Host "============================================================================"





