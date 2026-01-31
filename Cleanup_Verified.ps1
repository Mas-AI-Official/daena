param([switch]$RealRun)

$Source = "D:\Ideas\Daena_old_upgrade_20251213"
$ModelsRoot = "D:\Ideas\MODELS_ROOT"
$BrainStorage = "$ModelsRoot\brain_storage"

Write-Host "=========================================="
Write-Host "   DAENA CLEANUP & ORGANIZATION SCRIPT    "
Write-Host "=========================================="
Write-Host "Source Project: $Source"
Write-Host "Target Root:    $ModelsRoot"
Write-Host ""

if (-not $RealRun) {
    Write-Host "[DRY RUN] Use -RealRun to execute changes."
    Write-Host ""
}
else {
    Write-Host "[REAL RUN] Executing changes..."
    # Create target directories
    if (-not (Test-Path $BrainStorage)) { New-Item -ItemType Directory -Force -Path $BrainStorage | Out-Null }
}

# Helper to run robocopy
function Invoke-SafeMove($src, $dest) {
    if (-not (Test-Path $src)) {
        Write-Host "[-] Source not found: $src" -ForegroundColor DarkGray
        return
    }
    
    if (-not $RealRun) {
        Write-Host "[PLAN] MOVE: $src  ->  $dest" -ForegroundColor Cyan
    }
    else {
        Write-Host "[EXEC] Moving $src..." -ForegroundColor Yellow
        # /MOVE = move files and dirs
        # /E = recursive
        # /NFL /NDL = no file/dir logging (cleaner output)
        # /NP = no progress percentage (cleaner output)
        cmd /c "robocopy `"$src`" `"$dest`" /E /MOVE /NP /NFL /NDL"
        if ($LASTEXITCODE -ge 8) { 
            Write-Host "    [!] Robocopy failed with code $LASTEXITCODE" -ForegroundColor Red
        }
        else {
            Write-Host "    [+] Done." -ForegroundColor Green
        }
    }
}

# 1. Move Models Folder
Invoke-SafeMove "$Source\models" "$ModelsRoot"

# 2. Move Local Brain
Invoke-SafeMove "$Source\local_brain" "$BrainStorage\local_brain"

# 3. Move DaenaBrain (if exists)
Invoke-SafeMove "$Source\DaenaBrain" "$BrainStorage\DaenaBrain"

Write-Host ""
Write-Host "Cleanup check complete."
