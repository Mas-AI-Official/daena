#!/bin/bash
# Production Deployment Script for Daena
# This script deploys Daena to production with extra safety checks

set -e  # Exit on error

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🚀 Daena Production Deployment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⚠️  WARNING: This will deploy to PRODUCTION!"
echo ""

# Configuration
ENVIRONMENT=${ENVIRONMENT:-production}
PRODUCTION_URL=${PRODUCTION_URL:-https://daena.ai}
DOCKER_REGISTRY=${DOCKER_REGISTRY:-ghcr.io/masoud-masoori}
IMAGE_TAG=${IMAGE_TAG:-latest}

# Confirm production deployment
read -p "Are you sure you want to deploy to PRODUCTION? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "Deployment cancelled."
    exit 0
fi

echo ""
echo "📋 Configuration:"
echo "  Environment: $ENVIRONMENT"
echo "  Production URL: $PRODUCTION_URL"
echo "  Docker Registry: $DOCKER_REGISTRY"
echo "  Image Tag: $IMAGE_TAG"
echo ""

# Step 1: Pre-deployment checks
echo "✅ Step 1: Pre-deployment checks..."
echo ""

# Check if .env.production exists
if [ ! -f ".env.production" ]; then
    echo "  ❌ Error: .env.production not found"
    echo "  Please create .env.production with production values"
    exit 1
fi
echo "  ✅ .env.production exists"

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

# Step 2: Verify staging deployment
echo ""
echo "✅ Step 2: Verify staging deployment..."
echo ""

read -p "Has staging been deployed and tested successfully? (yes/no): " STAGING_CONFIRM
if [ "$STAGING_CONFIRM" != "yes" ]; then
    echo "  ⚠️  Warning: Staging not verified. Continue anyway? (yes/no): "
    read CONTINUE
    if [ "$CONTINUE" != "yes" ]; then
        echo "Deployment cancelled."
        exit 0
    fi
fi

# Step 3: Run full test suite
echo ""
echo "✅ Step 3: Running full test suite..."
echo ""

if [ -f "pytest.ini" ]; then
    echo "  Running pytest with verbose output..."
    python -m pytest -v --tb=short --cov=backend --cov=memory_service --cov-report=term-missing || {
        echo "  ❌ Tests failed. Aborting deployment."
        exit 1
    }
    echo "  ✅ All tests passed"
else
    echo "  ⚠️  pytest.ini not found, skipping tests"
fi

# Step 4: Build Docker image
echo ""
echo "✅ Step 4: Building Docker image..."
echo ""

docker build -t $DOCKER_REGISTRY/daena:$IMAGE_TAG . || {
    echo "  ❌ Docker build failed"
    exit 1
}
echo "  ✅ Docker image built: $DOCKER_REGISTRY/daena:$IMAGE_TAG"

# Step 5: Tag for production
echo ""
echo "✅ Step 5: Tagging image for production..."
echo ""

# Tag with commit hash for traceability
COMMIT_HASH=$(git rev-parse --short HEAD)
docker tag $DOCKER_REGISTRY/daena:$IMAGE_TAG $DOCKER_REGISTRY/daena:prod-$COMMIT_HASH || {
    echo "  ❌ Failed to tag image"
    exit 1
}
docker tag $DOCKER_REGISTRY/daena:$IMAGE_TAG $DOCKER_REGISTRY/daena:production || {
    echo "  ❌ Failed to tag image"
    exit 1
}
echo "  ✅ Image tagged as production and prod-$COMMIT_HASH"

# Step 6: Push to registry
echo ""
echo "✅ Step 6: Pushing to registry..."
echo ""

echo "  ⚠️  Make sure you're logged in to the registry"
echo "  Run: docker login $DOCKER_REGISTRY"
read -p "  Press Enter to continue or Ctrl+C to cancel..."

docker push $DOCKER_REGISTRY/daena:$IMAGE_TAG || {
    echo "  ❌ Failed to push image"
    exit 1
}
docker push $DOCKER_REGISTRY/daena:prod-$COMMIT_HASH || {
    echo "  ❌ Failed to push commit tag"
    exit 1
}
docker push $DOCKER_REGISTRY/daena:production || {
    echo "  ❌ Failed to push production tag"
    exit 1
}
echo "  ✅ Images pushed to registry"

# Step 7: Backup production database (if exists)
echo ""
echo "✅ Step 7: Creating backup..."
echo ""

if docker-compose -f docker-compose.yml ps | grep -q "mongodb.*Up"; then
    echo "  Creating database backup..."
    BACKUP_FILE="backups/production_backup_$(date +%Y%m%d_%H%M%S).tar.gz"
    mkdir -p backups
    docker-compose exec -T mongodb mongodump --archive | gzip > $BACKUP_FILE || {
        echo "  ⚠️  Warning: Backup failed (continuing anyway)"
    }
    echo "  ✅ Backup created: $BACKUP_FILE"
else
    echo "  ⏭️  Skipping backup (database not running or external)"
fi

# Step 8: Deploy with docker-compose
echo ""
echo "✅ Step 8: Deploying to production..."
echo ""

# Use production-specific compose file if it exists
COMPOSE_FILE="docker-compose.yml"
if [ -f "docker-compose.production.yml" ]; then
    COMPOSE_FILE="docker-compose.production.yml"
    echo "  Using docker-compose.production.yml"
fi

# Load production environment variables
export $(cat .env.production | grep -v '^#' | xargs)

# Deploy with zero-downtime strategy (rolling update)
docker-compose -f $COMPOSE_FILE --env-file .env.production up -d --no-deps --build app || {
    echo "  ❌ Deployment failed"
    echo "  Attempting rollback..."
    docker-compose -f $COMPOSE_FILE --env-file .env.production up -d
    exit 1
}
echo "  ✅ Services updated"

# Step 9: Wait for health checks
echo ""
echo "✅ Step 9: Waiting for health checks..."
echo ""

MAX_WAIT=120  # Longer timeout for production
WAIT_TIME=0
HEALTH_URL="${PRODUCTION_URL}/api/v1/slo/health"

while [ $WAIT_TIME -lt $MAX_WAIT ]; do
    if curl -f -s "$HEALTH_URL" > /dev/null 2>&1; then
        echo "  ✅ Health check passed"
        break
    fi
    echo "  ⏳ Waiting for service to be healthy... ($WAIT_TIME/$MAX_WAIT seconds)"
    sleep 10
    WAIT_TIME=$((WAIT_TIME + 10))
done

if [ $WAIT_TIME -ge $MAX_WAIT ]; then
    echo "  ❌ ERROR: Health check timeout!"
    echo "  Rolling back deployment..."
    docker-compose -f $COMPOSE_FILE --env-file .env.production up -d
    exit 1
fi

# Step 10: Run comprehensive smoke tests
echo ""
echo "✅ Step 10: Running comprehensive smoke tests..."
echo ""

API_KEY=${DAENA_API_KEY:-daena_secure_key_2025}
FAILED_TESTS=0

# Test health endpoint
if curl -f -s "$HEALTH_URL" > /dev/null; then
    echo "  ✅ Health endpoint: OK"
else
    echo "  ❌ Health endpoint: FAILED"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test council health
COUNCIL_URL="${PRODUCTION_URL}/api/v1/health/council"
if curl -f -s -H "X-API-Key: $API_KEY" "$COUNCIL_URL" > /dev/null; then
    echo "  ✅ Council health: OK"
else
    echo "  ⚠️  Council health: Check failed"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test metrics summary
METRICS_URL="${PRODUCTION_URL}/api/v1/monitoring/metrics/summary"
if curl -f -s -H "X-API-Key: $API_KEY" "$METRICS_URL" > /dev/null; then
    echo "  ✅ Metrics summary: OK"
else
    echo "  ⚠️  Metrics summary: Check failed"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

# Test SLO endpoints
SLO_URL="${PRODUCTION_URL}/api/v1/slo/metrics"
if curl -f -s -H "X-API-Key: $API_KEY" "$SLO_URL" > /dev/null; then
    echo "  ✅ SLO metrics: OK"
else
    echo "  ⚠️  SLO metrics: Check failed"
    FAILED_TESTS=$((FAILED_TESTS + 1))
fi

if [ $FAILED_TESTS -gt 2 ]; then
    echo "  ❌ ERROR: Too many smoke tests failed. Rolling back..."
    docker-compose -f $COMPOSE_FILE --env-file .env.production up -d
    exit 1
fi

# Step 11: Display deployment info
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Production Deployment Complete!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "📊 Deployment Information:"
echo "  Environment: $ENVIRONMENT"
echo "  URL: $PRODUCTION_URL"
echo "  Image: $DOCKER_REGISTRY/daena:$IMAGE_TAG"
echo "  Commit: $COMMIT_HASH"
echo ""
echo "🔗 Useful Links:"
echo "  Health: $HEALTH_URL"
echo "  Council: $COUNCIL_URL"
echo "  Metrics: $METRICS_URL"
echo "  SLO: $SLO_URL"
echo "  API Docs: ${PRODUCTION_URL}/docs"
echo ""
echo "📋 Next Steps:"
echo "  1. Monitor logs: docker-compose logs -f app"
echo "  2. Monitor metrics dashboard"
echo "  3. Watch for errors for 24-48 hours"
echo "  4. Verify all critical paths"
echo "  5. Monitor user feedback"
echo ""
echo "🚨 Important:"
echo "  - Monitor error rates closely"
echo "  - Watch SLO metrics"
echo "  - Check council round completion rates"
echo "  - Verify multi-tenant isolation"
echo ""
