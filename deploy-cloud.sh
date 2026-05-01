#!/bin/bash
# Daena Cloud Run deploy: Secret Manager bindings + Cloud SQL link.
#
# This script does NOT build the image. It updates the Cloud Run
# service config to bind 7 secrets from Secret Manager and link the
# Cloud SQL Postgres instance. Schema migrations run inside each
# container at start via /app/start.sh -> `alembic upgrade head`.
#
# Pre-requisites (run once, manually, with founder approval):
#   1. python scripts/setup_production_secrets.py   # creates secrets
#   2. gcloud builds submit --config=cloudbuild.yaml .   # builds image
#                                                        # with start.sh
#                                                        # entrypoint
#
# This script is idempotent: re-running updates env/secret bindings
# and produces a new revision (Cloud Run revisions are immutable).
set -euo pipefail

PROJECT='daena-467315'
REGION='us-central1'
SERVICE='daena-v2'  # fresh service per CLEAN_GCLOUD_REBUILD_PLAN.md (the
                    # legacy `daena` service was left broken for autopsy).
CLOUDSQL_INSTANCE="${PROJECT}:${REGION}:daena-db"

echo "=== Daena Cloud Deploy ==="

echo ""
echo "Pre-flight readiness check..."
if command -v pwsh >/dev/null 2>&1; then
  pwsh scripts/production_readiness_check.ps1 || {
    echo "ERROR: Readiness check failed. Aborting deploy."
    exit 1
  }
else
  echo "WARN: pwsh not on PATH; skipping pre-flight readiness check."
fi

echo ""
echo "1. Updating Cloud Run service: bind secrets + link Cloud SQL..."
gcloud run services update "${SERVICE}" \
  --project="${PROJECT}" \
  --region="${REGION}" \
  --add-cloudsql-instances="${CLOUDSQL_INSTANCE}" \
  --update-secrets="\
DATABASE_URL=daena-database-url:latest,\
DAENA_KEK=daena-daena-kek:latest,\
JWT_SECRET_KEY=daena-jwt-secret-key:latest,\
VAULT_ENCRYPTION_KEY=daena-vault-encryption-key:latest,\
GROQ_API_KEY=daena-groq-api-key:latest,\
GEMINI_API_KEY=daena-gemini-api-key:latest,\
GOOGLE_CLIENT_SECRET=daena-google-client-secret:latest,\
GITHUB_CLIENT_SECRET=daena-github-client-secret:latest" \
  --update-env-vars="\
APP_ENV=production,\
LOG_LEVEL=info,\
USE_CONNECTION_REGISTRY_V2=false,\
DISABLE_AUTH=false"

echo ""
echo "Note: schema migration ('alembic upgrade head') runs at container"
echo "      start via /app/start.sh -- see Dockerfile ENTRYPOINT."

echo ""
echo "2. Verifying deployment..."
SERVICE_URL=$(gcloud run services describe "${SERVICE}" \
  --project="${PROJECT}" --region="${REGION}" \
  --format='get(status.url)')
echo "Service URL: ${SERVICE_URL}"

TOKEN=$(gcloud auth print-identity-token)
curl -fsS -H "Authorization: Bearer ${TOKEN}" \
  "${SERVICE_URL}/api/v1/health" | python -m json.tool

echo ""
echo "3. Post-deploy readiness re-check..."
if command -v pwsh >/dev/null 2>&1; then
  pwsh scripts/production_readiness_check.ps1
fi

echo ""
echo "=== Deploy complete ==="
