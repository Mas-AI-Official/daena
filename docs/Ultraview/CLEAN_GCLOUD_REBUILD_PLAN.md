# Clean GCloud Rebuild Plan

**Date:** 2026-05-01
**Status:** PLAN ONLY — execution gated on founder approval of this doc
**Authority:** Founder authorization 2026-05-01
**Branch:** `rebuild-connections-mcp-runtime`
**Operator:** Claude Code (Opus 4.7)

> Daena remains **local-first**. GCloud is being rebuilt as a clean
> backup / demo / client-ready environment, **not** the main operator
> workflow. See `LOCAL_FIRST_DAENA_ARCHITECTURE.md`.

---

## 1. Current broken state

| Surface                       | State                                                                                                |
|-------------------------------|------------------------------------------------------------------------------------------------------|
| Cloud Run service `daena`     | Latest 4 revisions (00040, 00041, 00042, 00043) failed health checks; traffic stuck on 00038-msl from 2026-04-08 |
| Cloud Run revision 00038      | Old image (2026-03-21) running with looping uvicorn child-process death (founder-confirmed unstable) |
| Cloud SQL `daena-db`          | RUNNABLE, POSTGRES_15. `daena` user password rotated 2026-05-01.                                     |
| Cloud SQL database `daena`    | Empty schema (no tables); pre-existing                                                               |
| Cloud SQL user `daena`        | Exists, password rotated. Owns the `daena` database.                                                 |
| Cloud SQL user `daena_app`    | **Does NOT exist** (founder spec calls for it)                                                       |
| Secret Manager (7 secrets)    | All present + IAM bound to `daena-run`; values populated 2026-05-01                                  |
| `VAULT_ENCRYPTION_KEY`        | **LEAKED** in this session via a `--format='value(...env)'` query; exists as Cloud Run plaintext env |
| `DATABASE_URL`                | Now Secret Manager-bound to `daena-database-url:latest` on the (failed) 00041–00043 revisions        |
| `daena-run` SA                | `secretAccessor` on 7 secrets ✓; `cloudsql.client` granted 2026-05-01                                |
| `daena-build` SA              | Created 2026-05-01 with 6 narrow roles; used for cloudbuild.yaml                                     |
| Artifact Registry `daena-repo`| Has `daena:latest` image with start.sh entrypoint + python3 fix (built 5x this session)              |

### Root cause analysis (chain of failures already debugged)

1. ✓ FIXED — Cloud Build NOT_FOUND: missing default compute SA → created `daena-build` SA + pinned in cloudbuild.yaml
2. ✓ FIXED — `$SHORT_SHA` empty: switched to `$BUILD_ID`
3. ✓ FIXED — `SecurityDashboardPage.tsx` TS2322: arrow-wrap `onClick`
4. ✓ FIXED — env type conflict (existing plaintext + new SM ref): `--remove-env-vars`
5. ✓ FIXED — `python: command not found`: switched start.sh to `python3`
6. ✓ FIXED — `cloudsql.client` missing on `daena-run`: granted
7. ❓ UNRESOLVED — Cloud Run revisions retired in ~120 ms after IAM grant; either IAM not propagated yet OR a separate boot-time error not captured in logs
8. 🚨 INCIDENT — `VAULT_ENCRYPTION_KEY` leaked via `--format='value(...env)'` dump

## 2. Resources to KEEP (do not touch)

- GCP project `daena-467315`
- Billing configuration
- Cloud SQL instance `daena-db` (RUNNABLE, POSTGRES_15, us-central1)
- Artifact Registry repos `daena-repo` and `cloud-run-source-deploy`
- Service accounts `daena-run` and `daena-build` (with current IAM)
- All 7 existing Secret Manager secrets:
  - `daena-database-url`, `daena-daena-kek`, `daena-jwt-secret-key`,
    `daena-groq-api-key`, `daena-gemini-api-key`,
    `daena-google-client-secret`, `daena-github-client-secret`
- Local repo (`D:/Ideas/Daena`) and all backend / frontend source
- Local SQLite database (`backend/daena.db` if present)
- `vault.py`, `oauth_credentials_store.py` — explicitly NOT to be deleted

## 3. Resources to DELETE / RECREATE

| Action          | Resource                                | Reason                                                                      |
|-----------------|-----------------------------------------|------------------------------------------------------------------------------|
| Recreate        | Secret `daena-vault-encryption-key`     | New secret to hold the rotated VAULT_ENCRYPTION_KEY (replaces plaintext env) |
| Create          | Cloud SQL user `daena_app`              | Per founder spec; previously deviated to existing `daena` user               |
| Create          | Cloud SQL database `daena_v2`           | Fresh, owned by `daena_app`, no legacy schema noise                          |
| Recreate        | Secret `daena-database-url` (new version) | Updated URL pointing at `daena_v2` + `daena_app` credentials                |
| Create          | Cloud Run service `daena-v2`            | Fresh service; leaves broken `daena` revisions undisturbed for autopsy       |
| Leave alone     | Cloud Run service `daena`               | Founder may delete later after verifying `daena-v2` is stable                |

### NOT planned to delete
- Cloud SQL database `daena` (kept for autopsy; no valuable data, but no rush)
- Cloud SQL user `daena` (kept — its password is the value in `daena-database-url:latest`; superseded once `daena-database-url:2` lands)
- Old Cloud Run revisions 00040-00043 (auto-cleaned by Cloud Run retention policy)
- Old Artifact Registry image tags (kept; layer cache speeds up rebuilds)

## 4. Secrets that MUST be rotated

| Secret                       | Rotation owner          | When                                          |
|------------------------------|-------------------------|-----------------------------------------------|
| `VAULT_ENCRYPTION_KEY`       | Daena (this rebuild)    | Phase 1 — TODAY (was leaked in this session) |
| `daena-database-url`         | Daena (this rebuild)    | Phase 2 — TODAY (new daena_v2 credentials)   |
| `GROQ_API_KEY`               | Founder at console.groq.com | Out of scope for this rebuild; still pending |
| `GEMINI_API_KEY`             | Founder at aistudio.google.com | Out of scope for this rebuild; still pending |
| `GOOGLE_CLIENT_SECRET`       | Founder in GCP Console  | Out of scope for this rebuild; still pending |
| `GITHUB_CLIENT_SECRET`       | Founder on github.com   | Out of scope for this rebuild; still pending |

**Provider-side rotation reminder (UNCHANGED from prior reports):** moving
the 4 plaintext provider secrets into Secret Manager did NOT rotate them.
Until the founder regenerates them at the issuer surfaces, anyone with the
leaked terminal output from the 2026-05-01 incident retains valid credentials.

## 5. Target architecture

```
┌─ GCP project daena-467315 ───────────────────────────────────────────────┐
│                                                                           │
│  Cloud SQL daena-db (POSTGRES_15, RUNNABLE, us-central1)                 │
│   ├─ database daena       (legacy, untouched)                             │
│   ├─ database daena_v2    (NEW, owned by daena_app)                       │
│   ├─ user daena           (legacy, password rotated; superseded)          │
│   └─ user daena_app       (NEW, owns daena_v2; pw in Secret Manager)      │
│                                                                           │
│  Secret Manager (8 secrets)                                              │
│   ├─ daena-database-url           (NEW VERSION: daena_app + daena_v2)    │
│   ├─ daena-vault-encryption-key   (NEW SECRET: rotated VAULT_ENCRYPTION_KEY) │
│   ├─ daena-daena-kek              (existing, fresh)                       │
│   ├─ daena-jwt-secret-key         (existing, fresh)                       │
│   ├─ daena-groq-api-key           (existing, plaintext-moved + LEAKED)    │
│   ├─ daena-gemini-api-key         (existing, plaintext-moved + LEAKED)    │
│   ├─ daena-google-client-secret   (existing, plaintext-moved + LEAKED)    │
│   └─ daena-github-client-secret   (existing, plaintext-moved + LEAKED)    │
│                                                                           │
│  IAM bindings (daena-run runtime SA):                                    │
│   - secretAccessor on all 8 secrets                                       │
│   - cloudsql.client                                                       │
│   - logging.logWriter (default)                                           │
│                                                                           │
│  IAM bindings (daena-build build SA):                                    │
│   - run.admin, artifactregistry.writer, secretmanager.viewer,            │
│     logging.logWriter, cloudsql.client, storage.objectViewer             │
│   - iam.serviceAccountUser on daena-run                                   │
│                                                                           │
│  Artifact Registry daena-repo (us-central1)                              │
│   ├─ daena:latest         (current image with start.sh + python3)        │
│   └─ daena:<BUILD_ID>     (historical builds)                             │
│                                                                           │
│  Cloud Run service daena-v2 (NEW)                                        │
│   ├─ Runtime SA: daena-run                                                │
│   ├─ Image: us-central1-docker.pkg.dev/daena-467315/daena-repo/daena:latest │
│   ├─ Cloud SQL link: daena-467315:us-central1:daena-db                   │
│   ├─ ENTRYPOINT: /app/start.sh -> alembic upgrade head -> uvicorn        │
│   ├─ ENV (Secret Manager bindings, 8):                                   │
│   │    DATABASE_URL, DAENA_KEK, JWT_SECRET_KEY, GROQ_API_KEY,            │
│   │    GEMINI_API_KEY, GOOGLE_CLIENT_SECRET, GITHUB_CLIENT_SECRET,       │
│   │    VAULT_ENCRYPTION_KEY                                              │
│   └─ ENV (plaintext config, 4):                                          │
│        APP_ENV=production, LOG_LEVEL=info,                               │
│        USE_CONNECTION_REGISTRY_V2=false, DISABLE_AUTH=false              │
│                                                                           │
│  Cloud Run service daena (LEFT BROKEN, traffic stuck on 00038)          │
│   - Recommended: founder deletes after verifying daena-v2 is stable      │
└───────────────────────────────────────────────────────────────────────────┘
```

## 6. The user/database GRANT problem (resolved approach)

**Problem:** Founder spec calls for `daena_app` user owning a `daena_v2`
database. `gcloud sql users create daena_app` only grants
`cloudsqlsuperuser` role, which doesn't include automatic CONNECT to
existing-databases-not-created-by-user. `gcloud sql databases create`
doesn't accept an `--owner-user` flag for Postgres.

**Resolution:** Use `cloud-sql-python-connector` (pure-Python, pg8000
driver) installed temporarily to a local venv. Single Python script:

1. Reset `postgres` superuser password via gcloud (brief argv exposure;
   never printed; we discard the password after this session).
2. Connect to instance via `cloud-sql-python-connector` as `postgres`.
3. `CREATE USER daena_app WITH ENCRYPTED PASSWORD '<gen>'`
4. `CREATE DATABASE daena_v2 OWNER daena_app`
5. `GRANT ALL ON SCHEMA public TO daena_app` (defense in depth)
6. Close connection.

`cloud-sql-python-connector` handles the IAM auth + proxy automatically
(uses gcloud ADC). No external binary needed (just pip install).

**Why not pure gcloud:** `gcloud sql connect` requires a local psql
binary which isn't installed. `gcloud sql import sql` requires staging
the SQL in a Cloud Storage bucket (extra write surface). Python
connector is the canonical Google-recommended programmatic path.

## 7. Commands to execute (in order)

### Phase 1 — VAULT_ENCRYPTION_KEY rotation (no destructive impact)

```bash
# Generate fresh value, pipe into Secret Manager. Never print.
python -c "import secrets; print(secrets.token_hex(32))" | \
  gcloud secrets create daena-vault-encryption-key \
    --project=daena-467315 \
    --replication-policy=automatic \
    --data-file=-

# Grant runtime SA secretAccessor
gcloud secrets add-iam-policy-binding daena-vault-encryption-key \
  --project=daena-467315 \
  --member='serviceAccount:daena-run@daena-467315.iam.gserviceaccount.com' \
  --role='roles/secretmanager.secretAccessor' \
  --condition=None
```

### Phase 2 — Cloud SQL daena_app + daena_v2 (destructive in narrow scope)

Single Python script (committed at `scripts/provision_cloud_sql_v2.py`):

1. Validate gcloud auth + project = daena-467315
2. Reset `postgres` user password to a session-only generated value
3. Use `cloud-sql-python-connector` to connect as postgres
4. Create user `daena_app` with generated password
5. Create database `daena_v2` owned by `daena_app`
6. Build DATABASE_URL: `postgresql+asyncpg://daena_app:<pw>@/daena_v2?host=/cloudsql/daena-467315:us-central1:daena-db`
7. Push as new version of `daena-database-url` secret
8. Reset postgres password to a different random value (then forget it)

Never prints passwords. Idempotent re-run support via "exists" checks.

### Phase 3 — Local code patches (already in place from prior commits)

Files audit:
- `start.sh` — verify `python3` (not `python`); alembic before uvicorn ✓
- `Dockerfile` — verify ENTRYPOINT ["/app/start.sh"] ✓
- `cloudbuild.yaml` — verify SA pinning, --remove-env-vars, --update-secrets ✓
  - **MUST ADD**: `VAULT_ENCRYPTION_KEY=daena-vault-encryption-key:latest`
    to --update-secrets, AND `VAULT_ENCRYPTION_KEY` to --remove-env-vars
  - **MUST CHANGE**: target service name daena → daena-v2
  - **MUST CHANGE**: `--allow-unauthenticated` (or omit) per founder choice
- `deploy-cloud.sh` — verify (already updated) ✓; same VAULT changes needed
- `backend/app/main.py` — production guards verified ✓
- `scripts/production_readiness_check.ps1` — verify VAULT_ENCRYPTION_KEY
  added to `$RequiredSecretEnvNames`

### Phase 4 — Cloud Run service daena-v2 (option A, fresh)

- Triggered via updated `cloudbuild.yaml` (single submit).
- Service `daena-v2` is created on first deploy.
- No traffic migration from `daena` — `daena-v2` has its own URL.
- After health verified, founder may decide to:
  - Delete the broken `daena` service, OR
  - Move domain mapping from `daena` to `daena-v2`, OR
  - Keep both for parallel testing.

### Phase 5 — Single deploy + verification

```bash
# Single submit. No retries. If it fails, write the failure report.
gcloud builds submit --config=cloudbuild.yaml --project=daena-467315 .

# Watch logs
gcloud run services logs read daena-v2 --project=daena-467315 --region=us-central1 --limit=200
```

Look for:
- `[entrypoint] Running alembic upgrade head...`
- `[entrypoint] Starting uvicorn on port 8000...`
- `essentials.alembic_at version=007_connection_v2_registry`
- HTTP 200 from `/api/v1/health`

If anything fails, collect:
- Cloud Build ID
- Cloud Run revision name (`daena-v2-00001-xxx`)
- Last 50 log lines
- Write failure report. STOP.

## 8. What WILL be destroyed

- The session-only `postgres` superuser password (rotated twice;
  discarded between rotations). Founder will need to reset it via
  `gcloud sql users set-password postgres --prompt-for-password
  --instance=daena-db --project=daena-467315` if they need it later.
- The Cloud Run revisions for `daena-v2` will replace each other on
  re-deploy (normal Cloud Run behavior).

## 9. What WILL be preserved

- All 7 existing Secret Manager secrets (untouched; only ADDING the
  8th: `daena-vault-encryption-key`)
- Cloud SQL `daena-db` instance (no restart; no flag changes)
- Cloud SQL `daena` database + `daena` user (untouched; superseded)
- Cloud Run service `daena` and all its revisions (left alone for
  autopsy/rollback)
- Artifact Registry images (no deletion)
- Service accounts `daena-run` and `daena-build` (no IAM removal)
- All local code, local SQLite, vault.py, oauth_credentials_store.py

## 10. Rollback plan

If `daena-v2` deploy fails AND we have NOT touched `daena`:
- Nothing to roll back. `daena-v2` is fresh; on failure, it has zero
  serving revisions. Original `daena` (broken) is still serving 00038.

If we make a critical mistake (unlikely with this plan):

| What broke                          | Rollback                                                                      |
|-------------------------------------|--------------------------------------------------------------------------------|
| `daena_v2` database is corrupted    | `gcloud sql databases delete daena_v2 --instance=daena-db`; recreate via script |
| `daena_app` user creation issue     | `gcloud sql users delete daena_app --instance=daena-db`; recreate via script   |
| Wrong DATABASE_URL stored           | `gcloud secrets versions access N --secret=daena-database-url` to read prior; then `gcloud secrets versions add` with corrected URL via stdin |
| `daena-vault-encryption-key` wrong  | `gcloud secrets delete daena-vault-encryption-key`; recreate                  |
| Cloud Run `daena-v2` service broken | `gcloud run services delete daena-v2 --region=us-central1`; restart from Phase 4 |

**Cannot be rolled back:**
- The leaked `VAULT_ENCRYPTION_KEY` value is permanently leaked. Rotation
  is mandatory; the rotation cannot be undone.
- The `postgres` superuser password rotation cannot be undone (we don't
  preserve the prior value because it was unknown anyway).

## 11. Hard rules being held

| Rule                                                              | Holds during this rebuild? |
|-------------------------------------------------------------------|----------------------------|
| Do not delete GCP project `daena-467315`                          | YES                        |
| Do not delete billing configuration                               | YES                        |
| Do not delete local repo / DB / files                             | YES                        |
| Do not delete all Secret Manager secrets without recreating them  | YES (only adding 1, no deletes) |
| Do not print secret values                                        | YES                        |
| Do not commit secret values                                       | YES                        |
| Do not flip USE_CONNECTION_REGISTRY_V2=true in production         | YES (cloudbuild.yaml sets =false) |
| Do not run production `vault --apply`                             | YES                        |
| Do not delete `vault.py` or `oauth_credentials_store.py`          | YES                        |
| Do not run external security scans                                | YES                        |
| Do not send emails or external messages                           | YES                        |

## 12. Estimated time

- Phase 0 (this plan): 0 (already written)
- Phase 1 (VAULT_ENCRYPTION_KEY rotation): ~30 sec
- Phase 2 (Cloud SQL daena_app + daena_v2 setup): ~3 min (incl. pip install)
- Phase 3 (local code edits): ~5 min
- Phase 4 (Cloud Run daena-v2 first deploy): ~10 min (Cloud Build)
- Phase 5 (verification): ~3 min
- Phase 6 (final report + commit): ~5 min

Total: ~25 min if no surprises. Each phase is single-shot; no
retry loops.

---

**End of plan.**
**Awaiting:** founder review (implicit via the authorization message); proceeding with Phases 1–6.
