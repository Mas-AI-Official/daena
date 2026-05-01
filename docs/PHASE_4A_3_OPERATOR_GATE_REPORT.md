# Phase 4a-3 Operator Gate Report

**Branch:** `rebuild-connections-mcp-runtime`
**HEAD:** `94a0dcf`
**Generated:** 2026-04-30
**Author:** Claude Opus 4.7 (read-only investigation; no `--apply` executed)

> Per founder Phase 4a-3 operator-gate instruction. **`--apply` was NOT run** (founder rule). All checks below are read-only.

---

## 1. Current environment

| Indicator | Finding |
|---|---|
| `APP_ENV` in `backend/.env` | `development` |
| `core/config.py` default | `app_env: str = "development"` |
| Active DB pointer (`DATABASE_URL`) | `sqlite+aiosqlite:///./daena_dev2.db` |
| Local dev DB file | `backend/daena_dev2.db` (exists, populated) |
| `.env.staging` / `.env.production` | NOT present (only `.env.example`) |
| `VAULT_ENCRYPTION_KEY` (legacy) | `dev-only-32-byte-key-for-aes2560` (placeholder pattern) |
| `DAENA_KEK` (new) | NOT set |

**Verdict:** Local working copy is in **dev mode**, pointing at a SQLite file.

## 2. Production / staging targets

### Production: **EXISTS**

Per `D:/Ideas/Daena/DEPLOYED-URL.txt` + `deploy-cloud.sh`:

| Field | Value |
|---|---|
| Service URL | `https://daena-596551989073.us-central1.run.app` |
| Custom domain | `https://daena.mas-ai.co` (pending DNS) |
| GCP Project | `daena-467315` |
| Region | `us-central1` |
| Service account | `daena-run@daena-467315.iam.gserviceaccount.com` |
| Image | `us-central1-docker.pkg.dev/daena-467315/daena-repo/daena:latest` |
| Last deploy | 2026-03-21 |
| Min/Max instances | 0 / 2 (scales to zero) |
| `APP_ENV` in Cloud Run | `production` (set by `deploy-cloud.sh`) |

**The production service exists and was deployed 2026-03-21.** Live status was NOT verified by this report (Cloud Run health endpoint requires a GCP identity token; checking it requires founder-side `gcloud auth print-identity-token`).

### Staging: **NOT FOUND**

No `.env.staging`, no second Cloud Run service in `deploy-cloud.sh`, no staging-specific scripts. If staging exists, this report does not see it.

### Production database

Production DB binding is **NOT directly visible from this branch.** `deploy-cloud.sh` updates env vars but does not show `DATABASE_URL` for production — the prod DB connection is set elsewhere (likely Cloud Run secret manager OR a Postgres instance whose URL is in a GCP-managed env var). This report cannot determine:
- Whether prod uses Cloud SQL Postgres or another store.
- How many `ConnectorInstance` rows exist in prod.
- How many have non-null `credentials` blobs.

**Founder action required:** to know prod's encrypted-credential count, run the dry-run script against prod (Section 4.4).

## 3. ConnectorInstance + alt secret stores in dev DB

`backend/daena_dev2.db` (sqlite, 50 tables):

| Store | Rows | Real encrypted secrets? |
|---|---|---|
| `connector_instances` (total) | 44 | No |
| `connector_instances` with `credentials != SQL NULL` | 44 | No -- every cell stores the JSON literal `"null"` (4-char string), classified by the migration script as `skipped/null` |
| `vault_secrets` | 0 | (empty) |
| `secrets` (Phase 4a-2 new table) | 0 | (empty -- table created by `Base.metadata.create_all` in this session; migration 006 not applied via Alembic) |
| `oauth_credentials_store.json` (`backend/.daena_oauth_overrides.json`) | NOT PRESENT | n/a |
| `oauth_credentials` table | NOT PRESENT | n/a |
| `user_oauth_tokens` table | NOT PRESENT | n/a |

**Verdict for dev DB: ZERO real encrypted credential blobs anywhere.** Nothing to migrate.

## 4. Safe checks executed

### 4.1 `alembic current`

```
FAILED: No 'script_location' key found in configuration.
```

Alembic CLI is not configured at the repo root (`alembic.ini` missing). Migrations exist as importable Python files (chain `001 -> 002 -> 003 -> 004 -> 005 -> 006` verified by `importlib`), but the application currently relies on `Base.metadata.create_all` in `main.py` lifespan ESSENTIALS rather than Alembic stamping. **This is a known operator gap** -- production may apply migrations via a deploy hook OR not at all. Founder action: confirm whether prod runs `alembic upgrade head` on deploy.

### 4.2 `alembic heads`

Same FAILED message. Migration files in `backend/migrations/versions/` are present and correctly chained:

```
001_add_autopilot_think_mode (down=None)
002_add_pipeline_lost_columns (down=001)
003_add_workstreams (down=002)                          [committed 4d97f88]
004_add_chat_session_workstream_fk (down=003)           [committed 4d97f88]
005_add_cron_mcp_background_tables (down=004)           [committed 4d97f88]
006_secrets_envelope_vault (down=005)                   [committed f0c9f85]
```

### 4.3 Migration 006 file present

```
backend/migrations/versions/006_secrets_envelope_vault.py  (exists)
```

Tested by `importlib.util.spec_from_file_location` -- imports cleanly; `revision == "006_secrets_envelope_vault"`, `down_revision == "005_add_cron_mcp_background_tables"`. Test `test_secret_model.py::TestMigration006::test_migration_006_revision_chain` passes.

### 4.4 Dry-run on dev DB

```
candidate=44  already_migrated=0  skipped=44  failed=0
drift=0       written=0           dek_provisioned=0  aborted=False
```

JSON report at `/tmp/dry_run_report.json`. All 44 candidates are skipped because `credentials = JSON null` (legacy state, not encrypted). **No actual cipher work or DEK provisioning occurred.** This dev DB has nothing to migrate.

### 4.5 `--apply` NOT run

Per founder rule. Not executed locally; not executed against any remote DB.

## 5. Decision rule application

Founder rule:
> If no production DB and no real credentials exist, mark production migration gate as N/A for now and allow Phase 4b dev implementation.
> If production DB or real credentials exist, Phase 4b remains blocked until production dry-run report is reviewed by founder.

**Production DB: EXISTS** (Cloud Run service deployed 2026-03-21 at `daena-596551989073.us-central1.run.app`).
**Real credentials: UNKNOWN for prod, ZERO in dev.**

Under the founder rule, **production exists** triggers the second branch:
> Phase 4b remains blocked until production dry-run report is reviewed by founder.

## 6. Verdicts

### Is there a production DB?

**YES.** Cloud Run service `daena` in GCP project `daena-467315`, deployed 2026-03-21. The DB binding is not visible from this repo (likely set via Cloud Run env vars / Secret Manager). Live state not verified by this report.

### Are there real encrypted credentials?

| Scope | Verdict |
|---|---|
| Local dev DB | **NO** -- zero real encrypted blobs (44 JSON-null cells; 0 vault_secrets rows; no legacy JSON file) |
| Production | **UNKNOWN** -- this report cannot inspect the prod DB without operator-side credentials |

### Dev dry-run counts

```
candidate          44
already_migrated    0
skipped            44   (all "null" -- no real blobs)
failed              0
drift               0
written             0
dek_provisioned     0
aborted         False
```

### Whether production dry-run is required

**YES.** Production dry-run is REQUIRED before Phase 4b ships any code that writes secrets via vault_v2. Without it, Phase 4b would be working blind on whether legacy prod data round-trips correctly. The Phase 4a-3 script is the right tool; it just needs to be run by the operator with prod DB access + DAENA_KEK in env.

### Whether Phase 4b can start in dev-only mode

**Conditional YES, with explicit constraints:**

Phase 4b dev work CAN proceed for the following IF the founder accepts the trade-off:
- Schema design + Alembic migration `007_connection_v2` (the registry table)
- ConnectionRegistryV2 service layer (`backend/app/services/connection_v2/`)
- Per-kind discriminated-union Pydantic validation
- Tests against in-memory SQLite
- Frontend `useConnectionRegistry` hook against new API
- `_status_for_install` deletion (per ADR-002 D-010)

But Phase 4b CANNOT ship to production until:
- Operator runs `--dry-run` against prod and shares the report
- Founder approves `--apply`
- Operator runs `--apply` on prod
- 7-day soak window (or shorter equivalent + reconciliation cron) confirms zero drift

This means dev work and prod migration can proceed in parallel: Claude builds Phase 4b in dev while the operator runs the dry-run/apply/soak in prod. They converge at deploy time.

### What would block Phase 4b for production deploy

Per ADR-002 D-003 + Phase 4a-3 spec, the gate to PRODUCTION DEPLOY of Phase 4b is:

1. **Operator-side prod investigation** (Claude cannot do this from here):
   - Confirm whether prod runs `alembic upgrade head` on deploy. If not: configure it OR apply 006 manually via a one-shot job.
   - Confirm prod `DAENA_KEK` is set (or operator sets it for the first time -- migration 006 + the new lifespan ESSENTIALS step from `09b393a` are the things that require it). For first-time setup: generate 32 random bytes, base64-encode, store in Cloud Run Secret Manager as `DAENA_KEK`, redeploy. The KEK fingerprint logged at boot (`vault.kek_loaded sha256_prefix=<8hex>`) is the verification that the right value is loaded.
   - Run `python -m backend.scripts.migrate_vault_to_v2 --dry-run --report-json prod_dryrun.json` from a Cloud Run job OR from a local shell with the prod DATABASE_URL + DAENA_KEK in env.
   - Share `prod_dryrun.json` with the founder.

2. **Founder approval to `--apply` on prod.**

3. **Operator runs `--apply`** with the same env. Drift in apply mode aborts the batch (no partial state).

4. **7-day soak window** with both legacy `core/vault.py` and new `vault_v2` paths exercised. Phase 4b will need to add a reconciliation cron OR the operator can manually re-run `--dry-run` periodically to confirm zero drift.

5. **Phase 4b production rollout** (registry rewrite, frontend cutover, eventually delete legacy `core/vault.py` + `oauth_credentials_store.py`).

## 7. Recommendation to the founder

Two choices:

**(A) Strict gate (recommended):** Phase 4b is BLOCKED entirely until the operator runs prod dry-run + apply + soak. No Claude work on Phase 4b until that's done. Pro: zero risk of building Phase 4b on top of a vault path that hasn't been validated against real prod data. Con: Claude is idle for several days while operator investigates prod.

**(B) Parallel dev path (faster but riskier):** Claude builds Phase 4b in dev mode now (against in-memory SQLite + dev DB), keeping the legacy `core/vault.py` path live throughout. Operator runs prod dry-run / apply / soak in parallel. Phase 4b deploys to prod ONLY after the soak window proves zero drift. Pro: time-saving. Con: requires discipline to keep legacy path live in Phase 4b code (no premature `import app.core.vault` removal); risk of needing to rework Phase 4b if prod dry-run reveals a previously unknown legacy data shape.

If the founder picks (B), Claude will:
- Build Phase 4b reading EITHER legacy `core/vault.py` OR new `vault_v2` (whichever has the row), so it works pre- and post-migration
- Add a `feature flag USE_VAULT_V2` (default false) that gates which path the writers use
- NOT delete legacy vault.py / oauth_credentials_store.py
- NOT remove the DEK auto-provisioning from the migration script
- Document the cutover sequence so the operator can flip the flag after soak

**Stopping here per Phase 4a-3 founder instruction. No code changes. No `--apply`. Awaiting decision: (A) wait for prod soak before Phase 4b, or (B) start Phase 4b dev work in parallel.**
