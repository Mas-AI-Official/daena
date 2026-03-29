# Daena V2 -- Paste-Ready GCloud Commands

All commands use project `daena-467315`, region `northamerica-northeast1`.

---

## D4: One-Time GCP Setup (5 min)

### 4a. Authenticate and set project

```bash
gcloud auth login
gcloud config set project daena-467315
gcloud config set run/region northamerica-northeast1
```

### 4b. Enable required APIs

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  sqladmin.googleapis.com \
  compute.googleapis.com
```

### 4c. Create Artifact Registry repo (if not exists)

```bash
gcloud artifacts repositories create daena \
  --location=northamerica-northeast1 \
  --repository-format=docker \
  --description="Daena container images"
```

### 4d. Configure Docker auth

```bash
gcloud auth configure-docker northamerica-northeast1-docker.pkg.dev --quiet
```

---

## D5: Deploy (automated script)

### Option A: Full deploy (build + push + deploy)

```bash
cd D:\Ideas\Daena
bash scripts/deploy-gcp.sh
```

### Option B: Skip build (redeploy existing image)

```bash
bash scripts/deploy-gcp.sh --skip-build
```

### Option C: Dry run (see commands without executing)

```bash
bash scripts/deploy-gcp.sh --dry-run
```

---

## D6: Post-Deploy Manual Steps

### 6a. Map custom domain (one-time, 2 min)

```bash
gcloud beta run domain-mappings create \
  --service=daena \
  --domain=daena.mas-ai.co \
  --region=northamerica-northeast1
```

Then in your DNS provider (Cloudflare/Google Domains):
- Add CNAME record: `daena.mas-ai.co` -> `ghs.googlehosted.com`
- Or if using apex domain: A records from the output of the command above

### 6b. Add LLM API key (2 min, enables live chat)

```bash
# Add one or more provider keys:
gcloud run services update daena \
  --region=northamerica-northeast1 \
  --update-env-vars="ANTHROPIC_API_KEY=sk-ant-your-key-here"
```

```bash
# Or multiple at once:
gcloud run services update daena \
  --region=northamerica-northeast1 \
  --update-env-vars="ANTHROPIC_API_KEY=sk-ant-xxx,OPENAI_API_KEY=sk-xxx,GROQ_API_KEY=gsk_xxx"
```

### 6c. Verify deployment health

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe daena \
  --region=northamerica-northeast1 \
  --format='value(status.url)')

# Run health checks
curl -s "$SERVICE_URL/health" | python -m json.tool
curl -s "$SERVICE_URL/api/v1/health/ready" | python -m json.tool
curl -s "$SERVICE_URL/api/v1/health/version" | python -m json.tool
curl -s "$SERVICE_URL/api/v1/health/detailed" | python -m json.tool
```

### 6d. View logs (live monitoring)

```bash
gcloud run services logs read daena \
  --region=northamerica-northeast1 \
  --limit=50

# Or stream live:
gcloud beta run services logs tail daena \
  --region=northamerica-northeast1
```

---

## Rollback

### Roll back to previous revision

```bash
# List revisions
gcloud run revisions list --service=daena --region=northamerica-northeast1

# Route 100% traffic to a specific revision
gcloud run services update-traffic daena \
  --region=northamerica-northeast1 \
  --to-revisions=daena-REVISION_ID=100
```

---

## Optional: Secret Manager (for production secrets)

Instead of passing secrets as env vars, use GCP Secret Manager:

```bash
# Create secrets
echo -n "your-jwt-secret-64-chars" | \
  gcloud secrets create daena-jwt-secret --data-file=-

echo -n "your-vault-key-64-chars" | \
  gcloud secrets create daena-vault-key --data-file=-

# Grant Cloud Run access
PROJECT_NUM=$(gcloud projects describe daena-467315 --format='value(projectNumber)')
gcloud secrets add-iam-policy-binding daena-jwt-secret \
  --member="serviceAccount:${PROJECT_NUM}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding daena-vault-key \
  --member="serviceAccount:${PROJECT_NUM}-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Mount secrets in Cloud Run
gcloud run services update daena \
  --region=northamerica-northeast1 \
  --update-secrets="JWT_SECRET_KEY=daena-jwt-secret:latest,VAULT_ENCRYPTION_KEY=daena-vault-key:latest"
```

---

## Optional: Cloud SQL (PostgreSQL)

For persistent production database instead of SQLite:

```bash
# Create Cloud SQL instance
gcloud sql instances create daena-db \
  --database-version=POSTGRES_16 \
  --tier=db-f1-micro \
  --region=northamerica-northeast1 \
  --storage-size=10GB \
  --storage-type=SSD

# Create database and user
gcloud sql databases create daena --instance=daena-db
gcloud sql users set-password postgres \
  --instance=daena-db \
  --password=YOUR_STRONG_PASSWORD

# Connect Cloud Run to Cloud SQL
gcloud run services update daena \
  --region=northamerica-northeast1 \
  --add-cloudsql-instances=daena-467315:northamerica-northeast1:daena-db \
  --update-env-vars="DATABASE_URL=postgresql+asyncpg://postgres:YOUR_STRONG_PASSWORD@/daena?host=/cloudsql/daena-467315:northamerica-northeast1:daena-db"
```
