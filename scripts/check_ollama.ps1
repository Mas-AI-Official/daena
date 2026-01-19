# Quick check if Ollama is running
try {
    $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
    $models = ($response.Content | ConvertFrom-Json).models
    Write-Host "[OK] Ollama is running!"
    Write-Host ""
    Write-Host "Found $($models.Count) model(s):"
    foreach ($m in $models) {
        Write-Host "  - $($m.name)"
    }
    exit 0
} catch {
    Write-Host "[WARN] Ollama may still be starting"
    Write-Host "  Error: $($_.Exception.Message)"
    exit 1
}




