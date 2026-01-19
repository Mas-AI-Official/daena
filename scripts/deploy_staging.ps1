# Staging Deployment Script for Daena (PowerShell)
# This script prepares and deploys Daena to a staging environment

$ErrorActionPreference = "Stop"

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "🚀 Daena Staging Deployment" -ForegroundColor Cyan
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""

# Configuration
$ENVIRONMENT = if ($env:ENVIRONMENT) { $env:ENVIRONMENT } else { "staging" }
$STAGING_URL = if ($env:STAGING_URL) { $env:STAGING_URL } else { "https://staging.daena.ai" }
$DOCKER_REGISTRY = if ($env:DOCKER_REGISTRY) { $env:DOCKER_REGISTRY } else { "ghcr.io/masoud-masoori" }
$IMAGE_TAG = if ($env:IMAGE_TAG) { $env:IMAGE_TAG } else { "latest" }

Write-Host "📋 Configuration:" -ForegroundColor Yellow
Write-Host "  Environment: $ENVIRONMENT"
Write-Host "  Staging URL: $STAGING_URL"
Write-Host "  Docker Registry: $DOCKER_REGISTRY"
Write-Host "  Image Tag: $IMAGE_TAG"
Write-Host ""

# Step 1: Pre-deployment checks
Write-Host "✅ Step 1: Pre-deployment checks..." -ForegroundColor Green
Write-Host ""

# Check if .env.staging exists
if (-not (Test-Path ".env.staging")) {
    Write-Host "⚠️  Warning: .env.staging not found. Creating from template..." -ForegroundColor Yellow
    if (Test-Path ".env.production.example") {
        Copy-Item ".env.production.example" ".env.staging"
        Write-Host "  Created .env.staging from template" -ForegroundColor Green
        Write-Host "  ⚠️  Please update .env.staging with staging-specific values!" -ForegroundColor Yellow
    } else {
        Write-Host "  ❌ Error: .env.production.example not found" -ForegroundColor Red
        exit 1
    }
}

# Check if Docker is running
try {
    docker info | Out-Null
    Write-Host "  ✅ Docker is running" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Error: Docker is not running" -ForegroundColor Red
    exit 1
}

# Check if docker-compose is available
try {
    docker-compose --version | Out-Null
    Write-Host "  ✅ docker-compose is available" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Error: docker-compose not found" -ForegroundColor Red
    exit 1
}

# Step 2: Run tests
Write-Host ""
Write-Host "✅ Step 2: Running tests..." -ForegroundColor Green
Write-Host ""

if (Test-Path "pytest.ini") {
    Write-Host "  Running pytest..."
    python -m pytest -q --tb=short
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ❌ Tests failed. Aborting deployment." -ForegroundColor Red
        exit 1
    }
    Write-Host "  ✅ All tests passed" -ForegroundColor Green
} else {
    Write-Host "  ⚠️  pytest.ini not found, skipping tests" -ForegroundColor Yellow
}

# Step 3: Build Docker image
Write-Host ""
Write-Host "✅ Step 3: Building Docker image..." -ForegroundColor Green
Write-Host ""

docker build -t "${DOCKER_REGISTRY}/daena:${IMAGE_TAG}" .
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Docker build failed" -ForegroundColor Red
    exit 1
}
Write-Host "  ✅ Docker image built: ${DOCKER_REGISTRY}/daena:${IMAGE_TAG}" -ForegroundColor Green

# Step 4: Tag for staging
Write-Host ""
Write-Host "✅ Step 4: Tagging image for staging..." -ForegroundColor Green
Write-Host ""

docker tag "${DOCKER_REGISTRY}/daena:${IMAGE_TAG}" "${DOCKER_REGISTRY}/daena:staging"
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Failed to tag image" -ForegroundColor Red
    exit 1
}
Write-Host "  ✅ Image tagged as staging" -ForegroundColor Green

# Step 5: Push to registry (if registry is set)
if ($DOCKER_REGISTRY -ne "local") {
    Write-Host ""
    Write-Host "✅ Step 5: Pushing to registry..." -ForegroundColor Green
    Write-Host "  Registry: $DOCKER_REGISTRY"
    Write-Host "  ⚠️  Note: Make sure you're logged in to the registry" -ForegroundColor Yellow
    Write-Host "  Run: docker login $DOCKER_REGISTRY"
    Read-Host "  Press Enter to continue or Ctrl+C to skip..."
    
    docker push "${DOCKER_REGISTRY}/daena:${IMAGE_TAG}"
    docker push "${DOCKER_REGISTRY}/daena:staging"
    Write-Host "  ✅ Images pushed to registry" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "⏭️  Step 5: Skipping registry push (local registry)" -ForegroundColor Yellow
}

# Step 6: Deploy with docker-compose
Write-Host ""
Write-Host "✅ Step 6: Deploying with docker-compose..." -ForegroundColor Green
Write-Host ""

# Use staging-specific compose file if it exists
$COMPOSE_FILE = "docker-compose.yml"
if (Test-Path "docker-compose.staging.yml") {
    $COMPOSE_FILE = "docker-compose.staging.yml"
    Write-Host "  Using docker-compose.staging.yml"
}

# Load staging environment variables
Get-Content ".env.staging" | ForEach-Object {
    if ($_ -match '^([^#][^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
    }
}

docker-compose -f $COMPOSE_FILE --env-file .env.staging up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ❌ Deployment failed" -ForegroundColor Red
    exit 1
}
Write-Host "  ✅ Services started" -ForegroundColor Green

# Step 7: Wait for health checks
Write-Host ""
Write-Host "✅ Step 7: Waiting for health checks..." -ForegroundColor Green
Write-Host ""

$MAX_WAIT = 60
$WAIT_TIME = 0
$HEALTH_URL = "${STAGING_URL}/api/v1/slo/health"

while ($WAIT_TIME -lt $MAX_WAIT) {
    try {
        $response = Invoke-WebRequest -Uri $HEALTH_URL -Method Get -TimeoutSec 5 -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "  ✅ Health check passed" -ForegroundColor Green
            break
        }
    } catch {
        # Continue waiting
    }
    Write-Host "  ⏳ Waiting for service to be healthy... ($WAIT_TIME/$MAX_WAIT seconds)" -ForegroundColor Yellow
    Start-Sleep -Seconds 5
    $WAIT_TIME += 5
}

if ($WAIT_TIME -ge $MAX_WAIT) {
    Write-Host "  ⚠️  Warning: Health check timeout (service may still be starting)" -ForegroundColor Yellow
}

# Step 8: Run smoke tests
Write-Host ""
Write-Host "✅ Step 8: Running smoke tests..." -ForegroundColor Green
Write-Host ""

$API_KEY = if ($env:DAENA_API_KEY) { $env:DAENA_API_KEY } else { "daena_secure_key_2025" }

# Test health endpoint
try {
    $response = Invoke-WebRequest -Uri $HEALTH_URL -Method Get -TimeoutSec 5
    Write-Host "  ✅ Health endpoint: OK" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Health endpoint: FAILED" -ForegroundColor Red
}

# Test council health
$COUNCIL_URL = "${STAGING_URL}/api/v1/health/council"
try {
    $headers = @{ "X-API-Key" = $API_KEY }
    $response = Invoke-WebRequest -Uri $COUNCIL_URL -Method Get -Headers $headers -TimeoutSec 5
    Write-Host "  ✅ Council health: OK" -ForegroundColor Green
} catch {
    Write-Host "  ⚠️  Council health: Check failed (may need API key)" -ForegroundColor Yellow
}

# Test metrics summary
$METRICS_URL = "${STAGING_URL}/api/v1/monitoring/metrics/summary"
try {
    $headers = @{ "X-API-Key" = $API_KEY }
    $response = Invoke-WebRequest -Uri $METRICS_URL -Method Get -Headers $headers -TimeoutSec 5
    Write-Host "  ✅ Metrics summary: OK" -ForegroundColor Green
} catch {
    Write-Host "  ⚠️  Metrics summary: Check failed (may need API key)" -ForegroundColor Yellow
}

# Step 9: Display deployment info
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "✅ Staging Deployment Complete!" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Write-Host "📊 Deployment Information:" -ForegroundColor Yellow
Write-Host "  Environment: $ENVIRONMENT"
Write-Host "  URL: $STAGING_URL"
Write-Host "  Image: ${DOCKER_REGISTRY}/daena:${IMAGE_TAG}"
Write-Host ""
Write-Host "🔗 Useful Links:" -ForegroundColor Yellow
Write-Host "  Health: $HEALTH_URL"
Write-Host "  Council: $COUNCIL_URL"
Write-Host "  Metrics: $METRICS_URL"
Write-Host "  API Docs: ${STAGING_URL}/docs"
Write-Host ""
Write-Host "📋 Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Verify all services are running: docker-compose ps"
Write-Host "  2. Check logs: docker-compose logs -f"
Write-Host "  3. Run full test suite on staging"
Write-Host "  4. Monitor for 24 hours"
Write-Host "  5. Proceed to production deployment"
Write-Host ""

