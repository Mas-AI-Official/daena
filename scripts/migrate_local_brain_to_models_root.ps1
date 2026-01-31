# migrate_local_brain_to_models_root.ps1
# Migrates D:\Ideas\Daena_old_upgrade_20251213\local_brain to D:\Ideas\MODELS_ROOT:
# - Brain data (brain_store, user_context, chat_history) -> MODELS_ROOT\daena_brain
# - daena-brain model (manifest + blobs) -> MODELS_ROOT\ollama (only if not already there)
# After migration, set BRAIN_ROOT=D:\Ideas\MODELS_ROOT\daena_brain (or leave unset; code uses MODELS_ROOT/daena_brain).
# Usage: .\scripts\migrate_local_brain_to_models_root.ps1 [-WhatIf]

param([switch]$WhatIf)

$ErrorActionPreference = "Stop"
$projectRoot = (Get-Item $PSScriptRoot).Parent.FullName
$localBrain = Join-Path $projectRoot "local_brain"
$modelsRoot = $env:MODELS_ROOT
if (-not $modelsRoot) { $modelsRoot = "D:\Ideas\MODELS_ROOT" }
$daenaBrain = Join-Path $modelsRoot "daena_brain"
$ollamaRoot = Join-Path $modelsRoot "ollama"

if (-not (Test-Path $localBrain)) {
    Write-Host "local_brain not found at $localBrain. Nothing to migrate." -ForegroundColor Yellow
    exit 0
}

Write-Host "=== Migrate local_brain to MODELS_ROOT ===" -ForegroundColor Cyan
Write-Host "  local_brain: $localBrain"
Write-Host "  MODELS_ROOT: $modelsRoot"
Write-Host "  daena_brain (brain data): $daenaBrain"
Write-Host "  ollama (LLMs): $ollamaRoot"
Write-Host ""

# 1) Create daena_brain and copy brain data
$brainStoreSrc = Join-Path $localBrain "brain_store"
$brainStoreDst = Join-Path $daenaBrain "brain_store"
$userContextSrc = Join-Path $localBrain "user_context.json"
$chatHistorySrc = Join-Path $localBrain "chat_history"

if (-not $WhatIf) {
    New-Item -ItemType Directory -Force -Path $daenaBrain | Out-Null
    New-Item -ItemType Directory -Force -Path $brainStoreDst | Out-Null
    New-Item -ItemType Directory -Force -Path (Join-Path $daenaBrain "chat_history") | Out-Null
}

if (Test-Path $brainStoreSrc) {
    Write-Host "[1] Copying brain_store to $daenaBrain\brain_store..."
    if (-not $WhatIf) {
        Copy-Item -Path (Join-Path $brainStoreSrc "*") -Destination $brainStoreDst -Recurse -Force
    }
    Write-Host "    OK"
} else {
    Write-Host "[1] brain_store not found; skipping"
}

if (Test-Path $userContextSrc) {
    Write-Host "[2] Copying user_context.json to $daenaBrain..."
    if (-not $WhatIf) {
        Copy-Item -Path $userContextSrc -Destination $daenaBrain -Force
    }
    Write-Host "    OK"
} else {
    Write-Host "[2] user_context.json not found; skipping"
}

if (Test-Path $chatHistorySrc) {
    Write-Host "[3] Copying chat_history to $daenaBrain\chat_history..."
    if (-not $WhatIf) {
        Copy-Item -Path (Join-Path $chatHistorySrc "*") -Destination (Join-Path $daenaBrain "chat_history") -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host "    OK"
} else {
    Write-Host "[3] chat_history not found; skipping (empty dir created)"
}

# 2) Copy daena-brain to MODELS_ROOT/ollama (manifest + blobs not already there)
$daenaManifestSrc = Join-Path $localBrain "manifests\registry.ollama.ai\library\daena-brain"
$daenaManifestDst = Join-Path $ollamaRoot "manifests\registry.ollama.ai\library\daena-brain"
$blobsSrc = Join-Path $localBrain "blobs"
$blobsDst = Join-Path $ollamaRoot "blobs"

if (Test-Path $daenaManifestSrc) {
    Write-Host "[4] Copying daena-brain manifest to MODELS_ROOT\ollama..."
    if (-not $WhatIf) {
        New-Item -ItemType Directory -Force -Path $daenaManifestDst | Out-Null
        Copy-Item -Path (Join-Path $daenaManifestSrc "*") -Destination $daenaManifestDst -Force
    }
    Write-Host "    OK"
    if (Test-Path $blobsSrc) {
        Write-Host "[5] Copying missing blobs from local_brain to MODELS_ROOT\ollama\blobs..."
        if (-not $WhatIf) {
            New-Item -ItemType Directory -Force -Path $blobsDst | Out-Null
            Get-ChildItem $blobsSrc -File | ForEach-Object {
                $dest = Join-Path $blobsDst $_.Name
                if (-not (Test-Path $dest)) { Copy-Item $_.FullName -Destination $dest -Force }
            }
            Write-Host "    OK"
        } else {
            Write-Host "    (WhatIf: would copy blobs)"
        }
    }
} else {
    Write-Host "[4] daena-brain manifest not found; skipping"
}

Write-Host ""
Write-Host "Migration done. Next steps:" -ForegroundColor Green
Write-Host "  1. Set BRAIN_ROOT=$daenaBrain in .env (optional; code defaults to MODELS_ROOT/daena_brain when MODELS_ROOT is set)."
Write-Host "  2. Restart backend; brain_store, user_context, chat_history will use $daenaBrain."
Write-Host "  3. Ollama will use MODELS_ROOT/ollama (daena-brain now there)."
Write-Host "  4. After verifying, you can delete project local_brain (or run cleanup_old_upgrade.ps1 -Confirm to remove only backend\.venv and daena_tts)."
Write-Host ""
