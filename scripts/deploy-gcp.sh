#!/usr/bin/env bash
# ==============================================================
# Daena V2 GCP Deployment Script
# ==============================================================
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - Docker installed
#   - .env.production filled with real values
#   - Artifact Registry repo created (auto-created below)
#
# Usage:
#   ./scripts/deploy-gcp.sh              Deploy latest
#   ./scripts/deploy-gcp.sh --skip-build Deploy from existing :latest
#   ./scripts/deploy-gcp.sh --dry-run    Show commands without executing
# ==============================================================

set -euo pipefail

# --- Configuration ---
PROJECT_ID="daena-467315"
REGION="us-central1"
REPO_NAME="daena"
IMAGE_NAME="daena"
SERVICE_NAME="daena"
DOMAIN="daena.mas-ai.co"
DAENA_VERSION="2.0.1"

# Derived
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO_NAME}"
GIT_SHA=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TAG="${DAENA_VERSION}-${GIT_SHA}"
FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${TAG}"
LATEST_IMAGE="${REGISTRY}/${IMAGE_NAME}:latest"

# --- Flags ---
SKIP_BUILD=false
DRY_RUN=false
for arg in "$@"; do
    case $arg in
        --skip-build) SKIP_BUILD=true ;;
        --dry-run)    DRY_RUN=true ;;
    esac
done

run_cmd() {
    echo "[CMD] $*"
    if [ "$DRY_RUN" = false ]; then
        "$@"
    fi
}

echo "============================================"
echo "[Daena Deploy] V${DAENA_VERSION}"
echo "[Daena Deploy] Project: ${PROJECT_ID}"
echo "[Daena Deploy] Region:  ${REGION}"
echo "[Daena Deploy] Image:   ${FULL_IMAGE}"
echo "[Daena Deploy] Git SHA: ${GIT_SHA}"
echo "[Daena Deploy] Date:    ${BUILD_DATE}"
echo "============================================"

# --- Step 0: One-time setup (idempotent) ---
echo ""
echo "[Step 0] Ensuring Artifact Registry repo exists..."
run_cmd gcloud artifacts repositories describe "${REPO_NAME}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" 2>/dev/null || \
run_cmd gcloud artifacts repositories create "${REPO_NAME}" \
    --project="${PROJECT_ID}" \
    --location="${REGION}" \
    --repository-format=docker \
    --description="Daena container images"

# --- Step 1: Authenticate Docker with GCP ---
echo ""
echo "[Step 1] Configuring Docker auth..."
run_cmd gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# --- Step 2: Build Docker image ---
if [ "$SKIP_BUILD" = false ]; then
    echo ""
    echo "[Step 2] Building Docker image..."
    run_cmd docker build \
        --build-arg DAENA_VERSION="${DAENA_VERSION}" \
        --build-arg BUILD_DATE="${BUILD_DATE}" \
        --build-arg GIT_SHA="${GIT_SHA}" \
        -t "${FULL_IMAGE}" \
        -t "${LATEST_IMAGE}" \
        .

    # --- Step 3: Push to Artifact Registry ---
    echo ""
    echo "[Step 3] Pushing to Artifact Registry..."
    run_cmd docker push "${FULL_IMAGE}"
    run_cmd docker push "${LATEST_IMAGE}"
else
    echo ""
    echo "[Step 2-3] Skipped (--skip-build flag)"
fi

# --- Step 4: Load env vars from .env.production ---
echo ""
echo "[Step 4] Loading environment variables..."
# NOTE: DEMO_MODE is intentionally NOT defaulted to true here. A production
# deploy must run in real mode. If a demo deployment is wanted, set
# DEMO_MODE=true explicitly in .env.production (it will be appended below).
ENV_VARS="DAENA_VERSION=${DAENA_VERSION},BUILD_DATE=${BUILD_DATE},GIT_SHA=${GIT_SHA}"
if [ -f .env.production ]; then
    while IFS='=' read -r key value; do
        # Skip comments, empty lines, and lines without =
        [[ -z "$key" || "$key" =~ ^# ]] && continue
        # Trim whitespace
        key=$(echo "$key" | xargs)
        value=$(echo "$value" | xargs | sed 's/^["'"'"']//;s/["'"'"']$//')
        # Skip managed vars and empty values
        [[ "$key" == "POSTGRES_PASSWORD" || "$key" == "DAENA_VERSION" || -z "$value" ]] && continue
        ENV_VARS="${ENV_VARS},${key}=${value}"
    done < .env.production
    echo "  Loaded env vars from .env.production"
else
    echo "  WARNING: .env.production not found. Using build-time defaults only."
fi

# --- Step 5: Deploy to Cloud Run ---
echo ""
echo "[Step 5] Deploying to Cloud Run..."
run_cmd gcloud run deploy "${SERVICE_NAME}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --image="${FULL_IMAGE}" \
    --platform=managed \
    --port=8000 \
    --memory=1Gi \
    --cpu=1 \
    --min-instances=0 \
    --max-instances=5 \
    --timeout=300 \
    --concurrency=80 \
    --set-env-vars="${ENV_VARS}" \
    --allow-unauthenticated

# --- Step 6: Verify deployment ---
echo ""
echo "[Step 6] Verifying deployment..."
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
    --project="${PROJECT_ID}" \
    --region="${REGION}" \
    --format='value(status.url)' 2>/dev/null || echo "UNKNOWN")

echo ""
echo "============================================"
echo "[Daena Deploy] Deployment complete!"
echo "============================================"
echo "  Service URL: ${SERVICE_URL}"
echo "  Version:     ${DAENA_VERSION}"
echo "  Image:       ${FULL_IMAGE}"
echo "  Git SHA:     ${GIT_SHA}"
echo "  Build Date:  ${BUILD_DATE}"
echo "============================================"
echo ""
echo "Verification commands:"
echo "  curl ${SERVICE_URL}/health"
echo "  curl ${SERVICE_URL}/api/v1/health/ready"
echo "  curl ${SERVICE_URL}/api/v1/health/version"
echo "  curl ${SERVICE_URL}/api/v1/health/detailed"
echo ""
echo "Next steps (manual, one-time):"
echo "  1. Map custom domain:"
echo "     gcloud run domain-mappings create \\"
echo "       --service=${SERVICE_NAME} --domain=${DOMAIN} --region=${REGION}"
echo "  2. Update DNS: CNAME ${DOMAIN} -> ghs.googlehosted.com"
echo "  3. Add LLM API key:"
echo "     gcloud run services update ${SERVICE_NAME} \\"
echo "       --region=${REGION} --update-env-vars=ANTHROPIC_API_KEY=sk-..."
