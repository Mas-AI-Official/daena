# ============================================================================
# Check Existing Models and Training Status
# ============================================================================
# This script checks what models exist and if daena-brain is already trained
# ============================================================================

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "CHECK EXISTING MODELS & TRAINING STATUS" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Get project root
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$localBrainPath = Join-Path $projectRoot "local_brain"
$modelsPath = Join-Path $localBrainPath "models"
$trainedPath = Join-Path $projectRoot "models\trained"

# Step 1: Check local_brain directory
Write-Host "[1/5] Checking local_brain directory..." -ForegroundColor White
if (Test-Path $localBrainPath) {
    Write-Host "[OK] local_brain directory exists" -ForegroundColor Green
    Write-Host "  Path: $localBrainPath" -ForegroundColor Gray
} else {
    Write-Host "[ERROR] local_brain directory not found" -ForegroundColor Red
    Write-Host "  Expected: $localBrainPath" -ForegroundColor Gray
    exit 1
}
Write-Host ""

# Step 2: Check models in local_brain
Write-Host "[2/5] Checking models in local_brain..." -ForegroundColor White
$foundModels = @()

if (Test-Path $modelsPath) {
    Write-Host "[OK] Models directory exists" -ForegroundColor Green
    
    # Check manifests
    $manifestsPath = Join-Path $modelsPath "manifests\registry.ollama.ai\library"
    if (Test-Path $manifestsPath) {
        Write-Host "  Checking manifests..." -ForegroundColor Gray
        Get-ChildItem -Path $manifestsPath -Directory -Recurse | ForEach-Object {
            $modelPath = $_.FullName.Replace($manifestsPath, "").TrimStart('\')
            if ($modelPath -match "^(qwen|llama|daena)") {
                $foundModels += $modelPath
                Write-Host "    - Found: $modelPath" -ForegroundColor Green
            }
        }
    }
    
    # Check blobs
    $blobsPath = Join-Path $modelsPath "blobs"
    if (Test-Path $blobsPath) {
        $blobCount = (Get-ChildItem -Path $blobsPath -File).Count
        Write-Host "  Found $blobCount blob file(s)" -ForegroundColor Gray
    }
} else {
    Write-Host "[WARN] Models directory not found" -ForegroundColor Yellow
}
Write-Host ""

# Step 3: Check what Ollama sees
Write-Host "[3/5] Checking what Ollama sees..." -ForegroundColor White
$ollamaModels = @()
try {
    $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
    $ollamaModels = ($response.Content | ConvertFrom-Json).models
    Write-Host "[OK] Ollama is running" -ForegroundColor Green
    
    if ($ollamaModels.Count -gt 0) {
        Write-Host "  Models available in Ollama ($($ollamaModels.Count)):" -ForegroundColor White
        foreach ($model in $ollamaModels) {
            $marker = ""
            if ($model.name -eq "daena-brain") {
                $marker = " [TRAINED - EXISTS!]"
            } elseif ($model.name -match "qwen2\.5:7b-instruct") {
                $marker = " [DEFAULT]"
            } elseif ($model.name -match "qwen2\.5:14b") {
                $marker = " [LARGE]"
            }
            Write-Host "    - $($model.name)$marker" -ForegroundColor Gray
        }
    } else {
        Write-Host "  [WARN] No models found in Ollama" -ForegroundColor Yellow
        Write-Host "    Models exist in local_brain but Ollama doesn't see them" -ForegroundColor Gray
        Write-Host "    Need to restart Ollama with OLLAMA_MODELS set" -ForegroundColor Gray
    }
} catch {
    Write-Host "[ERROR] Ollama is not running: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "  Start it with: scripts\START_OLLAMA.bat" -ForegroundColor Yellow
}
Write-Host ""

# Step 4: Check if daena-brain is already trained
Write-Host "[4/5] Checking if daena-brain is already trained..." -ForegroundColor White
$daenaBrainExists = $false
$daenaBrainInOllama = $ollamaModels | Where-Object { $_.name -eq "daena-brain" }

if ($daenaBrainInOllama) {
    $daenaBrainExists = $true
    Write-Host "[SUCCESS] daena-brain is already trained and available in Ollama!" -ForegroundColor Green
    Write-Host "  Name: $($daenaBrainInOllama.name)" -ForegroundColor Gray
    Write-Host "  Size: $($daenaBrainInOllama.size)" -ForegroundColor Gray
    Write-Host "  Modified: $($daenaBrainInOllama.modified_at)" -ForegroundColor Gray
} else {
    Write-Host "[INFO] daena-brain is not yet created in Ollama" -ForegroundColor Yellow
    
    # Check if Modelfile exists
    $modelfilePath = Join-Path $trainedPath "Modelfile"
    if (Test-Path $modelfilePath) {
        Write-Host "  [OK] Modelfile exists - ready to create" -ForegroundColor Green
        Write-Host "    Path: $modelfilePath" -ForegroundColor Gray
    } else {
        Write-Host "  [WARN] Modelfile not found" -ForegroundColor Yellow
        Write-Host "    Expected: $modelfilePath" -ForegroundColor Gray
    }
}
Write-Host ""

# Step 5: Summary and recommendations
Write-Host "[5/5] Summary and Recommendations..." -ForegroundColor White
Write-Host ""

if ($daenaBrainExists) {
    Write-Host "[SUCCESS] daena-brain is ready to use!" -ForegroundColor Green
    Write-Host "  No training needed - model already exists" -ForegroundColor White
    Write-Host ""
    Write-Host "You can:" -ForegroundColor Cyan
    Write-Host "  1. Use daena-brain immediately - backend will auto-detect it" -ForegroundColor White
    Write-Host "  2. Test it: python scripts\verify_models.py" -ForegroundColor White
    Write-Host "  3. Check status: http://127.0.0.1:8000/api/v1/brain/status" -ForegroundColor White
} else {
    Write-Host "[ACTION NEEDED] daena-brain needs to be created" -ForegroundColor Yellow
    Write-Host ""
    
    if ($ollamaModels.Count -eq 0) {
        Write-Host "  Issue: Ollama doesn't see any models" -ForegroundColor Red
        Write-Host "  Solution:" -ForegroundColor Cyan
        Write-Host "    1. Restart Ollama with OLLAMA_MODELS set" -ForegroundColor White
        Write-Host "       Run: scripts\START_OLLAMA.bat" -ForegroundColor Green
        Write-Host "    2. Then create daena-brain: cd models\trained && create_daena_brain.bat" -ForegroundColor White
    } else {
        Write-Host "  Models available in Ollama, but daena-brain not created yet" -ForegroundColor Yellow
        Write-Host "  Solution:" -ForegroundColor Cyan
        Write-Host "    Create daena-brain: cd models\trained && create_daena_brain.bat" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Green
Write-Host "[OK] CHECK COMPLETE" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""




