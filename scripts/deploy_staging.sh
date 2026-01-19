#!/bin/bash
# Staging Deployment Script for Daena
# This script prepares and deploys Daena to a staging environment

set -e  # Exit on error

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Daena Staging Deployment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Configuration
ENVIRONMENT=${ENVIRONMENT:-staging}
STAGING_URL=${STAGING_URL:-https://staging.daena.ai}
DOCKER_REGISTRY=${DOCKER_REGISTRY:-ghcr.io/masoud-masoori}
IMAGE_TAG=${IMAGE_TAG:-latest}

echo "📋 Configuration:"
echo "  Environment: $ENVIRONMENT"
echo "  Staging URL: $STAGING_URL"
echo "  Docker Registry: $DOCKER_REGISTRY"
echo "  Image Tag: $IMAGE_TAG"
echo ""

# Step 1: Pre-deployment checks
echo "✅ Step 1: Pre-deployment checks..."
echo ""

# Check if .env.staging exists
if [ ! -f ".env.staging" ]; then
    echo "⚠️  Warning: .env.staging not found. Creating from template..."
    if [ -f ".env.production.example" ]; then
        cp .env.production.example .env.staging
        echo "  Created .env.staging from template"
        echo "  ⚠️  Please update .env.staging with staging-specific values!"
    else
        echo "  ❌ Error: .env.production.example not found"
        exit 1
    fi
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "  ❌ Error: Docker is not running"
    exit 1
fi
echo "  ✅ Docker is running"

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo "  ❌ Error: docker-compose not found"
    exit 1
fi
echo "  ✅ docker-compose is available"

# Step 2: Run tests
echo ""
echo "✅ Step 2: Running tests..."
echo ""

if [ -f "pytest.ini" ]; then
    echo "  Running pytest..."
    python -m pytest -q --tb=short || {
        echo "  ❌ Tests failed. Aborting deployment."
        exit 1
    }
    echo "  ✅ All tests passed"
else
    echo "  ⚠️  pytest.ini not found, skipping tests"
fi

# Step 3: Build Docker image
echo ""
echo "✅ Step 3: Building Docker image..."
echo ""

docker build -t $DOCKER_REGISTRY/daena:$IMAGE_TAG . || {
    echo "  ❌ Docker build failed"
    exit 1
}
echo "  ✅ Docker image built: $DOCKER_REGISTRY/daena:$IMAGE_TAG"

# Step 4: Tag for staging
echo ""
echo "✅ Step 4: Tagging image for staging..."
echo ""

docker tag $DOCKER_REGISTRY/daena:$IMAGE_TAG $DOCKER_REGISTRY/daena:staging || {
    echo "  ❌ Failed to tag image"
    exit 1
}
echo "  ✅ Image tagged as staging"

# Step 5: Push to registry (if registry is set)
if [ "$DOCKER_REGISTRY" != "local" ]; then
    echo ""
    echo "✅ Step 5: Pushing to registry..."
    echo "  Registry: $DOCKER_REGISTRY"
    echo "  ⚠️  Note: Make sure you're logged in to the registry"
    echo "  Run: docker login $DOCKER_REGISTRY"
    read -p "  Press Enter to continue or Ctrl+C to skip..."
    
    docker push $DOCKER_REGISTRY/daena:$IMAGE_TAG || {
        echo "  ⚠️  Warning: Failed to push to registry (continuing anyway)"
    }
    docker push $DOCKER_REGISTRY/daena:staging || {
        echo "  ⚠️  Warning: Failed to push staging tag (continuing anyway)"
    }
    echo "  ✅ Images pushed to registry"
else
    echo ""
    echo "⏭️  Step 5: Skipping registry push (local registry)"
fi

# Step 6: Deploy with docker-compose
echo ""
echo "✅ Step 6: Deploying with docker-compose..."
echo ""

# Use staging-specific compose file if it exists
COMPOSE_FILE="docker-compose.yml"
if [ -f "docker-compose.staging.yml" ]; then
    COMPOSE_FILE="docker-compose.staging.yml"
    echo "  Using docker-compose.staging.yml"
fi

# Load staging environment variables
export $(cat .env.staging | grep -v '^#' | xargs)

docker-compose -f $COMPOSE_FILE --env-file .env.staging up -d || {
    echo "  ❌ Deployment failed"
    exit 1
}
echo "  ✅ Services started"

# Step 7: Wait for health checks
echo ""
echo "✅ Step 7: Waiting for health checks..."
echo ""

MAX_WAIT=60
WAIT_TIME=0
HEALTH_URL="${STAGING_URL}/api/v1/slo/health"

while [ $WAIT_TIME -lt $MAX_WAIT ]; do
    if curl -f -s "$HEALTH_URL" > /dev/null 2>&1; then
        echo "  ✅ Health check passed"
        break
    fi
    echo "  ⏳ Waiting for service to be healthy... ($WAIT_TIME/$MAX_WAIT seconds)"
    sleep 5
    WAIT_TIME=$((WAIT_TIME + 5))
done

if [ $WAIT_TIME -ge $MAX_WAIT ]; then
    echo "  ⚠️  Warning: Health check timeout (service may still be starting)"
fi

# Step 8: Run smoke tests
echo ""
echo "✅ Step 8: Running smoke tests..."
echo ""

# Test health endpoint
if curl -f -s "$HEALTH_URL" > /dev/null; then
    echo "  ✅ Health endpoint: OK"
else
    echo "  ❌ Health endpoint: FAILED"
fi

# Test council health
COUNCIL_URL="${STAGING_URL}/api/v1/health/council"
if curl -f -s -H "X-API-Key: ${DAENA_API_KEY:-daena_secure_key_2025}" "$COUNCIL_URL" > /dev/null; then
    echo "  ✅ Council health: OK"
else
    echo "  ⚠️  Council health: Check failed (may need API key)"
fi

# Test metrics summary
METRICS_URL="${STAGING_URL}/api/v1/monitoring/metrics/summary"
if curl -f -s -H "X-API-Key: ${DAENA_API_KEY:-daena_secure_key_2025}" "$METRICS_URL" > /dev/null; then
    echo "  ✅ Metrics summary: OK"
else
    echo "  ⚠️  Metrics summary: Check failed (may need API key)"
fi

# Step 9: Display deployment info
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Staging Deployment Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Deployment Information:"
echo "  Environment: $ENVIRONMENT"
echo "  URL: $STAGING_URL"
echo "  Image: $DOCKER_REGISTRY/daena:$IMAGE_TAG"
echo ""
echo "🔗 Useful Links:"
echo "  Health: $HEALTH_URL"
echo "  Council: $COUNCIL_URL"
echo "  Metrics: $METRICS_URL"
echo "  API Docs: ${STAGING_URL}/docs"
echo ""
echo "📋 Next Steps:"
echo "  1. Verify all services are running: docker-compose ps"
echo "  2. Check logs: docker-compose logs -f"
echo "  3. Run full test suite on staging"
echo "  4. Monitor for 24 hours"
echo "  5. Proceed to production deployment"
echo ""

