# Production DB & Secret Rotation Plan

**Status:** EMERGENCY — production secrets exposed; production DB confirmed non-durable.
**Date:** 2026-05-01
**Branch:** `rebuild-connections-mcp-runtime`
**Audience:** Founder + Operator
**Author:** Claude Code (Opus 4.7)

> **No production change happens autonomously.** Every step in this
> plan requires founder approval and operator-side `gcloud` action.
> This document is the runbook, not the trigger.

---

## 0. Cloud deployment paused. Local-first mode is primary. (added 2026-05-01)

After this plan was authored, the founder issued a strategic pivot:
**Daena is local-first** for founder/operator development; Cloud Run
is paused as the production target and remains optional (for demos /
managed-client engagements only). See:

- `LOCAL_FIRST_DAENA_ARCHITECTURE.md` — what runs on the founder's
  workstation, how to launch it, and where memory / vault / RAG
  live locally.
- `CLOUD_DEPLOYMENT_PAUSED_DECISION.md` — what's preserved in GCP,
  what's paused, cost-control options for Cloud SQL, resume criteria.

Then the founder revised: **fix the GCloud production foundation now**
(Phases 1–6 below + the Cloud Build NOT_FOUND fix in
`CLOUD_BUILD_NOT_FOUND_DIAGNOSIS.md`) so future deploys are not
painful — but **local-first remains the primary developer workflow**.

Implications for this rotation plan:

- §3 (rotation checklist) and §6 (DATABASE_URL migration) **remain
  the source of truth** for cloud rotation steps. Founder still owns
  provider-side rotation of leaked secrets at issuer surfaces.
- §7 (`deploy-cloud.sh` rewrite) is **DONE** in commit `f7f79dd`.
  `cloudbuild.yaml` is the canonical atomic build+deploy path.
- §9 (founder approval gates) **still apply** for every cloud-side
  action. None are autonomous.
- New gate: every `gcloud builds submit` must follow the recommended
  sequence in `PRODUCTION_HYGIENE_AUTOMATION_REPORT.md` §5 and the
  service-account fix in `CLOUD_BUILD_NOT_FOUND_DIAGNOSIS.md`.

The rest of this plan (§§1–10) reads as originally written.

---

## 1. Production risk assessment

### Confirmed (founder-reported)

| Finding | Severity | Source of evidence |
|---|---|---|
| Cloud Run `DATABASE_URL=sqlite+aiosqlite:///./daena_cloud.db` | **CRITICAL** | Founder-confirmed, 2026-05-01 |
| Multiple live secrets present as raw env vars (not Secret Manager refs) | **CRITICAL** | Founder-confirmed, 2026-05-01 |
| At least 6 secrets exposed in terminal output during inspection | **HIGH** | Same incident, 2026-05-01 |
| `Base.metadata.create_all` runs on every container start in prod | **HIGH** | `backend/app/main.py:800` (no env guard) |
| `deploy-cloud.sh` does NOT run `alembic upgrade head` | **HIGH** | `D:/Ideas/Daena/deploy-cloud.sh` (29 lines, no alembic call) |

### Why each is critical

1. **SQLite on Cloud Run is ephemeral.** Cloud Run containers are
   spun up on demand; each cold start gets a fresh container
   filesystem. The SQLite file `./daena_cloud.db` is created from
   scratch every time a new container boots. Any state written to it
   (tenants, users, audit chain, secrets, vault, settings) is lost
   on container restart. **Daena prod has effectively never had
   durable state.**

2. **Min instances = 0.** Per `PHASE_4A_3_OPERATOR_GATE_REPORT.md`,
   the service is configured to scale to zero. Every period of
   inactivity ⇒ container shutdown ⇒ next request creates a new
   container ⇒ new SQLite file. The window of state loss is minutes,
   not hours.

3. **Multi-instance is broken.** When `max_instances > 1` (currently
   2) and two containers are running, each has its OWN SQLite file.
   Writes from container A are invisible to container B. Audit chain
   integrity is undefined.

4. **Raw secret env vars** mean every operator with `gcloud run`
   read access can dump them via `gcloud run services describe`.
   Compare to Secret Manager refs, which require `secretmanager.versions.access` IAM separately.

5. **`Base.metadata.create_all` in production** masks Alembic stamp
   drift. The schema you get on each cold start is whatever the
   currently-deployed code's `Base.metadata` says, regardless of the
   DB's `alembic_version` row. Combined with ephemeral SQLite, every
   cold start re-creates the schema — but past data is gone anyway,
   so the worst symptom (silent data loss) is masked by an even
   worse one (no data persists at all).

6. **No alembic step in `deploy-cloud.sh`** means even if we fix
   everything else, the operator must remember to run alembic by
   hand on every deploy. That will fail eventually.

### Combined effect

**Production has been a stateless demo.** Every Cloud Run container
boot is a fresh slate. There is no vault, no audit chain, no user
data, no governance trail to migrate or roll back from. This makes
the rotation cheap (nothing to preserve) but the cleanup non-trivial
(clients calling the live URL may have built expectations on
behavior).

The good news: **the V2 work this branch shipped has not been
deployed.** Production is still on the 2026-03-21 image. None of the
V2 code has touched a production environment. We can fix the
foundation cleanly before the V2 cutover.

---

## 2. Exposed secret names (NO VALUES)

The following secret names appeared in terminal output during the
2026-05-01 inspection. **Treat all of them as compromised and rotate
immediately.** Values are NOT included anywhere in this document.

| Env var name | Likely consumer | Rotation surface |
|---|---|---|
| `JWT_SECRET_KEY` | `app/services/auth.py` (access + refresh token signing) | Daena-managed; new strong random value |
| `VAULT_ENCRYPTION_KEY` | Legacy `vault.py` (AES-256-GCM key, deprecated by `DAENA_KEK`) | Daena-managed; only matters until vault.py is retired post-soak |
| `GOOGLE_CLIENT_SECRET` | OAuth callback for Google Drive / Calendar / Gmail integrations | Google Cloud Console → APIs & Services → Credentials → OAuth 2.0 Client IDs |
| `GITHUB_CLIENT_SECRET` | OAuth callback for GitHub connector | github.com → Settings → Developer settings → OAuth Apps |
| `GROQ_API_KEY` | Groq provider integration | console.groq.com → API Keys |
| `GEMINI_API_KEY` | Google Gemini provider integration | aistudio.google.com → API Keys |

**Treat as also-suspect** (any secret currently a raw Cloud Run env
var) — the founder-disclosed list above is the confirmed set, but
the same exposure surface implies any other plaintext env values
should be rotated too. The readiness script in §10 enumerates env
keys (not values) and flags any non-Secret-Manager bindings.

---

## 3. Rotation checklist

For each compromised secret, complete every step in order:

### Step A — Generate new value at the issuing surface

| Secret | Where to generate |
|---|---|
| `JWT_SECRET_KEY` | Locally: `python -c "import secrets; print(secrets.token_urlsafe(64))"`. Do NOT print to a terminal that's screen-shared or being recorded. |
| `VAULT_ENCRYPTION_KEY` | Locally: `python -c "import secrets; print(secrets.token_hex(32))"`. Same caution. |
| `GOOGLE_CLIENT_SECRET` | Google Cloud Console → APIs & Services → Credentials → click the OAuth client → "Add secret" → archive the old one after confirming the new one works. Never both active longer than 24h. |
| `GITHUB_CLIENT_SECRET` | github.com → Settings → Developer settings → OAuth Apps → click your Daena app → "Generate a new client secret" → revoke the old one |
| `GROQ_API_KEY` | console.groq.com → API Keys → "Create API Key" → delete the old one |
| `GEMINI_API_KEY` | aistudio.google.com → "Get API key" → "Create API key in new project" or rotate existing → disable the old one |

### Step B — Store ONLY in Secret Manager (never raw env)

For every secret listed above, create a Secret Manager binding:

```bash
# placeholder names; replace <new-value> with the freshly generated value
# typed into stdin -- NEVER as a positional arg (positional args land
# in the operator's shell history)
echo -n '<new-value>' | gcloud secrets create daena-<secret-name> \
  --project=daena-467315 \
  --replication-policy=automatic \
  --data-file=-

# Grant the Cloud Run runtime service account access
gcloud secrets add-iam-policy-binding daena-<secret-name> \
  --project=daena-467315 \
  --member='serviceAccount:daena-run@daena-467315.iam.gserviceaccount.com' \
  --role='roles/secretmanager.secretAccessor'
```

Do NOT use `--data='<value>'` or any flag that puts the secret on
the command line. Always pipe via stdin.

### Step C — Revoke / archive the old value

| Secret | Revocation step |
|---|---|
| `JWT_SECRET_KEY` | None at the issuer — revocation = redeploy with new value, which invalidates all existing access tokens |
| `VAULT_ENCRYPTION_KEY` | None at the issuer — only matters if you decrypt with the old key; new write/read uses new key |
| `GOOGLE_CLIENT_SECRET` | "Disable" or "Delete" the old secret in Google Cloud Console after the new one is in Secret Manager + verified |
| `GITHUB_CLIENT_SECRET` | "Revoke" the old secret on GitHub after new one verified |
| `GROQ_API_KEY` | Delete old key on console.groq.com after new key in Secret Manager |
| `GEMINI_API_KEY` | Delete old key on aistudio.google.com after new key in Secret Manager |

### Step D — Update `deploy-cloud.sh` to bind from Secret Manager

See §7 for the full rewrite. After §7 lands, every secret is sourced
from Secret Manager, never from `--update-env-vars`.

### Step E — Verify with the readiness script

Run `pwsh scripts/production_readiness_check.ps1` after the deploy.
Every check must PASS before the rotation is considered complete.

### Step F — Rotate JWT means re-login for everyone

Rotating `JWT_SECRET_KEY` invalidates all existing access tokens.
Every user (founder included) will be logged out and must sign in
again. Schedule this rotation when users are not in the middle of
critical work.

⛔ **Founder approval required before each Step A** (and for the
`gcloud` actions in Steps B + D).

---

## 4. Secret Manager migration plan

### Goal

Move every Cloud Run env var that has a value (as opposed to a
non-secret config like `APP_ENV=production`) into Secret Manager
references. After migration, `gcloud run services describe daena
--format='value(spec.template.spec.containers[0].env)'` should show
ONLY:

- Plaintext non-secret config (`APP_ENV`, `LOG_LEVEL`, `CORS_ORIGINS`, etc.)
- Secret references in the form
  `projects/daena-467315/secrets/daena-<name>/versions/latest`

No raw secret values anywhere in the env block.

### Migration order (per secret)

1. Generate new value at issuer (§3 Step A)
2. Push new value into Secret Manager (§3 Step B)
3. Update Cloud Run service to bind the env var via Secret Manager:
   ```bash
   gcloud run services update daena \
     --project=daena-467315 \
     --region=us-central1 \
     --remove-env-vars=<NAME> \
     --update-secrets=<NAME>=daena-<name>:latest
   ```
4. Verify Cloud Run health (next request succeeds)
5. Revoke old value at issuer (§3 Step C)

### Pinning vs `:latest`

For founder-only stage, `:latest` is fine — rotation is rare and
manual. When paying users land, switch to pinned versions
(`daena-<name>:3`) so rotation is a controlled deploy, not an
implicit live change.

### One-time cleanup

After every secret is migrated, run:

```bash
# Verify env block contains only non-secret config + Secret Manager refs
gcloud run services describe daena \
  --project=daena-467315 --region=us-central1 \
  --format='value(spec.template.spec.containers[0].env[].name)'
```

This prints names only (no values). The readiness script does the
same check programmatically.

⛔ **Founder approval required for each `gcloud run services update`.**

---

## 5. Cloud SQL PostgreSQL setup plan

This section is the abbreviated form of `DAENA_DATABASE_READINESS_PLAN.md`
§7.1, with the focus on what's needed to fix the current SQLite-on-Cloud-Run
incident.

### Step 5.1 — Provision instance

```bash
gcloud sql instances create daena-prod \
  --project=daena-467315 \
  --database-version=POSTGRES_16 \
  --region=us-central1 \
  --tier=db-g1-small \
  --storage-size=10 \
  --storage-auto-increase \
  --backup-start-time=03:00 \
  --enable-point-in-time-recovery
```

The `--root-password` MUST be provided via stdin or the Cloud
Console's "Set root password" prompt — never a flag value.

### Step 5.2 — Create database + app user

```bash
gcloud sql databases create daena --instance=daena-prod --project=daena-467315

# App user password also via stdin
gcloud sql users create daena_app --instance=daena-prod --project=daena-467315
# (Cloud Console prompts for password; do not pass --password)
```

### Step 5.3 — Push DB password into Secret Manager

```bash
echo -n '<app-user-password>' | gcloud secrets create daena-db-password \
  --project=daena-467315 --replication-policy=automatic --data-file=-

gcloud secrets add-iam-policy-binding daena-db-password \
  --project=daena-467315 \
  --member='serviceAccount:daena-run@daena-467315.iam.gserviceaccount.com' \
  --role='roles/secretmanager.secretAccessor'
```

### Step 5.4 — Build the DATABASE_URL secret

The full URL combines:
- driver: `postgresql+asyncpg`
- user: `daena_app`
- password: from Secret Manager
- host: `/cloudsql/daena-467315:us-central1:daena-prod` (Unix socket via Cloud SQL Auth Proxy sidecar)
- database: `daena`

Construct locally and push:

```bash
# Construct in stdin (DO NOT echo to terminal)
DB_URL='postgresql+asyncpg://daena_app:<password>@/daena?host=/cloudsql/daena-467315:us-central1:daena-prod'
echo -n "$DB_URL" | gcloud secrets create daena-database-url \
  --project=daena-467315 --replication-policy=automatic --data-file=-

gcloud secrets add-iam-policy-binding daena-database-url \
  --project=daena-467315 \
  --member='serviceAccount:daena-run@daena-467315.iam.gserviceaccount.com' \
  --role='roles/secretmanager.secretAccessor'

unset DB_URL  # clear from current shell
```

### Step 5.5 — Enable extensions

After the instance is up, connect via Cloud SQL Studio (browser) or
the auth proxy and run:

```sql
CREATE EXTENSION IF NOT EXISTS pgvector;
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS btree_gin;
```

⛔ **Founder approval before Step 5.1** (creating the instance is the
first chargeable action).

---

## 6. DATABASE_URL migration: SQLite → Cloud SQL Postgres

### Current state

```
Cloud Run env: DATABASE_URL=sqlite+aiosqlite:///./daena_cloud.db
```

→ Container creates a fresh SQLite file on every cold start. State is
ephemeral. There is **nothing to migrate from** the current prod DB
because past data is already gone (or was lost on the most recent
container restart).

### Target state

```
Cloud Run env: DATABASE_URL = (Secret Manager ref to daena-database-url)
                              → postgresql+asyncpg://daena_app:***@/daena?host=/cloudsql/...
```

### Migration steps

1. **Provision Cloud SQL Postgres** (§5)
2. **Update `deploy-cloud.sh`** to bind the secret (§7)
3. **Add Alembic startup step** (§7) so schema is created on first deploy
4. **Add `Base.metadata.create_all` production guard** (§7) so future
   silent drift is blocked
5. **Deploy** with the new bindings + entrypoint
6. **Verify** the readiness script PASS

### Data preservation: NONE NEEDED

Since prod state is and always has been ephemeral, there's nothing
to dump/transform/load. The first deploy after this plan is the
first deploy with durable storage. Treat it as a fresh prod.

### One-shot operator verification (after deploy)

```bash
gcloud sql connect daena-prod --user=daena_app --project=daena-467315
\dn   # list schemas
\dt   # list tables
SELECT version_num FROM alembic_version;  -- expected: 007_connection_v2_registry
```

⛔ **Founder approval required for the deploy that switches the binding.**

---

## 7. Required `deploy-cloud.sh` changes

### Current `deploy-cloud.sh` (29 lines) — what it does today

- Updates Cloud Run env vars with `GROQ_API_KEY` + `GEMINI_API_KEY`
  + `OLLAMA_BASE_URL=` + `APP_ENV=production` AS RAW ENV VARS
- Prints the service URL
- Hits `/api/v1/health`

### What it does NOT do (gaps)

1. ❌ Bind any value from Secret Manager
2. ❌ Add Cloud SQL instance connection
3. ❌ Bind DATABASE_URL (production falls back to the SQLite default
   in `app/core/config.py:134`)
4. ❌ Run `alembic upgrade head` before serving
5. ❌ Block `Base.metadata.create_all` in production
6. ❌ Verify the readiness check after deploy

### Required rewrite (with safe placeholders only)

The new `deploy-cloud.sh` must look approximately like this (DO NOT
copy without founder approval; secret names + IDs need confirmation):

```bash
#!/bin/bash
set -euo pipefail

PROJECT='daena-467315'
REGION='us-central1'
SERVICE='daena'
CLOUDSQL_INSTANCE="${PROJECT}:${REGION}:daena-prod"

echo "=== Daena Cloud Deploy ==="
echo "Pre-flight readiness check..."
pwsh scripts/production_readiness_check.ps1 || {
  echo "❌ Readiness check failed. Aborting deploy."
  exit 1
}

echo "1. Updating Cloud Run service with Secret Manager bindings..."
gcloud run services update "${SERVICE}" \
  --project="${PROJECT}" \
  --region="${REGION}" \
  --add-cloudsql-instances="${CLOUDSQL_INSTANCE}" \
  --update-env-vars="\
APP_ENV=production,\
LOG_LEVEL=info,\
USE_CONNECTION_REGISTRY_V2=false,\
DISABLE_AUTH=false,\
CORS_ORIGINS=https://daena.mas-ai.co,\
OLLAMA_BASE_URL=" \
  --update-secrets="\
DATABASE_URL=daena-database-url:latest,\
DAENA_KEK=daena-kek:latest,\
JWT_SECRET_KEY=daena-jwt-secret:latest,\
GROQ_API_KEY=daena-groq-api-key:latest,\
GEMINI_API_KEY=daena-gemini-api-key:latest,\
GOOGLE_CLIENT_SECRET=daena-google-client-secret:latest,\
GITHUB_CLIENT_SECRET=daena-github-client-secret:latest" \
  --remove-env-vars="VAULT_ENCRYPTION_KEY"  # legacy, retired post-soak

echo ""
echo "2. Verifying deployment + schema state..."
SERVICE_URL=$(gcloud run services describe "${SERVICE}" \
  --project="${PROJECT}" --region="${REGION}" --format='get(status.url)')
echo "Service URL: ${SERVICE_URL}"

TOKEN=$(gcloud auth print-identity-token)
curl -fsS -H "Authorization: Bearer ${TOKEN}" \
  "${SERVICE_URL}/api/v1/health/detailed" \
  | python -m json.tool

echo ""
echo "3. Post-deploy readiness re-check..."
pwsh scripts/production_readiness_check.ps1
echo ""
echo "=== Deploy complete ==="
```

### Required Dockerfile / entrypoint change (Alembic)

The container must run `alembic upgrade head` BEFORE `uvicorn`. If
the Dockerfile currently runs uvicorn directly, replace with a
shell entrypoint:

```bash
#!/bin/sh
# /app/start.sh
set -e
cd /app/backend
echo "Running Alembic migrations..."
alembic -c migrations/alembic.ini upgrade head
echo "Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8080}"
```

Then in Dockerfile:
```dockerfile
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh
ENTRYPOINT ["/app/start.sh"]
```

### Required `app/main.py` production guard

Wrap the `Base.metadata.create_all` call (currently
`backend/app/main.py:800`) so production fails loudly if Alembic
didn't run:

```python
# In lifespan ESSENTIALS, around line 798-810:
async with engine.begin() as conn:
    if not settings.is_production:
        # Dev convenience: idempotent CREATE TABLE IF NOT EXISTS for
        # rapid iteration. NEVER runs in production -- production
        # schema must come from Alembic.
        await conn.run_sync(Base.metadata.create_all)
    else:
        # Production sanity: assert alembic_version is at expected head.
        from sqlalchemy import text as _text
        result = await conn.execute(_text("SELECT version_num FROM alembic_version"))
        current = result.scalar_one_or_none()
        if current is None:
            raise RuntimeError(
                "Production schema check failed: alembic_version table is "
                "empty. Run `alembic upgrade head` before booting."
            )
        logger.info("essentials.alembic_at", version=current)

    # The hand-rolled ALTER TABLE block below MUST also be guarded --
    # it duplicates Alembic 004/006 logic and is dev-only.
    if not settings.is_production:
        from sqlalchemy import text as _text
        # ... existing _nbmf_cols + _chat_session_cols block ...
```

⛔ **Founder approval required for each of the three rewrites above.**
None of them will be applied autonomously.

---

## 8. Rollback plan

### If post-deploy health check fails

```bash
# Roll back to the previous revision
gcloud run services update-traffic daena \
  --project=daena-467315 --region=us-central1 \
  --to-revisions=daena-<previous-revision>=100
```

The previous revision is the 2026-03-21 image, which has none of the
V2 work and uses raw env vars + ephemeral SQLite. Rolling back
restores prior (broken-but-running) behavior; it does NOT preserve
any new state because SQLite was already ephemeral.

### If the new Postgres deploy fails to come up

Cloud SQL instance survives independently of Cloud Run. The
operator can:
1. Roll Cloud Run back per the previous step.
2. Inspect Cloud SQL via `gcloud sql connect`.
3. Re-deploy after the issue is fixed; Cloud SQL data persists.

### If a rotated secret is wrong

Each Secret Manager secret retains version history. The operator can:
```bash
gcloud secrets versions list daena-<name> --project=daena-467315
gcloud run services update daena --update-secrets=<NAME>=daena-<name>:<previous-version>
```

### What CANNOT be rolled back

- A leaked secret cannot be "un-leaked." Once exposed, it must be
  rotated. The 6 secrets in §2 are committed to rotation regardless
  of any later decision.
- Once `USE_CONNECTION_REGISTRY_V2=true` is flipped on prod with
  data behind it, downgrade requires either a vault dual-read window
  or a data migration. **Do NOT flip the V2 flag on prod until the
  vault soak window has run cleanly.**

---

## 9. Founder approval gates

Each ⛔ gate below requires explicit founder approval before proceeding.
Default action when ungated: **STOP**.

| # | Gate | Owner |
|---|---|---|
| 1 | Generate new values for the 6 exposed secrets (§3 Step A) | Founder (per-issuer) |
| 2 | Push new values into Secret Manager (§3 Step B) | Operator with founder approval |
| 3 | Provision Cloud SQL Postgres instance (§5.1) | Founder + Operator |
| 4 | Create `daena-database-url` secret (§5.4) | Founder + Operator |
| 5 | Rewrite `deploy-cloud.sh` per §7 | Founder review of diff before commit |
| 6 | Add `start.sh` entrypoint + Dockerfile change (§7) | Founder review |
| 7 | Add `Base.metadata.create_all` production guard in `main.py` (§7) | Founder review |
| 8 | First production deploy with new bindings | Founder explicit go |
| 9 | Revoke old secrets at issuer surfaces (§3 Step C) — only after new ones are verified working | Founder (per-issuer) |
| 10 | Vault migration `--apply` on prod (out of scope here; see prior plan) | Founder + Operator |
| 11 | Flip `USE_CONNECTION_REGISTRY_V2=true` on prod (out of scope here) | Founder + Operator after 7-day soak |

---

## 10. Local vs GCP/operator split

### What CAN be done locally (no production touch)

- ✅ This plan (already done)
- ✅ `scripts/production_readiness_check.ps1` (already done)
- ✅ Generate the new secret values locally (Step A) — provided the
  generation environment is not screen-shared / recorded
- ✅ Update `deploy-cloud.sh` and `app/main.py` in a separate PR
  branch for founder review (not pushed to main, not deployed)
- ✅ Test the readiness script against the local repo (it checks
  file shapes; the gcloud checks will fail without auth, which is
  intentional — see "Local vs GCP modes" in the script)

### What REQUIRES GCP / operator access

- Pushing values to Secret Manager (Step B + §5.4)
- Provisioning Cloud SQL (§5.1)
- `gcloud run services update` (§6 + §7)
- Revoking secrets at issuer surfaces (Step C)
- Verifying `gcloud sql connect` schema (§6)
- Running the deployed service health check
- Rotating Google / GitHub OAuth client secrets (web console actions)

### What CANNOT be done by Claude Code

- Anything that mutates production
- Anything that requires `gcloud` authentication (Claude Code does
  not have a service account binding)
- Any action that prints or commits a secret value

---

## Summary of what to do RIGHT NOW

1. **Stop using the 6 exposed secrets.** Plan their rotation per §3.
2. **Run the readiness script** locally to see the current state of
   the deployed service: `pwsh scripts/production_readiness_check.ps1`
3. **Decide on Cloud SQL provisioning timing.** Earliest: today.
   Latest: before any prod deploy that needs durable state.
4. **Do not deploy** until §7's `deploy-cloud.sh` rewrite + §5's
   Cloud SQL provisioning + §3's secret rotation are all done AND
   founder-approved.
5. **Do not flip `USE_CONNECTION_REGISTRY_V2=true`** in production
   until the vault soak window has run cleanly post-Postgres-cutover.

---

**Generated:** 2026-05-01
**Generated by:** Claude Code (Opus 4.7)
**No production changes were made by this document.**
