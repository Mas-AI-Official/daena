
# Tools/Cleanup-Models.ps1
# Scans for model weights outside central storage and proposes migration.
# Safety: Never deletes without explicit confirmation.

param (
    [string]$ProjectRoot = "D:\Ideas\Daena_old_upgrade_20251213",
    [string]$LegacyRoot = "D:\Ideas\Daena\models",
    [string]$CentralRoot = "D:\Ideas\MODELS_ROOT",
    [long]$SizeThreshold = 500MB
)

$ErrorActionPreference = "Stop"

function Get-ModelFiles {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return @() }
    
    Get-ChildItem -Path $Path -Recurse -File | 
    Where-Object { 
        $_.Length -gt $SizeThreshold -or 
        $_.Extension -match "\.(gguf|bin|safetensors|pt|pth|h5|model)$" 
    }
}

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " DAENA MODEL CENTRALIZATION UTILITY" -ForegroundColor Cyan
Write-Host "=========================================="
Write-Host "Scanning locations for scattered weights..."

$MigrationPlan = @()

# 1. Scan Legacy Root
Write-Host "`n[1/3] Scanning Legacy Root: $LegacyRoot" -ForegroundColor Yellow
$LegacyFiles = Get-ModelFiles -Path $LegacyRoot
if ($LegacyFiles) {
    foreach ($file in $LegacyFiles) {
        Write-Host "  Found: $($file.Name) ($([math]::Round($file.Length / 1MB, 2)) MB)"
        $MigrationPlan += [PSCustomObject]@{
            Source = $file.FullName
            Dest   = Join-Path $CentralRoot "_imported\legacy\$($file.Name)"
            Size   = $file.Length
        }
    }
}
else {
    Write-Host "  Empty or clean." -ForegroundColor Green
}

# 2. Scan Project Root (exclude virtual envs)
Write-Host "`n[2/3] Scanning Project Root: $ProjectRoot" -ForegroundColor Yellow
$ProjectFiles = Get-ModelFiles -Path $ProjectRoot | Where-Object { 
    $_.FullName -notmatch "\\venv" -and 
    $_.FullName -notmatch "\\.git" -and
    $_.FullName -notmatch "\\node_modules"
}

if ($ProjectFiles) {
    foreach ($file in $ProjectFiles) {
        Write-Host "  Found: $($file.Name) ($([math]::Round($file.Length / 1MB, 2)) MB) in $($file.Directory.Name)"
        $MigrationPlan += [PSCustomObject]@{
            Source = $file.FullName
            Dest   = Join-Path $CentralRoot "_imported\project\$($file.Name)"
            Size   = $file.Length
        }
    }
}
else {
    Write-Host "  Clean." -ForegroundColor Green
}

# 3. Report & Action
Write-Host "`n=========================================="
if ($MigrationPlan.Count -eq 0) {
    Write-Host "SUCCESS: No scattered weights found. All clean!" -ForegroundColor Cyan
    exit 0
}

Write-Host "FOUND $($MigrationPlan.Count) FILES CANDIDATE FOR MIGRATION:" -ForegroundColor Magenta
$MigrationPlan | Format-Table Source, Dest -AutoSize

$confirm = Read-Host "`nDo you want to MOVE these files to $CentralRoot\_imported? (Y/N)"
if ($confirm -eq "Y") {
    foreach ($item in $MigrationPlan) {
        $destDir = Split-Path $item.Dest -Parent
        if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
        
        Write-Host "Moving $($item.Source)..." -NoNewline
        Move-Item -Path $item.Source -Destination $item.Dest
        Write-Host " Done." -ForegroundColor Green
    }
    Write-Host "`nMigration Complete. Please verify files in $CentralRoot\_imported." -ForegroundColor Cyan
}
else {
    Write-Host "Operation cancelled." -ForegroundColor Yellow
}
