# Start llama.cpp's llama-server with one of the 3 GGUF models
# available under MODELS_ROOT. Defaults to Qwen3-8B (general-purpose)
# because that's the best balance of speed + quality on an RTX 4060.
#
# Usage (PowerShell):
#   .\start-llama-server.ps1                  # default = qwen3-8b
#   .\start-llama-server.ps1 -Model coder     # Qwen3-Coder-30B-A3B
#   .\start-llama-server.ps1 -Model gemma     # Gemma-4-E4B
#   .\start-llama-server.ps1 -Port 8080       # change port (default 8080)
#   .\start-llama-server.ps1 -Ctx 32768       # larger context
#
# Leave this terminal open. Daena auto-detects via VLLM_BASE_URL
# (already set to http://127.0.0.1:8080/v1 in backend/.env).

param(
    [ValidateSet("qwen3-8b", "coder", "gemma")]
    [string]$Model = "qwen3-8b",
    [int]$Port = 8080,
    [int]$Ctx = 16384,
    [int]$NGL = 999
)

$ErrorActionPreference = "Stop"

$LlamaServer = "D:\Ideas\llama.cpp\llama-server.exe"
if (-not (Test-Path $LlamaServer)) {
    Write-Error "llama-server.exe not found at $LlamaServer. Install llama.cpp CUDA build first."
}

$ModelMap = @{
    "qwen3-8b" = "D:\Ideas\MODELS_ROOT\gguf\qwen3-8b\Qwen3-8B-Q4_K_M.gguf"
    "coder"    = "D:\Ideas\MODELS_ROOT\gguf\qwen3-coder-30b-a3b\Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf"
    "gemma"    = "D:\Ideas\MODELS_ROOT\gguf\gemma-4-e4b\gemma-4-E4B-it-Q4_K_M.gguf"
}

$ModelPath = $ModelMap[$Model]
if (-not (Test-Path $ModelPath)) {
    Write-Error "Model file missing at $ModelPath. Redownload under MODELS_ROOT\gguf\."
}

Write-Host "Starting llama-server:" -ForegroundColor Cyan
Write-Host "  Model:  $Model" -ForegroundColor Cyan
Write-Host "  File:   $ModelPath" -ForegroundColor Cyan
Write-Host "  Port:   $Port" -ForegroundColor Cyan
Write-Host "  Ctx:    $Ctx" -ForegroundColor Cyan
Write-Host "  GPU layers: $NGL (999 = offload everything to CUDA)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Endpoint: http://127.0.0.1:$Port/v1 (OpenAI-compatible)" -ForegroundColor Green
Write-Host "Daena backend picks this up automatically via VLLM_BASE_URL." -ForegroundColor Green
Write-Host ""

& $LlamaServer `
    -m $ModelPath `
    -c $Ctx `
    -ngl $NGL `
    --host 127.0.0.1 --port $Port `
    --jinja --parallel 1
