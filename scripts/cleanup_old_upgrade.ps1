# cleanup_old_upgrade.ps1
# Model path cleanup: print size report, optionally move memory DB/stores to BRAIN_ROOT, delete duplicates only with -Confirm.
# Usage: .\scripts\cleanup_old_upgrade.ps1 [-Confirm]
# Set $env:BRAIN_ROOT (e.g. D:\Ideas\DAENA_BRAIN_ROOT) to move memory DB/stores there.

param(
    [switch]$Confirm
)

$ErrorActionPreference = "Stop"
$projectRoot = (Get-Item $PSScriptRoot).Parent.FullName
$oldFolders = @(
    @{ Path = "local_brain"; Desc = "Legacy local brain (prefer MODELS_ROOT/ollama)" },
    @{ Path = "backend\.venv"; Desc = "Nested venv (use project venv)" },
    @{ Path = "daena_tts"; Desc = "Leftover env folder" },
    @{ Path = "DaenaBrain"; Desc = "Unused DaenaBrain folder (delete only if not connected)" }
)
$brainRoot = $env:BRAIN_ROOT
if (-not $brainRoot) { $brainRoot = Join-Path $projectRoot "local_brain" }

Write-Host "=== Daena upgrade cleanup ===" -ForegroundColor Cyan
Write-Host "Project root: $projectRoot"
Write-Host "BRAIN_ROOT (for memory DB): $brainRoot"
Write-Host ""

# Size report
Write-Host "=== Size report ===" -ForegroundColor Yellow
foreach ($f in $oldFolders) {
    $full = Join-Path $projectRoot $f.Path
    if (Test-Path $full) {
        $size = (Get-ChildItem $full -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        $sizeMB = [math]::Round($size / 1MB, 2)
        Write-Host "  $($f.Path): $sizeMB MB - $($f.Desc)"
    } else {
        Write-Host "  $($f.Path): (not found)"
    }
}
$logsPath = Join-Path $projectRoot "logs"
if (Test-Path $logsPath) {
    $size = (Get-ChildItem $logsPath -Recurse -File -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
    Write-Host "  logs/: $([math]::Round($size/1MB,2)) MB (do not commit)"
} else {
    Write-Host "  logs/: (not found)"
}
Write-Host ""

# Move memory DB/stores to BRAIN_ROOT (optional)
if ($env:BRAIN_ROOT -and (Test-Path (Join-Path $projectRoot "local_brain"))) {
    Write-Host "To move local_brain content to BRAIN_ROOT, copy manually or use robocopy." -ForegroundColor Gray
    Write-Host "  Example: New-Item -ItemType Directory -Force $brainRoot; Copy-Item -Path (Join-Path $projectRoot 'local_brain\*') -Destination $brainRoot -Recurse -Force" -ForegroundColor Gray
    Write-Host ""
}

# Delete only with -Confirm
if (-not $Confirm) {
    Write-Host "No deletions (use -Confirm to delete confirmed duplicates)." -ForegroundColor Green
    Write-Host "Note: backend\.venv, daena_tts, logs, local_brain are in .gitignore. Keep local_brain until migrated to MODELS_ROOT/BRAIN_ROOT." -ForegroundColor Gray
    exit 0
}

Write-Host "=== Confirm deletions ===" -ForegroundColor Red
Write-Host "With -Confirm, backend\.venv, daena_tts, and DaenaBrain (if present) are removed (not local_brain or logs)."
$response = Read-Host "Type YES to delete backend\.venv, daena_tts, and DaenaBrain"
if ($response -ne "YES") {
    Write-Host "Aborted."
    exit 0
}
foreach ($f in @("backend\.venv", "daena_tts", "DaenaBrain")) {
    $full = Join-Path $projectRoot $f
    if (Test-Path $full) {
        Remove-Item $full -Recurse -Force
        Write-Host "  Removed: $f"
    }
}
Write-Host "Done."
