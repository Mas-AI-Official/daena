# One-time setup: dedicated hands-off deploy service account for Daena prod.
#
# WHY: gcloud USER auth hits a 2SV reauthentication wall every few hours, which
# blocks non-interactive `gcloud builds submit`. A SERVICE ACCOUNT is not subject
# to 2SV, so once this runs the production deploy can be fully hands-off.
#
# RUN THIS ONCE, INTERACTIVELY, in a shell logged in with an account that has
# Owner / IAM-admin on daena-467315:
#     gcloud auth login masoud.masoori@mas-ai.co
#     powershell -ExecutionPolicy Bypass -File .\deploy\setup-deploy-sa.ps1
#
# SECURITY (governance NEVER #1: no secret/key IN SOURCE):
#   - The key is written OUTSIDE the repo to $KeyPath below.
#   - Never commit it; never move it into the repo tree.
#   - Rotate: gcloud iam service-accounts keys create/delete.
#   - Roles are the minimum needed to submit a Cloud Build that builds+deploys.

$ErrorActionPreference = "Stop"
$Project = "daena-467315"
$SaName  = "daena-deploy"
$SaEmail = "$SaName@$Project.iam.gserviceaccount.com"
$BuildSa = "daena-build@$Project.iam.gserviceaccount.com"
$KeyDir  = Join-Path $env:USERPROFILE ".config\daena"
$KeyPath = Join-Path $KeyDir "deploy-sa-key.json"

Write-Host "[1/5] Creating service account $SaEmail (idempotent)..."
gcloud iam service-accounts describe $SaEmail --project=$Project 2>$null
if ($LASTEXITCODE -ne 0) {
  gcloud iam service-accounts create $SaName --project=$Project `
    --display-name="Daena hands-off deploy (Cloud Build submitter)"
}

Write-Host "[2/5] Granting minimal project roles..."
# Submit and drive Cloud Build:
gcloud projects add-iam-policy-binding $Project `
  --member="serviceAccount:$SaEmail" --role="roles/cloudbuild.builds.editor" --condition=None | Out-Null
# Source upload for `builds submit` (can be tightened to objectAdmin on the
# gs://daena-467315_cloudbuild bucket once it exists):
gcloud projects add-iam-policy-binding $Project `
  --member="serviceAccount:$SaEmail" --role="roles/storage.admin" --condition=None | Out-Null
# Read build logs:
gcloud projects add-iam-policy-binding $Project `
  --member="serviceAccount:$SaEmail" --role="roles/logging.viewer" --condition=None | Out-Null

Write-Host "[3/5] Allowing the deploy SA to act AS the build SA ($BuildSa)..."
gcloud iam service-accounts add-iam-policy-binding $BuildSa --project=$Project `
  --member="serviceAccount:$SaEmail" --role="roles/iam.serviceAccountUser" --condition=None | Out-Null

Write-Host "[4/5] Writing key OUTSIDE the repo to $KeyPath ..."
New-Item -ItemType Directory -Force -Path $KeyDir | Out-Null
if (Test-Path $KeyPath) {
  Write-Host "   Key already exists; skipping creation (rotate manually if needed)."
} else {
  gcloud iam service-accounts keys create $KeyPath --iam-account=$SaEmail --project=$Project
}

Write-Host ""
Write-Host "[5/5] Done. Activate the hands-off identity in any shell with:"
Write-Host "   gcloud auth activate-service-account --key-file=`"$KeyPath`""
Write-Host "Then `gcloud builds submit` needs NO 2FA. Rollback: deploy/ROLLBACK.md"
