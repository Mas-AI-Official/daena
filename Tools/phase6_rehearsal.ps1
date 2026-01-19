# Phase 6 Task 3 Rehearsal Script
# Runs cutover verification, disaster recovery drill, and monitoring endpoint checks
# Saves snapshots for review

param(
    [string]$OutputDir = "artifacts/phase6_rehearsal",
    [switch]$SkipDrill = $false,
    [switch]$SkipMonitoring = $false
)

$ErrorActionPreference = "Stop"

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "Phase 6 Task 3 Rehearsal" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

# Create output directory
$outputPath = New-Item -ItemType Directory -Force -Path $OutputDir
Write-Host "Output directory: $outputPath" -ForegroundColor Green
Write-Host ""

# Step 1: Run cutover verification
Write-Host "Step 1: Running cutover verification..." -ForegroundColor Yellow
try {
    $cutoverOutput = python Tools/daena_cutover.py --verify-only 2>&1 | Out-String
    # Save raw output
    $cutoverOutput | Out-File -FilePath "$outputPath/cutover_verification.txt" -Encoding UTF8
    # Try to parse as JSON if possible
    try {
        $cutoverJson = $cutoverOutput | ConvertFrom-Json -ErrorAction SilentlyContinue
        if ($cutoverJson) {
            $cutoverJson | ConvertTo-Json -Depth 10 | Out-File -FilePath "$outputPath/cutover_verification.json" -Encoding UTF8
        }
    } catch {
        # Not JSON, that's okay
    }
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Cutover verification passed" -ForegroundColor Green
        Write-Host $cutoverOutput
    } else {
        Write-Host "⚠️ Cutover verification returned non-zero exit code: $LASTEXITCODE" -ForegroundColor Yellow
        Write-Host $cutoverOutput
    }
} catch {
    Write-Host "❌ Cutover verification failed: $_" -ForegroundColor Red
    Write-Host "Continuing with other steps..." -ForegroundColor Yellow
}
Write-Host ""

# Step 2: Run disaster recovery drill
if (-not $SkipDrill) {
    Write-Host "Step 2: Running disaster recovery drill..." -ForegroundColor Yellow
    try {
        $drillOutput = python Tools/daena_drill.py 2>&1 | Out-String
        # Save raw output
        $drillOutput | Out-File -FilePath "$outputPath/drill_report.txt" -Encoding UTF8
        # Try to parse as JSON if possible
        try {
            $drillJson = $drillOutput | ConvertFrom-Json -ErrorAction SilentlyContinue
            if ($drillJson) {
                $drillJson | ConvertTo-Json -Depth 10 | Out-File -FilePath "$outputPath/drill_report.json" -Encoding UTF8
            }
        } catch {
            # Not JSON, that's okay
        }
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Disaster recovery drill completed" -ForegroundColor Green
            Write-Host $drillOutput
        } else {
            Write-Host "⚠️ Drill returned non-zero exit code: $LASTEXITCODE" -ForegroundColor Yellow
            Write-Host $drillOutput
        }
    } catch {
        Write-Host "❌ Disaster recovery drill failed: $_" -ForegroundColor Red
        Write-Host "Continuing with other steps..." -ForegroundColor Yellow
    }
    Write-Host ""
} else {
    Write-Host "Step 2: Skipped (--SkipDrill flag)" -ForegroundColor Gray
    Write-Host ""
}

# Step 3: Check monitoring endpoints
if (-not $SkipMonitoring) {
    Write-Host "Step 3: Checking monitoring endpoints..." -ForegroundColor Yellow
    
    # Check if server is running (optional - will skip if not available)
    $baseUrl = "http://localhost:8000"
    $apiKey = "daena_secure_key_2025"
    
    $endpoints = @(
        @{ Path = "/api/v1/health/council"; Name = "Council Health" },
        @{ Path = "/api/v1/registry/summary"; Name = "Registry Summary" },
        @{ Path = "/api/v1/system/summary"; Name = "System Summary" },
        @{ Path = "/api/v1/monitoring/metrics"; Name = "Monitoring Metrics" }
    )
    
    $monitoringResults = @()
    
    foreach ($endpoint in $endpoints) {
        try {
            Write-Host "  Checking $($endpoint.Name)..." -ForegroundColor Gray
            $response = Invoke-WebRequest -Uri "$baseUrl$($endpoint.Path)" `
                -Headers @{ "X-API-Key" = $apiKey } `
                -Method GET `
                -TimeoutSec 5 `
                -ErrorAction SilentlyContinue
            
            if ($response.StatusCode -eq 200) {
                $content = $response.Content | ConvertFrom-Json
                $monitoringResults += @{
                    endpoint = $endpoint.Path
                    name = $endpoint.Name
                    status = "success"
                    status_code = $response.StatusCode
                    data = $content
                }
                Write-Host "    ✅ $($endpoint.Name) - OK" -ForegroundColor Green
            } else {
                $monitoringResults += @{
                    endpoint = $endpoint.Path
                    name = $endpoint.Name
                    status = "error"
                    status_code = $response.StatusCode
                }
                Write-Host "    ⚠️ $($endpoint.Name) - HTTP $($response.StatusCode)" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "    ⚠️ $($endpoint.Name) - Not available (server may not be running)" -ForegroundColor Yellow
            $monitoringResults += @{
                endpoint = $endpoint.Path
                name = $endpoint.Name
                status = "unavailable"
                error = $_.Exception.Message
            }
        }
    }
    
    # Save monitoring results
    $monitoringResults | ConvertTo-Json -Depth 10 | Out-File -FilePath "$outputPath/monitoring_endpoints.json" -Encoding UTF8
    Write-Host ""
} else {
    Write-Host "Step 3: Skipped (--SkipMonitoring flag)" -ForegroundColor Gray
    Write-Host ""
}

# Step 4: Generate governance artifacts snapshot
Write-Host "Step 4: Generating governance artifacts snapshot..." -ForegroundColor Yellow
try {
    $governanceOutput = python Tools/generate_governance_artifacts.py --output-dir "$outputPath/governance" --skip-drill 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Governance artifacts generated" -ForegroundColor Green
    } else {
        Write-Host "⚠️ Governance artifacts generation returned non-zero exit code: $LASTEXITCODE" -ForegroundColor Yellow
        Write-Host $governanceOutput
    }
} catch {
    Write-Host "❌ Governance artifacts generation failed: $_" -ForegroundColor Red
    Write-Host "Continuing..." -ForegroundColor Yellow
}
Write-Host ""

# Step 5: Create summary report
Write-Host "Step 5: Creating summary report..." -ForegroundColor Yellow
$summary = @{
    timestamp = (Get-Date).ToUniversalTime().ToString("o")
    rehearsal_version = "1.0"
    output_directory = $outputPath.FullName
    steps_completed = @(
        "cutover_verification"
        if (-not $SkipDrill) { "disaster_recovery_drill" }
        if (-not $SkipMonitoring) { "monitoring_endpoints" }
        "governance_artifacts"
    )
    artifacts = @(
        "cutover_verification.json"
        if (-not $SkipDrill) { "drill_report.json" }
        if (-not $SkipMonitoring) { "monitoring_endpoints.json" }
        "governance/"
    )
}

$summary | ConvertTo-Json -Depth 10 | Out-File -FilePath "$outputPath/rehearsal_summary.json" -Encoding UTF8

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "✅ Phase 6 Task 3 Rehearsal Complete" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Write-Host "Artifacts saved to: $($outputPath.FullName)" -ForegroundColor Cyan
Write-Host ""
Write-Host "Files generated:" -ForegroundColor Yellow
Get-ChildItem -Path $outputPath -Recurse -File | ForEach-Object {
    Write-Host "  • $($_.FullName.Replace($outputPath.FullName, '.'))" -ForegroundColor Gray
}
Write-Host ""

