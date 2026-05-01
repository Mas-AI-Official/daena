# Daena — Database Readiness Plan

**Date:** 2026-05-01
**Branch:** `rebuild-connections-mcp-runtime`
**Audience:** Founder + Operator
**Purpose:** Honest assessment of Daena's current database posture +
recommended path to a production-grade Postgres-backed deployment.

This plan answers the 10 founder questions and locks in the
recommended position: **SQLite for local dev, PostgreSQL (with
pgvector) for production, MongoDB only if a clear document-store
requirement emerges.** Production must NOT rely on
`Base.metadata.create_all` for schema management.

---

## TL;DR

| Topic | Current state | Recommendation |
|---|---|---|
| Local dev DB | SQLite (`backend/daena_dev2.db`) | Keep SQLite for dev; it's fine |
| Production DB | UNKNOWN — not visible from this branch | Make it Cloud SQL Postgres 16 |
| Schema management | `Base.metadata.create_all` + ad-hoc `ALTER TABLE` in lifespan | Alembic only; remove `create_all` from prod path |
| Vector storage / RAG | None active in `connection_v2` truth store; embeddings used elsewhere | Add `pgvector` extension on prod Postgres; co-locate with relational data |
| Audit logs | `goa_audit_events` table, hash-chained | Stays on Postgres in same DB; partition by month after 1M rows |
| Secrets | `secrets` table, envelope-encrypted | Stays on Postgres; KEK in Cloud Run Secret Manager (already designed) |
| MongoDB | NOT in active use | Skip until a clear document-store need emerges (none today) |

**Production deploy is currently NOT safe** for the same 4 reasons as
the prior `MIGRATION_SYSTEM_GAP_REPORT.md`:
1. Schema state in prod is unknown
2. No `alembic upgrade head` step in `deploy-cloud.sh`
3. `tenants.dek_wrapped` may not exist in prod yet
4. The implicit `Base.metadata.create_all` masks alembic stamp drift

This plan provides the migration sequencing to fix all 4.

---

## 1. What DB is Daena using locally?

**SQLite via aiosqlite, file at `backend/daena_dev2.db`.**

```
DATABASE_URL=sqlite+aiosqlite:///./daena_dev2.db
```

`backend/app/core/config.py` line 134:
```python
database_url: str = "sqlite+aiosqlite:///./daena_dev2.db"
```

Tables are created via two paths:
1. **Alembic migrations** at `backend/migrations/versions/` (currently
   001 → 007). Used when the operator runs
   `alembic -c migrations/alembic.ini upgrade head`.
2. **`Base.metadata.create_all`** in `app/main.py` lifespan ESSENTIALS
   (line ~742). This is the path that actually runs in dev.

In dev, the second path is the source of truth. Tables for migrations
that Alembic never stamped (e.g. 005, 006, 007) exist on disk because
`create_all` is idempotent. The dev DB has at least 50 tables.

Models use **portable type decorators** (`backend/app/models/base.py`):
- `GUID()` — `CHAR(36)` on SQLite, native `UUID` on Postgres
- `JSONBCompat` — `JSON` on SQLite, native `JSONB` on Postgres

That portability is intentional: the same model file works on both
backends.

## 2. What DB is production using or expected to use?

**UNKNOWN to this branch.**

Per the prior `PHASE_4A_3_OPERATOR_GATE_REPORT.md` §2:
- Production exists at `https://daena-596551989073.us-central1.run.app`
- Last deploy: 2026-03-21
- `deploy-cloud.sh` updates Cloud Run env vars but does NOT show
  `DATABASE_URL` for prod
- No `.env.staging` or `.env.production` present in the repo

The most likely production binding is **Cloud SQL Postgres** (because
asyncpg is already a project dependency) but this is NOT verified
from-source. The operator must inspect Cloud Run env or the Secret
Manager binding to confirm.

**Founder action required:** Run from a workstation with `gcloud`
authenticated:
```
gcloud run services describe daena --region=us-central1 \
  --format='value(spec.template.spec.containers[0].env)' | grep DATABASE
```

If `DATABASE_URL` is not present, the prod container is falling back
to the SQLite default `sqlite+aiosqlite:///./daena_dev2.db` — meaning
prod is running on an ephemeral SQLite file inside the Cloud Run
container that is destroyed on every restart. **If this is the case,
production has NEVER had durable state.** This is the worst-case
scenario; the next best is "Postgres is bound but schema state is
drifted from the codebase."

## 3. Is production schema migration safe today?

**No.** Three blocking reasons:

### Blocker A: Stamp drift
`alembic_version` in prod almost certainly points at 002 (the last
migration that landed pre-2026-03-21 deploy), but the running code
has model definitions matching migration 007. `Base.metadata.create_all`
silently creates the missing tables, so the schema works at runtime,
but `alembic downgrade` would corrupt the DB.

### Blocker B: ALTER TABLE columns
`create_all` does NOT alter existing tables. Migrations 004 and 006
add columns to pre-existing tables (`chat_sessions.workstream_id`,
`tenants.dek_wrapped`). The lifespan's hand-rolled ALTER TABLE block
covers some of these but NOT all. So in prod:
- `chat_sessions.workstream_id` may or may not exist (depends on
  whether the lifespan ALTER ran successfully on first 4b deploy)
- `tenants.dek_wrapped` is **definitely missing** in prod (the lifespan
  ALTER block doesn't include it; only Alembic 006 adds it)

### Blocker C: deploy-cloud.sh has no migration step
Re-reading `deploy-cloud.sh`: it builds the image, sets env vars, and
deploys. It never runs alembic. Until that step is added, every prod
deploy is a roll of the dice on schema correctness.

**Verdict:** Don't deploy until A, B, and C are all fixed.

## 4. What breaks if we keep SQLite?

SQLite is fine for **local single-user dev**. It breaks for production
in the following ways:

| Concern | SQLite reality |
|---|---|
| Concurrent writes | Single-writer lock; multi-user load causes "database is locked" errors |
| Cloud Run | Container filesystem is ephemeral; SQLite file is destroyed on every cold start. State is NOT durable |
| Multi-instance scaling | Cannot share a SQLite file across Cloud Run instances |
| Native types | No native UUID, no native JSONB, no array, no enum constraint enforcement |
| Vector search (pgvector) | Not available |
| Audit log integrity | Hash chain still works, but no row-level locking under concurrent writes |
| Row count limits | Practical limit ~10M before lock contention dominates |
| Backups | Need `.backup` SQL command or file copy; harder to integrate with managed backups |
| Permissions | No row-level security |
| Replication | None |

**SQLite stays for local dev.** Every other deploy target needs a
networked DB.

## 5. Should Daena use Postgres, MongoDB, or both?

**Postgres.** MongoDB only if we hit a real document-store need we
can't model in JSONB.

### Why Postgres wins

- Models already use `JSONBCompat` (native JSONB on Postgres) — drop-in
  upgrade
- `asyncpg` already a project dependency (`pyproject.toml` line 20)
- ACID guarantees for `goa_audit_events` hash chain (concurrent
  appends without re-ordering)
- Row-level security for multi-tenant isolation (later)
- pgvector for embeddings (a future RAG store can sit in the same DB
  as relational data — one connection pool, one transaction)
- Cloud SQL Postgres is GCP-managed; matches the existing Cloud Run
  infra
- Migrations via Alembic work identically on Postgres + SQLite

### Why NOT MongoDB

- The current schema (50+ tables, FK constraints, hash chains, JOINs
  for governance audit) is heavily relational
- No piece of Daena's domain currently calls for document-store
  patterns (no large nested unstructured documents, no schema-less
  user-generated content storage at scale)
- Adding Mongo means a second DB to operate, replicate, back up, and
  reason about
- JSONB on Postgres handles the few semi-structured fields (config,
  settings, capabilities) without giving up SQL joins

### When MongoDB might earn its way in

- If we add a feature that generates millions of variable-shape
  documents per tenant per month (e.g. raw scrape archives, web
  crawler dumps)
- If Daena ever ships a tenant-supplied schema product (BYO
  document collection)

Neither exists today. Don't pre-pay the operational cost.

### A note on multiple DBs

For separation of concerns it's tempting to put audit + secrets in a
"different" DB. Resist this in v1: a single Postgres instance with
schemas (`public`, `audit`, `secrets`, `connections`) is enough
isolation for the founder-only/IAAS phase, with materially less
operational burden.

## 6. Recommended production DB architecture for founder-only / IAAS

```
┌────────────────────────────────────────────────────────────┐
│                  Cloud SQL: Postgres 16                    │
│ ─────────────────────────────────────────────────────────  │
│  Region: us-central1 (matches Cloud Run)                   │
│  Tier:   db-g1-small (1 vCPU, 1.7 GB) for founder-only     │
│  Storage: 10 GB SSD, autoresize on                         │
│  Backups: Daily, 7-day retention, point-in-time enabled    │
│  Maintenance window: 03:00 UTC Sun (off-hours)             │
│  HA: Disabled at founder-only stage; flip when paying users│
│                                                            │
│  Extensions:                                               │
│    - pgvector              (RAG embeddings)                │
│    - pg_stat_statements   (query observability)            │
│    - btree_gin            (JSONB indexing)                 │
│                                                            │
│  Schemas:                                                  │
│    public      -- application tables (users, tenants,      │
│                   chat_sessions, connector_instances,      │
│                   connection_v2, etc.)                     │
│    audit       -- goa_audit_events (partitioned by month   │
│                   after 1M rows)                           │
│    secrets     -- secrets (envelope-encrypted)             │
│    rag         -- memory_entries with vector(1536) col     │
│                                                            │
│  Roles:                                                    │
│    daena_app   -- app role; read+write on public, audit,   │
│                   rag; INSERT-only on audit (no UPDATE/DEL)│
│    daena_admin -- migration role; DDL allowed              │
│    daena_ro    -- BI / dashboards; SELECT-only             │
└────────────────────────────────────────────────────────────┘
                           │
                           │ Cloud SQL Auth Proxy or Private IP
                           │
┌────────────────────────────────────────────────────────────┐
│                Cloud Run: daena (us-central1)              │
│ ─────────────────────────────────────────────────────────  │
│  DATABASE_URL  = postgresql+asyncpg://daena_app:***@.../db │
│  DAENA_KEK     = (Secret Manager binding)                  │
│  USE_CONNECTION_REGISTRY_V2 = false  (until soak passes)   │
│  Min/Max instances = 0/2 (scales to zero)                  │
│                                                            │
│  Startup container script:                                 │
│    1. alembic -c migrations/alembic.ini upgrade head       │
│    2. uvicorn app.main:app --host 0.0.0.0 --port $PORT     │
└────────────────────────────────────────────────────────────┘
                           │
                           │
            ┌──────────────┴──────────────┐
            ▼                             ▼
    Cloud Run Secret Manager       Cloud Logging
    (DAENA_KEK + DB password)      (audit log shadow)
```

### Why this shape

- **Single Postgres instance**: enough for founder-only and the
  earliest paying tenants. Postgres on `db-g1-small` is ~$25/month —
  the cheapest tier that supports backups + pgvector.
- **Schemas not separate DBs**: cross-schema JOINs are free and
  transactionally consistent.
- **`audit` schema with INSERT-only role**: append-only by SQL
  permission, not just by code convention. Tampering attempts fail
  at the DB layer.
- **`rag` schema with `vector(1536)`**: pgvector extension. RAG
  similarity search co-located with `chat_messages` so a single SQL
  query can fetch related memory + the conversation it links to.
- **Alembic in container startup**: `deploy-cloud.sh` ships an entry
  point that runs `alembic upgrade head` BEFORE the uvicorn server.
  No more silent stamp drift.
- **Cloud Run scale-to-zero**: keeps founder-only cost near zero when
  idle. Cloud SQL keeps a warm connection pool through the auth
  proxy.

### Cost estimate (founder-only)

| Component | Approx monthly cost |
|---|---|
| Cloud SQL `db-g1-small` Postgres + 10GB | ~$25 |
| Cloud Run 0–2 instances + cold starts | ~$5 |
| Cloud Logging (modest) | ~$2 |
| Secret Manager + KMS | ~$1 |
| **Total** | **~$33** |

Scale-up moments:
- HA switch (failover replica): +$25/month → $58 total
- Bumping to `db-custom-2-3840` (2 vCPU, 3.75 GB): +$45 → ~$78
- Read replica (analytics): +$25 → ~$103

## 7. Steps to migrate safely from SQLite/dev to production Postgres

This is the operator-side rollout sequence. Founder approval required
at each ⛔ step.

### Step 7.1 — Provision Cloud SQL Postgres (one-time)

```bash
# Provision instance
gcloud sql instances create daena-prod \
  --database-version=POSTGRES_16 \
  --region=us-central1 \
  --tier=db-g1-small \
  --storage-size=10 \
  --storage-auto-increase \
  --backup-start-time=03:00 \
  --enable-point-in-time-recovery \
  --root-password=<set-strong-password>

# Create database + user
gcloud sql databases create daena --instance=daena-prod
gcloud sql users create daena_app --instance=daena-prod \
  --password=<set-strong-app-password>

# Enable extensions (run via gcloud sql connect or Cloud SQL Studio)
psql ... -c "CREATE EXTENSION IF NOT EXISTS pgvector;"
psql ... -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"
psql ... -c "CREATE EXTENSION IF NOT EXISTS btree_gin;"

# Create schemas + role permissions
psql ... <<SQL
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS secrets;
CREATE SCHEMA IF NOT EXISTS rag;
GRANT USAGE ON SCHEMA public, audit, secrets, rag TO daena_app;
GRANT INSERT, SELECT ON ALL TABLES IN SCHEMA audit TO daena_app;
REVOKE UPDATE, DELETE ON ALL TABLES IN SCHEMA audit FROM daena_app;
SQL
```

### Step 7.2 — Wire Cloud Run to Postgres (NO migration yet)

Update `deploy-cloud.sh` to bind `DATABASE_URL` from Secret Manager:

```bash
gcloud secrets create daena-database-url \
  --data-file=- <<<"postgresql+asyncpg://daena_app:***@/daena?host=/cloudsql/daena-467315:us-central1:daena-prod"

gcloud run services update daena \
  --update-secrets=DATABASE_URL=daena-database-url:latest \
  --add-cloudsql-instances=daena-467315:us-central1:daena-prod
```

⛔ **Founder approval before applying** — this changes prod's binding.

### Step 7.3 — Add `alembic upgrade head` to container startup

Update `Dockerfile` entrypoint or `deploy-cloud.sh` so the container
runs migrations BEFORE serving:

```bash
#!/bin/sh
set -e
cd /app/backend
alembic -c migrations/alembic.ini upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
```

⛔ **Founder approval** — this is the change that closes Blocker C.

### Step 7.4 — Remove `Base.metadata.create_all` from prod path

Move the call inside a guard:
```python
if settings.app_env != "production":
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

This forces production to fail fast if Alembic migrations didn't run.
Closes Blocker A.

### Step 7.5 — Verify schema state on prod (read-only)

```bash
gcloud sql connect daena-prod --user=daena_admin
\dn          -- list schemas
\dt public.* -- list tables
SELECT version_num FROM alembic_version;
```

Expected: `version_num = '007_connection_v2_registry'` after Step 7.3
runs.

### Step 7.6 — Migrate dev SQLite data to prod Postgres (one-time, optional)

Only if there's data worth migrating. For founder-only at the
beginning, this is N/A — start fresh. If needed later:

```bash
# Dump SQLite tables we care about
sqlite3 backend/daena_dev2.db .dump tenants users > dump.sql
# Translate to Postgres syntax (or use pgloader)
pgloader sqlite:///backend/daena_dev2.db postgresql://...

# OR custom export script that reads via SQLAlchemy + writes via SQLAlchemy
# (avoids the SQLite-to-Postgres dialect mismatch)
```

⛔ **Founder approval** before any data move.

### Step 7.7 — Soak window

After Step 7.3 + 7.4 deploy:
- Watch Cloud Logging for `daena_essentials_ready` (should appear
  within 30s of cold start)
- Run `python backend/scripts/reconcile_connection_v2.py -v` against
  prod (with prod `DATABASE_URL` exported locally) for 7 days
- Verify zero `missing_v2_mirror` drift before flipping
  `USE_CONNECTION_REGISTRY_V2=true`

### Step 7.8 — Flip the V2 flag

```bash
gcloud run services update daena \
  --update-env-vars=USE_CONNECTION_REGISTRY_V2=true
```

⛔ **Founder approval** — this is the final step that activates V2 in
prod.

### Step 7.9 — Vault migration `--apply`

⛔ **Founder approval** — see prior reports. Independent gate from V2
flip; the vault migration moves legacy encrypted creds into the
new `secrets` table.

## 8. How to handle RAG / vector storage

**Use pgvector co-located with relational data.** Don't bring in a
separate vector DB at the founder-only stage.

```sql
CREATE EXTENSION IF NOT EXISTS pgvector;

-- Add to memory_entries (or a new rag.embeddings table)
ALTER TABLE memory_entries ADD COLUMN embedding vector(1536);
CREATE INDEX ix_memory_entries_embedding
  ON memory_entries USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
```

Why pgvector over Pinecone / Weaviate / Qdrant:
- Single connection pool, single transaction model
- Joins between relational + vector queries are SQL, not multi-system
  glue
- Cost: ~$0/month extra (uses existing Postgres). Pinecone starts at
  $70/month; Weaviate Cloud $25/month minimum
- pgvector handles up to ~10M rows comfortably on `db-g1-small`
- Switch to a dedicated vector DB later if recall/latency needs
  outgrow Postgres

When to add a separate vector store:
- Embedding count > 10M per tenant
- p99 latency > 200ms for top-k=10 queries on `db-g1-small`
- Hybrid search (keyword + vector) becomes complex

## 9. How to handle audit logs and secrets

### Audit logs (`goa_audit_events`)

- Schema: `audit.goa_audit_events`
- Role: `daena_app` has INSERT + SELECT only; no UPDATE / DELETE
- Hash chain: per-tenant `prev_hash` → `entry_hash` chain (already
  shipped). The DB-layer permission revoke is belt-and-suspenders for
  the code-layer hash chain
- Partition by month after 1M rows:
  ```sql
  CREATE TABLE audit.goa_audit_events_2026_05 PARTITION OF audit.goa_audit_events
    FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
  ```
- Retention: founder-only stage = forever. Paying tenants stage =
  hot for 12 months, archived to GCS after 12 months (raw JSONL for
  cold queryability)
- Backup: Cloud SQL automated backups + a separate weekly logical
  dump to GCS

### Secrets (`secrets` table)

Already designed (Phase 4a-2):
- Schema: `secrets.secrets`
- Envelope encryption: KEK in Cloud Run Secret Manager → HKDF →
  per-tenant DEK → AES-256-GCM ciphertext
- AAD binding: `class || tenant_id || bound_to`
- KEK boot validation refuses to start if KEK is invalid
- Role: `daena_app` has full SELECT/INSERT/UPDATE; no DELETE without
  founder

The DB permissions reinforce the code-layer guarantees. A compromise
of the app role doesn't allow the attacker to drop the audit chain
or wipe secrets.

## 10. What must be fixed before production deploy

| Blocker | Fix | Status |
|---|---|---|
| Schema state in prod is unknown | Run `alembic current` against prod and compare to expected `007_connection_v2_registry` | ⏳ Founder action (gcloud sql connect) |
| `deploy-cloud.sh` has no migration step | Add `alembic upgrade head` to container entrypoint | ⏳ Section 7.3 |
| `Base.metadata.create_all` in prod path | Guard behind `app_env != production` | ⏳ Section 7.4 |
| `tenants.dek_wrapped` not in prod | Alembic 006 adds it; will run via Step 7.3 | ⏳ Auto via 7.3 |
| Possible SQLite-on-Cloud-Run worst case | Verify `DATABASE_URL` is bound to Cloud SQL | ⏳ Section 2 |
| `env.py` may not import all models | Verify `migrations/env.py` imports `app.models` (Gap 4 from MIGRATION_SYSTEM_GAP_REPORT) | ⏳ One-line check |
| Vault `--apply` not yet run on prod | Founder-approved operator action | ⏳ Section 7.9 |
| `USE_CONNECTION_REGISTRY_V2` not flipped | Founder-approved after 7-day soak | ⏳ Section 7.8 |

**None of these can be done by Claude Code in autonomous mode.** They
all require founder approval + operator-side `gcloud` access.

---

## Recommended position (founder-locked)

1. **SQLite for local dev** — keep it; it's fine and matches the test
   suite via `Base.metadata.create_all`.
2. **PostgreSQL for production** — Cloud SQL Postgres 16, single
   instance with schemas for separation of concerns.
3. **MongoDB stays out** — until a clear document-store requirement
   appears (none today).
4. **pgvector for RAG** — co-located with relational data; add a
   separate vector DB only if pgvector scaling fails.
5. **Production must NOT rely on `Base.metadata.create_all`** — guard
   it behind `app_env != production` and require Alembic to run on
   container startup.

## Next founder actions

1. **Verify `DATABASE_URL` in prod**:
   ```bash
   gcloud run services describe daena --region=us-central1 \
     --format='value(spec.template.spec.containers[0].env[].name,spec.template.spec.containers[0].env[].value)' \
     | grep DATABASE
   ```
2. **Compare prod `alembic current` to expected `007`**.
3. **Decide**: do we provision Cloud SQL Postgres now (Section 7.1) or
   wait until the V2 flag is ready to flip?
4. **If provisioning now**: review Steps 7.1 → 7.4, then run them in
   order with backups taken before each step.

No code changes were made by this report. The implementation steps
are entirely operator-side.

---

**Generated:** 2026-05-01
**Generated by:** Claude Code (Opus 4.7) Phase 7-B
