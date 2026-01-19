# ============================================================================
# Start Ollama Service
# ============================================================================
# This script starts Ollama with the correct OLLAMA_MODELS path
# ============================================================================

$ErrorActionPreference = "Continue"

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host "START OLLAMA SERVICE" -ForegroundColor Cyan
Write-Host "============================================================================" -ForegroundColor Cyan
Write-Host ""

# Get project root
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$modelsPath = Join-Path $projectRoot "local_brain"

Write-Host "[1/4] Setting OLLAMA_MODELS path..." -ForegroundColor White
$env:OLLAMA_MODELS = $modelsPath
Write-Host "[OK] OLLAMA_MODELS = $modelsPath" -ForegroundColor Green
Write-Host ""

# Check if Ollama is already running
Write-Host "[2/4] Checking if Ollama is already running..." -ForegroundColor White
try {
    $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 -ErrorAction Stop
    Write-Host "[OK] Ollama is already running!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Available models:" -ForegroundColor White
    $models = ($response.Content | ConvertFrom-Json).models
    foreach ($model in $models) {
        Write-Host "  - $($model.name)" -ForegroundColor Gray
    }
    Write-Host ""
    Write-Host "Ollama is ready to use!" -ForegroundColor Green
    pause
    exit 0
} catch {
    Write-Host "[INFO] Ollama is not running, will start it..." -ForegroundColor Yellow
}
Write-Host ""

# Find Ollama executable
Write-Host "[3/4] Finding Ollama executable..." -ForegroundColor White
$ollamaPaths = @(
    "C:\Users\$env:USERNAME\AppData\Local\Programs\Ollama\ollama.exe",
    "$env:ProgramFiles\Ollama\ollama.exe",
    "$env:ProgramFiles(x86)\Ollama\ollama.exe"
)

$ollamaExe = $null
foreach ($path in $ollamaPaths) {
    if (Test-Path $path) {
        $ollamaExe = $path
        break
    }
}

if (-not $ollamaExe) {
    Write-Host "[ERROR] Ollama executable not found" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Ollama from: https://ollama.ai" -ForegroundColor Yellow
    Write-Host "Or provide the path to ollama.exe" -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

Write-Host "[OK] Found Ollama at: $ollamaExe" -ForegroundColor Green
Write-Host ""

# Start Ollama
Write-Host "[4/4] Starting Ollama service..." -ForegroundColor White
Write-Host "  With OLLAMA_MODELS = $modelsPath" -ForegroundColor Gray
Write-Host ""

try {
    # Start Ollama in background
    $process = Start-Process -FilePath $ollamaExe -WindowStyle Hidden -PassThru -ErrorAction Stop
    Write-Host "[OK] Ollama start command sent (PID: $($process.Id))" -ForegroundColor Green
    Write-Host ""
    
    # Wait for Ollama to start
    Write-Host "Waiting for Ollama to start..." -ForegroundColor Gray
    $maxWait = 30
    $waited = 0
    $started = $false
    
    while ($waited -lt $maxWait) {
        Start-Sleep -Seconds 2
        $waited += 2
        
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 2 -ErrorAction Stop
            $started = $true
            break
        } catch {
            Write-Host "." -NoNewline -ForegroundColor Gray
        }
    }
    
    Write-Host ""
    Write-Host ""
    
    if ($started) {
        Write-Host "[SUCCESS] Ollama is now running!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Checking available models..." -ForegroundColor White
        try {
            $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 5 -ErrorAction Stop
            $models = ($response.Content | ConvertFrom-Json).models
            if ($models.Count -gt 0) {
                Write-Host "  Found $($models.Count) model(s):" -ForegroundColor Green
                foreach ($model in $models) {
                    Write-Host "    - $($model.name)" -ForegroundColor Gray
                }
            } else {
                Write-Host "  No models found yet" -ForegroundColor Yellow
                Write-Host "  Models should be in: $modelsPath" -ForegroundColor Gray
                Write-Host "  You may need to restart Ollama after setting OLLAMA_MODELS" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "  Could not list models: $($_.Exception.Message)" -ForegroundColor Yellow
        }
    } else {
        Write-Host "[WARN] Ollama may still be starting" -ForegroundColor Yellow
        Write-Host "  Wait a few more seconds and check: http://localhost:11434/api/tags" -ForegroundColor Gray
    }
    
} catch {
    Write-Host "[ERROR] Failed to start Ollama" -ForegroundColor Red
    Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "Try starting Ollama manually:" -ForegroundColor Yellow
    Write-Host "  1. Open a new PowerShell window" -ForegroundColor White
    Write-Host "  2. Set: `$env:OLLAMA_MODELS = '$modelsPath'" -ForegroundColor White
    Write-Host "  3. Run: Start-Process '$ollamaExe'" -ForegroundColor White
    Write-Host ""
    pause
    exit 1
}

Write-Host ""
Write-Host "============================================================================" -ForegroundColor Green
Write-Host "[OK] OLLAMA IS READY" -ForegroundColor Green
Write-Host "============================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "You can now:" -ForegroundColor Cyan
Write-Host "  1. Create daena-brain model: cd models\trained && .\create_daena_brain_api.ps1" -ForegroundColor White
Write-Host "  2. Verify models: python scripts\verify_models.py" -ForegroundColor White
Write-Host "  3. Check brain status: http://127.0.0.1:8000/api/v1/brain/status" -ForegroundColor White
Write-Host ""
pause




