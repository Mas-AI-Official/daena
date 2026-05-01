# Cloud Build NOT_FOUND Diagnosis

**Date:** 2026-05-01
**Symptom:** `gcloud builds submit --config=cloudbuild.yaml --project=daena-467315 .`
returns:
```
ERROR: (gcloud.builds.submit) NOT_FOUND: Requested entity was not
found. This command is authenticated as masoud.masoori@mas-ai.co
which is the active account specified by the [core/account] property.
```

**Source upload succeeds** (~280 MiB tarball lands in
`gs://daena-467315_cloudbuild/source/...`). The error fires on the
next step — the Cloud Build API call to *create* the build.

---

## Root cause

Cloud Build is configured to **execute as a service account that
does not exist** in the project.

```
$ gcloud builds get-default-service-account --project=daena-467315 --region=global
596551989073-compute@developer.gserviceaccount.com

$ gcloud iam service-accounts list --project=daena-467315 --format='value(email)'
daena-run@daena-467315.iam.gserviceaccount.com
```

The default Cloud Build SA points to the legacy **Compute Engine
default service account** (`<project-number>-compute@developer.gserviceaccount.com`),
which is auto-provisioned only when Compute Engine is activated.
That SA was never created in this project (or was deleted) — only
`daena-run` exists.

The IAM policy *does* contain bindings to two Cloud Build identities,
but those identities are also missing as SA resources:

```
$ gcloud projects get-iam-policy daena-467315 --format=json | jq ...
roles/cloudbuild.builds.builder -> serviceAccount:596551989073@cloudbuild.gserviceaccount.com
roles/artifactregistry.writer   -> serviceAccount:596551989073@cloudbuild.gserviceaccount.com
roles/cloudbuild.serviceAgent   -> serviceAccount:service-596551989073@gcp-sa-cloudbuild.iam.gserviceaccount.com
```

These bindings reference identities that are not in the project's
SA list — they are stale / non-resolvable, which is why Cloud Build
fails to start a build using them.

## What it is NOT

Verified during diagnosis:

| Hypothesis                                       | Result |
|--------------------------------------------------|--------|
| Cloud Build API not enabled                      | ✗ enabled (`cloudbuild.googleapis.com` in `services list --enabled`) |
| Cloud Run API not enabled                        | ✗ enabled |
| Secret Manager API not enabled                   | ✗ enabled |
| Cloud SQL Admin API not enabled                  | ✗ enabled |
| Artifact Registry API not enabled                | ✗ enabled |
| IAM API not enabled                              | ✗ enabled |
| Compute API not enabled                          | ✗ enabled |
| Storage API not enabled                          | ✗ enabled |
| Default Cloud Build source bucket missing        | ✗ present (`daena-467315_cloudbuild`, `daena-467315_us-central1_cloudbuild`) |
| Artifact Registry repo `daena-repo` missing      | ✗ present (us-central1, DOCKER format) |
| Artifact Registry repo `cloud-run-source-deploy` | ✗ present |
| Project not active                               | ✗ ACTIVE |
| Wrong gcloud account                             | ✗ active = `masoud.masoori@mas-ai.co` (founder) |
| Wrong project ID                                 | ✗ `daena-467315` matches |
| Bad cloudbuild.yaml path                         | ✗ valid YAML, references existing repo |
| `.gcloudignore` excludes too much                | ✗ source upload succeeded (1084 files, 279.8 MiB) |

The build never made it past the SA-check stage. The cloudbuild.yaml
content was never evaluated.

## The fix

Create a **dedicated Cloud Build service account** (`daena-build`)
with narrow per-purpose roles and pin it as the build SA via
`cloudbuild.yaml`. Pin the runtime SA (`daena-run`) on the deploy
step so build vs runtime separation is explicit.

### Step 1 — Create the build SA

```bash
gcloud iam service-accounts create daena-build \
  --project=daena-467315 \
  --display-name='Daena Cloud Build' \
  --description='Dedicated SA for Cloud Build steps (build + push + deploy). NOT a runtime SA.'
```

### Step 2 — Grant 6 narrow project-level roles

Per founder rule "minimum required roles, no broad grants":

```bash
SA="daena-build@daena-467315.iam.gserviceaccount.com"
PROJECT="daena-467315"
for ROLE in \
  roles/run.admin \
  roles/artifactregistry.writer \
  roles/secretmanager.viewer \
  roles/logging.logWriter \
  roles/cloudsql.client \
  roles/storage.objectViewer
do
  gcloud projects add-iam-policy-binding $PROJECT \
    --member=serviceAccount:$SA \
    --role=$ROLE \
    --condition=None
done
```

Why these roles, and **not** the catch-all `roles/cloudbuild.builds.builder`:

| Role                                | Why                                              | Why not just `cloudbuild.builds.builder`           |
|-------------------------------------|--------------------------------------------------|------------------------------------------------------|
| `roles/run.admin`                   | deploy / update Cloud Run service                | builder includes this but also much more             |
| `roles/artifactregistry.writer`     | push image to Artifact Registry                  | builder includes this; writer is exactly what's needed |
| `roles/secretmanager.viewer`        | verify secrets exist when binding via `--update-secrets` | builder includes `secretmanager.versions.access` (READ values) which build SA does NOT need |
| `roles/logging.logWriter`           | write build logs (required with custom SA)       | builder includes |
| `roles/cloudsql.client`             | validate `--add-cloudsql-instances` in deploy step | builder includes |
| `roles/storage.objectViewer`        | read source tarball from `daena-467315_cloudbuild` | builder includes `storage.objectAdmin` which is broader |

The narrow set blocks daena-build from reading any secret value,
admin-writing storage, or modifying IAM — strictly safer than the
catch-all role.

### Step 3 — Grant `iam.serviceAccountUser` on `daena-run`

So daena-build can deploy with daena-run as the runtime SA:

```bash
gcloud iam service-accounts add-iam-policy-binding \
  daena-run@daena-467315.iam.gserviceaccount.com \
  --member=serviceAccount:daena-build@daena-467315.iam.gserviceaccount.com \
  --role=roles/iam.serviceAccountUser \
  --project=daena-467315 \
  --condition=None
```

This is per-SA (not project-wide) per Google's actAs guidance.

### Step 4 — Pin SAs in `cloudbuild.yaml`

```yaml
# Top-level: build SA used for all build steps.
serviceAccount: 'projects/$PROJECT_ID/serviceAccounts/daena-build@$PROJECT_ID.iam.gserviceaccount.com'

# When using a custom build SA, Cloud Build requires explicit log
# destination. CLOUD_LOGGING_ONLY (already in our config) is fine.
options:
  logging: CLOUD_LOGGING_ONLY

# In the gcloud run deploy step, explicit runtime SA:
- '--service-account=daena-run@$PROJECT_ID.iam.gserviceaccount.com'
```

All four steps are landed in commit f7f79dd's follow-up patch.

## Verification

After the fix, re-run:

```bash
gcloud builds submit --config=cloudbuild.yaml --project=daena-467315 .
```

Expected: source upload succeeds (already did), then the build
PROCEEDS rather than NOT_FOUNDing on SA lookup. Build steps run as
`daena-build`; deploy step deploys with `daena-run` as runtime SA.

If the build then fails for a different reason (e.g. Dockerfile
error, alembic migration error inside container), that is a
*different* problem — `CLOUD_BUILD_NOT_FOUND_DIAGNOSIS.md` is solved
once the NOT_FOUND error is gone.

## Side observations (not blockers)

1. `daena-run` currently has `roles/cloudbuild.builds.builder`,
   `roles/artifactregistry.writer`, and `roles/storage.admin` —
   over-broad for a runtime SA. After this Cloud Build fix lands and
   we confirm `daena-build` works in production deploys, those
   bindings on `daena-run` can be removed in a separate cleanup PR.
2. The IAM bindings referencing `596551989073@cloudbuild.gserviceaccount.com`
   and `service-596551989073@gcp-sa-cloudbuild.iam.gserviceaccount.com`
   are stale — neither identity is a resolvable SA in this project.
   They can be removed in the same cleanup PR; harmless to leave
   for now (Cloud Build no longer references them).
3. `cloudresourcemanager.googleapis.com` is **not** in the enabled
   APIs list. `gcloud config list` prompted to enable it. Not a
   build-time blocker (build still uploads source) but should be
   enabled for future `gcloud projects` commands to work without
   prompting.

---

**Generated:** 2026-05-01
**Author:** Claude Code (Opus 4.7)
**Counterpart docs:** `PRODUCTION_HYGIENE_AUTOMATION_REPORT.md`,
`PRODUCTION_DB_AND_SECRET_ROTATION_PLAN.md`,
`LOCAL_FIRST_DAENA_ARCHITECTURE.md`
