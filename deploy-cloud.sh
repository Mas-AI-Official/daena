#!/bin/bash
set -e

echo "=== Daena Cloud Deploy ==="
echo "1. Updating Cloud Run env vars with Groq + Gemini keys..."

gcloud run services update daena \
  --project=daena-467315 \
  --region=us-central1 \
  --update-env-vars="\
GROQ_API_KEY=\${GROQ_API_KEY},\
GEMINI_API_KEY=\${GEMINI_API_KEY},\
OLLAMA_BASE_URL=,\
APP_ENV=production"

echo ""
echo "2. Verifying deployment..."
SERVICE_URL=$(gcloud run services describe daena --project=daena-467315 --region=us-central1 --format="get(status.url)")
echo "Service URL: $SERVICE_URL"

echo ""
echo "3. Testing health..."
# Cloud Run requires identity token
TOKEN=$(gcloud auth print-identity-token)
curl -s -H "Authorization: Bearer $TOKEN" "$SERVICE_URL/api/v1/health" | python -m json.tool

echo ""
echo "=== Deploy complete! ==="
echo "Groq (8 models inc. Kimi K2) + Gemini (2 models) now live in cloud."
