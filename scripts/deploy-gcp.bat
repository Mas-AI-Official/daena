@echo off
REM ============================================================
REM Daena GCP Cloud Run Deployment Script
REM ============================================================
REM Prerequisites:
REM   1. gcloud auth login (authenticate)
REM   2. Docker Desktop running
REM   3. .env.production exists at repo root
REM ============================================================

set PROJECT_ID=daena-467315
set REGION=us-central1
set REPO=daena-repo
set IMAGE=us-central1-docker.pkg.dev/%PROJECT_ID%/%REPO%/daena:latest

echo.
echo === Step 1: Verify authentication ===
gcloud auth list
gcloud config set project %PROJECT_ID%

echo.
echo === Step 2: Enable required APIs ===
gcloud services enable run.googleapis.com
gcloud services enable artifactregistry.googleapis.com
gcloud services enable secretmanager.googleapis.com
gcloud services enable cloudbuild.googleapis.com

echo.
echo === Step 3: Create Artifact Registry (ignore if exists) ===
gcloud artifacts repositories create %REPO% ^
  --repository-format=docker ^
  --location=%REGION% ^
  --description="Daena container images" 2>nul

echo.
echo === Step 4: Configure Docker auth ===
gcloud auth configure-docker %REGION%-docker.pkg.dev --quiet

echo.
echo === Step 5: Build and push image ===
docker build -t %IMAGE% .
docker push %IMAGE%

echo.
echo === Step 6: Deploy to Cloud Run ===
gcloud run deploy daena ^
  --image %IMAGE% ^
  --platform managed ^
  --region %REGION% ^
  --port 8000 ^
  --memory 1Gi ^
  --cpu 1 ^
  --min-instances 0 ^
  --max-instances 2 ^
  --timeout 300 ^
  --allow-unauthenticated ^
  --set-env-vars "ENVIRONMENT=production,DEBUG=false,DATABASE_URL=sqlite+aiosqlite:///./daena_prod.db,CORS_ORIGINS=[\"https://daena.mas-ai.co\"],OLLAMA_BASE_URL=http://localhost:11434,JWT_SECRET_KEY=CHANGE_ME_BEFORE_DEPLOY,VAULT_ENCRYPTION_KEY=CHANGE_ME_BEFORE_DEPLOY"

echo.
echo === Step 7: Get deployed URL ===
gcloud run services describe daena --region %REGION% --format="value(status.url)"

echo.
echo === Step 8: Test health ===
for /f %%u in ('gcloud run services describe daena --region %REGION% --format="value(status.url)"') do (
  curl -s %%u/health
  echo.
  curl -s %%u/api/v1/health/detailed
)

echo.
echo === DONE ===
echo Remember to:
echo   1. Set real JWT_SECRET_KEY and VAULT_ENCRYPTION_KEY
echo   2. Set up custom domain: gcloud run domain-mappings create --service daena --domain daena.mas-ai.co --region %REGION%
echo   3. Add DNS records per instructions
pause
