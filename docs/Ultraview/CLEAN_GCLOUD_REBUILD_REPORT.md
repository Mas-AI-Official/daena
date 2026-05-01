# Clean GCloud Rebuild — Cutover Verification Report

**Date:** 2026-05-01
**Operator:** Claude Code (Opus 4.7) at founder direction
**Plan:** `docs/Ultraview/CLEAN_GCLOUD_REBUILD_PLAN.md`
**Mode:** verification only; no further deploys triggered.

> **Status one-liner:** infrastructure rebuild SUCCEEDED on every checked surface (Secret Manager, Cloud SQL, schema bootstrap, alembic, image, IAM). The app then refused to serve because `CORS_ORIGINS` is unset in the deploy config, and `app/main.py:758` correctly aborts production startup on localhost-only CORS. Schema is healthy, DB is Postgres + linked, no working revision is yet receiving traffic.

---

## 1. Build ID

`8d232870-50de-4e12-aaff-bd163817b104`

| Field        | Value |
| ------------ | ----- |
| Status       | `FAILURE` (after `WORKING` blocked on revision health-check timeout) |
| Created      | 2026-05-01T19:00:47Z |
| Source SHA   | `5646877` (HEAD of `rebuild-connections-mcp-runtime`) |
| Image pushed | `us-central1-docker.pkg.dev/daena-467315/daena-repo/daena:8d232870-…` + `:latest` |
| Build SA     | `daena-build@daena-467315.iam.gserviceaccount.com` |
| Runtime SA   | `daena-run@daena-467315.iam.gserviceaccount.com` |

The build's docker steps (build + 2x push) finished cleanly. The 4th step (`gcloud run deploy`) created revision `daena-v2-00002-vcp` but waited the full health-check window for it to become Ready; the revision crashed on startup, so the build step exited non-zero. That is correct behavior.

Two earlier builds in the same window also FAILed (`62016675-…`, `683e8403-…`) before the schema-bootstrap fix landed; those were the source of revision `daena-v2-00001-zw5`'s alembic crash.

## 2. Cloud Run service name

`daena-v2`  (project `daena-467315`, region `us-central1`)

This is the fresh service per `CLEAN_GCLOUD_REBUILD_PLAN.md`. The legacy `daena` service has been left untouched for autopsy and holds 4 broken revisions on a stale 2026-04-08 image.

## 3. Latest revision

`daena-v2-00002-vcp`

| Revision           | Status                  | Reason |
| ------------------ | ----------------------- | ------ |
| `daena-v2-00001-zw5` | `False` (failed)      | `alembic upgrade head` ran against an empty DB and tried `001_add_autopilot_think_mode` → `NoSuchTableError: chat_sessions`. Pre-bootstrap-fix image. |
| `daena-v2-00002-vcp` | `Unknown` (provisioning, will resolve to `False`) | Schema bootstrap succeeded; uvicorn started; FastAPI lifespan raised `RuntimeError: Unsafe runtime configuration: CORS_ORIGINS still points only to localhost addresses` at `backend/app/main.py:758`. |

`status.latestReadyRevisionName` is empty. `status.url` is empty. The service has no revision serving traffic.

## 4. Readiness check result

`pwsh scripts/production_readiness_check.ps1` against `daena-v2`:

```
PASS: 16   FAIL: 0   WARN: 1   SKIP: 0
```

WARN is `CORS-ORIGINS-RESTRICTED` ("CORS_ORIGINS not set on the service spec; using app default; verify it's restrictive"). All 16 PASS items: deploy script structure, migration step in entrypoint, secret bindings, Cloud SQL link, `Base.metadata.create_all` guard, Dockerfile entrypoint, gcloud auth, `gcloud run services describe`, DATABASE_URL is Secret Manager-backed, all 8 secrets bound, `APP_ENV=production`, `DISABLE_AUTH=false`, `USE_CONNECTION_REGISTRY_V2=false`, env inventory (12 entries: 8 secret refs + 4 plaintext), Cloud SQL link present, all 8 required Secret Manager secrets exist.

The script never hit `/api/v1/health`; it has no live-traffic probe in the current `daena-v2` configuration, so the WARN was the only signal flagging the CORS gap that later crashed the app.

## 5. DATABASE_URL is Secret Manager-backed

**Yes.** Cloud Run env spec on revision `daena-v2-00002-vcp`:

| Env var name | Source |
| ------------ | ------ |
| `DATABASE_URL` | `valueFrom.secretKeyRef.name = daena-database-url` |

No plaintext fallback. Verified by projecting `spec.containers[0].env[].valueFrom.secretKeyRef.name` (resource name only, value never resolved).

## 6. DATABASE_URL is Postgres, not SQLite

**Yes (Postgres).** Two independent confirmations:

1. Revision `daena-v2-00001-zw5` alembic stdout: `INFO  [alembic.runtime.migration] Context impl PostgresqlImpl. Will assume transactional DDL.` — alembic resolved the URL to a Postgres dialect at runtime.
2. The `daena-database-url` secret resource was provisioned by this rebuild as `postgresql+asyncpg://daena_app:…@/daena?host=/cloudsql/daena-467315:us-central1:daena-db` (Unix-socket Cloud SQL Auth Proxy form). Value confirmed indirectly via successful Postgres connect; never printed.

## 7. Cloud SQL is linked

**Yes.**  Service template annotation on `daena-v2`:

```
run.googleapis.com/cloudsql-instances=daena-467315:us-central1:daena-db
```

The runtime SA `daena-run` carries `roles/cloudsql.client`, which was the missing permission on the first pass and has been granted. Cloud Run mounts the auth-proxy socket at `/cloudsql/daena-467315:us-central1:daena-db/`, matching the `host=` in the secret.

## 8. Alembic ran

**Yes.** Entrypoint stdout from `daena-v2-00002-vcp`:

```
[entrypoint] Checking schema state...
[entrypoint] Schema state: no-alembic-table
[entrypoint] First boot -- bootstrapping schema via SQLAlchemy...
[entrypoint] Stamping alembic to head (skip historical migrations)...
[entrypoint] Starting uvicorn on port 8080...
```

The bootstrap branch in `start.sh` correctly took the `no-alembic-table` path, ran `Base.metadata.create_all`, then `python3 -m alembic -c migrations/alembic.ini stamp head`, then `exec uvicorn`. On all subsequent boots against this DB, `alembic upgrade head` will run and be a no-op (the next-migration apply when one is added will work normally).

## 9. App started successfully

**No.** Stack from `daena-v2-00002-vcp`:

```
File "/app/app/main.py", line 758, in lifespan
    raise RuntimeError(
        "Unsafe runtime configuration: " + "; ".join(guardrail_issues)
    )
RuntimeError: Unsafe runtime configuration: CORS_ORIGINS still points only to localhost addresses
ERROR:    Application startup failed. Exiting.
```

The guard at `backend/app/main.py:750-760` evaluates `diagnostics["guardrail_issues"]`; in production (`APP_ENV=production`) and with `disable_auth=false`, it raises rather than warns, which is the intended fail-closed behavior. uvicorn child process [47] was killed; container exited; Cloud Run health check timed out → revision marked failed.

This is a config gap, not a regression. `cloudbuild.yaml` and `deploy-cloud.sh` set `APP_ENV`, `LOG_LEVEL`, `USE_CONNECTION_REGISTRY_V2`, `DISABLE_AUTH` plaintext but do **not** include `CORS_ORIGINS`.

## 10. USE_CONNECTION_REGISTRY_V2 is still false / unset

**Confirmed `false` (plaintext).**

```
USE_CONNECTION_REGISTRY_V2  false
```

Locked by:
- `cloudbuild.yaml:48` — `--update-env-vars=APP_ENV=production,LOG_LEVEL=info,USE_CONNECTION_REGISTRY_V2=false,DISABLE_AUTH=false`
- `deploy-cloud.sh:56` — same env block.
- Readiness check assertion `V2-FLAG-NOT-FLIPPED` PASS.

The flag is not bound to Secret Manager (correct — it is operational, not a credential), and is enforced as plaintext on every revision spec the rebuild emits.

## 11. Remaining manual secret rotations

These are credentials we cannot rotate from the operator side without an external touch. None are on the critical path for cutover, but should be cycled to lock out any pre-rebuild leakage surface:

| Secret resource              | Action                                                                    | Owner |
| ---------------------------- | ------------------------------------------------------------------------- | ----- |
| `daena-groq-api-key`         | Rotate at Groq console; `gcloud secrets versions add daena-groq-api-key …`        | Founder |
| `daena-gemini-api-key`       | Rotate at Google AI Studio; `gcloud secrets versions add daena-gemini-api-key …`  | Founder |
| `daena-google-client-secret` | Rotate at Google Cloud Console OAuth client; add new version                      | Founder |
| `daena-github-client-secret` | Rotate at GitHub OAuth App; add new version                                       | Founder |

Already done by the rebuild (no founder action required):
- `daena-database-url` — new Postgres user + password generated this cutover, written to Secret Manager only.
- `daena-daena-kek` — provisioned this cutover.
- `daena-jwt-secret-key` — provisioned this cutover.
- `daena-vault-encryption-key` — rotated this cutover after the prior describe-leak incident.

**Open infra task (not a rotation):** add `CORS_ORIGINS` to the deploy config. Suggested value once a domain is mapped: `https://daena.mas-ai.co` (or the actual `*.run.app` URL of `daena-v2` while pre-domain). Wire into both `cloudbuild.yaml` and `deploy-cloud.sh` `--update-env-vars` block. This is a config edit + redeploy, not a rotation; queued for the next deploy turn.

## 12. Rollback path

There is **no working previous revision** to roll back to:

- `daena-v2-00001-zw5` — failed (alembic on empty DB).
- `daena-v2-00002-vcp` — failed (CORS guardrail).
- `daena` (legacy) — out-of-scope; 4 revisions on stale 2026-04-08 image, was already broken before this rebuild and is preserved untouched for autopsy per the rebuild plan.

Forward-only paths, in order of preference:

1. **Fix-and-redeploy (cheapest, recommended):** add `CORS_ORIGINS=<domain>` to `cloudbuild.yaml` and `deploy-cloud.sh` env block; `gcloud builds submit --config=cloudbuild.yaml .`; the new revision will start cleanly because the schema is already bootstrapped and the alembic_version table exists. Single-shot, single attempt.
2. **Fall back to local-first:** `daena-v2` stays in its current "configured but not Ready" state; founder runs the stack locally per `LOCAL_FIRST_DAENA_ARCHITECTURE.md` until cloud is unblocked. Cloud surface costs remain only for storage (image + secrets + Cloud SQL idle); no compute is billed because no revision is healthy.
3. **Tear down `daena-v2`:** `gcloud run services delete daena-v2 …` if the founder wants the rebuild parked. Cloud SQL instance, Secret Manager secrets, Artifact Registry image, and IAM bindings remain available for the next attempt and should NOT be deleted with the service.

The DB itself (`daena-db` instance, `daena` database, `daena_app` user) is in a clean post-bootstrap state — schema present, no rows. Nothing to roll back inside Postgres.

---

## Founder action items

1. **Decide path forward:** fix-and-redeploy with `CORS_ORIGINS` set, or stay local-first and park `daena-v2`.
2. **Rotate the four provider secrets** (Groq, Gemini, Google OAuth, GitHub OAuth) at your convenience and add new versions via `gcloud secrets versions add`.
3. **No production traffic** is reaching `daena-v2`; nothing is at risk while this report is reviewed.

## What this report does not include

- Secret values (none read or printed).
- A retry of the deploy. The founder's instruction was verify-only; this run honored that.
- Any change to the working tree besides the report file itself.
