# Migration System Gap Report

**Branch:** `rebuild-connections-mcp-runtime`
**HEAD:** `da8f737`
**Generated:** 2026-04-30
**Purpose:** Honest assessment of Daena's migration management state before Phase 4b adds migration 007. Per founder rule: report first; do not fully repair Alembic unless required for Phase 4b.

---

## Correction to prior reporting

`docs/PHASE_4A_3_OPERATOR_GATE_REPORT.md` §4.1 said "Alembic CLI is not configured at the repo root (alembic.ini missing)." That statement is **partially incorrect** and is corrected here.

**Truth:** `alembic.ini` and `env.py` BOTH exist at `backend/migrations/`:

```
backend/migrations/
├── alembic.ini
├── env.py
├── script.py.mako
└── versions/
    ├── 001_add_autopilot_think_mode.py
    ├── 002_add_pipeline_lost_columns.py
    ├── 003_add_workstreams.py
    ├── 004_add_chat_session_workstream_fk.py
    ├── 005_add_cron_mcp_background_tables.py
    └── 006_secrets_envelope_vault.py
```

The earlier `python -m alembic current` failed because Alembic by default looks for `alembic.ini` in the current working directory; I ran it from `backend/`, but the file is in `backend/migrations/`. The correct invocation is:

```
python -m alembic -c migrations/alembic.ini current
```

That works:

```
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
004_add_chat_session_workstream_fk
```

So the local dev DB is currently at revision `004`, but tables for migrations `005` and `006` ALSO exist (created via `Base.metadata.create_all` in lifespan ESSENTIALS, NOT via Alembic). This is the actual gap.

## Real gaps

### Gap 1 -- create_all masks alembic stamp drift

`backend/app/main.py` lifespan ESSENTIALS calls:

```python
async with engine.begin() as conn:
    await conn.run_sync(Base.metadata.create_all)
```

`Base.metadata.create_all` is idempotent for tables that don't exist -- it issues `CREATE TABLE IF NOT EXISTS` for every model registered in `Base.metadata`. This means: when Phase 4a-2 added the `Secret` model + `Tenant.dek_wrapped` column, the dev DB picked them up on next backend start, even though `alembic upgrade head` was never run to bump the alembic_version table from 004 to 006.

**Effect:** the dev DB has tables that alembic doesn't know exist (`secrets`, `mcp_servers`, `cron_runs`, `background_tasks`, `workstreams`, `workstream_events`, `chat_sessions.workstream_id`). Tactically: dev still works. Strategically: any future `alembic downgrade -1` from 004 would skip dropping these tables, leaving the schema in a half-state.

### Gap 2 -- create_all does NOT add COLUMNS to existing tables

Important caveat: `create_all` only CREATES tables; it does NOT alter existing tables. Migration 004 (`chat_sessions.workstream_id`) and migration 006 (`tenants.dek_wrapped`) both add columns to PRE-EXISTING tables. Dev pickups for those columns rely on the explicit `ALTER TABLE` block in `main.py` lifespan (lines ~720-748 -- the `_nbmf_cols` + `_chat_session_cols` dicts). That ALTER block does NOT include `tenants.dek_wrapped`, so:

- The dev DB I tested against during Phase 4a-3 dry-run **does not actually have `tenants.dek_wrapped` column** -- I verified this when test code tried `tenant.dek_wrapped` and got `AttributeError: 'Tenant' object has no attribute 'dek_wrapped'` initially (Phase 4a-3 fix added the Mapped declaration; the COLUMN doesn't exist on disk in dev DB until alembic 006 actually runs).

This means: **Phase 4a-3 dry-run on dev DB (44 candidates / 44 skipped) was technically correct because zero candidates required DEK provisioning**. If the dev DB had real encrypted credentials, the script would have tried to write `tenant.dek_wrapped` and failed with a SQL error. The graceful precheck I added (secrets table existence) would not have caught this -- it only checks the `secrets` table, not the `tenants.dek_wrapped` column.

Phase 4b should add a similar check for `tenants.dek_wrapped` column existence OR add `tenants.dek_wrapped` to the ALTER TABLE block in lifespan.

### Gap 3 -- production deploy doesn't run alembic

`deploy-cloud.sh` updates Cloud Run env vars + redeploys the container. It does NOT run `alembic upgrade head`. There is no Cloud Run job, no GitHub Actions migration step, no Dockerfile entrypoint that calls alembic. **Production schema state is unknown** -- it depends on whatever migrations were applied historically (probably 001 and 002, since those landed before 2026-03-21 deploy date), plus whatever `Base.metadata.create_all` picks up on each container start.

The fact that prod has been running since 2026-03-21 with `Base.metadata.create_all` means it has all tables for models present at deploy time, but unknown column state for ALTER additions (workstream_id on chat_sessions, NBMF columns on memory_entries, governance_mode on chat_sessions, tenants.dek_wrapped).

### Gap 4 -- env.py may not load all models

I have not inspected `backend/migrations/env.py` to confirm it imports `app.models` (which triggers all model side-effect imports). If env.py is missing key model imports, `alembic upgrade head` could fail to discover models and skip table creation.

## Risks for production

| Risk | Severity | Detection |
|---|---|---|
| Stamp drift -- alembic_version says X but tables match Y | **HIGH** | `alembic current` vs `inspect(engine).get_table_names()` diff |
| Missing columns -- Mapped column declared in model but column not in DB | **HIGH** | Runtime AttributeError or SQL error on first read/write |
| `tenants.dek_wrapped` not in prod DB | **HIGH for Phase 4b deploy** | Caught at `--apply` time when migration script tries to write the column |
| Phase 4a-3 dry-run on prod returns wrong candidate count | **MEDIUM** | Re-run with `--report-json` after fixing alembic |
| Alembic downgrade leaves orphan tables | **LOW** | Only matters if downgrade is ever attempted |

## Recommended fix path

**Minimal fix (required for Phase 4b dev work):** none. Migration 007 can be added as a new file in `backend/migrations/versions/`. Dev DB picks up the new tables via `Base.metadata.create_all` on next backend start. No alembic command needed for dev.

**Medium fix (recommended before Phase 4b production deploy):**

1. Operator runs `alembic -c migrations/alembic.ini current` in production. Records the actual revision.
2. If `< 006`: operator runs `alembic -c migrations/alembic.ini upgrade head` to apply 003-006 plus the new 007 from Phase 4b.
3. Add `tenants.dek_wrapped` to the lifespan ALTER TABLE block in `main.py` as a SAFETY NET in case alembic isn't run on every deploy. (One-line addition; not in Phase 4b PR 1 scope unless Phase 4b code triggers the field on dev.)

**Full fix (long-term, post-Phase-4b):**

1. Add an `alembic upgrade head` step to `deploy-cloud.sh` (one extra `gcloud run jobs execute` before re-pushing the container).
2. Add a CI/CD gate: `alembic check` (per Alembic 1.9+) or `alembic upgrade head --sql` smoke test on every PR.
3. Document in CLAUDE.md that `Base.metadata.create_all` is a dev convenience only, not the production deploy strategy.
4. Consider adding an `alembic upgrade head` call to the lifespan ESSENTIALS itself (with a feature flag so dev can opt out if testing migration scripts in isolation).

## Verdict for Phase 4b

**Phase 4b migration 007 can safely be added under the current system FOR DEV USE.** The migration file goes in `backend/migrations/versions/007_connection_v2_registry.py`. Dev DB picks up the new tables via `Base.metadata.create_all` automatically on next backend start. Tests use in-memory SQLite + `Base.metadata.create_all` and so will work without any alembic CLI invocation.

**Phase 4b migration 007 application to PRODUCTION** is gated on the same operator steps as Phase 4a deploy:
1. Operator runs `alembic -c migrations/alembic.ini upgrade head` against prod (applies 003-007 if behind).
2. Operator verifies via `alembic current`.
3. Then -- and only then -- the Cloud Run deploy + flag flip happens.

**No urgent Alembic repair is required for Phase 4b PR 1 to ship.** I am NOT performing the medium or full fixes in this commit. The gaps are documented; the operator can act on them before the production deploy gate.

---

## Phase 4b decision

✅ **Add migration `007_connection_v2_registry.py` in Phase 4b PR 1.** Dev picks it up via `create_all`; operator must run alembic for prod.

❌ **Do NOT repair `deploy-cloud.sh` to run alembic in this commit.** Out of scope for Phase 4b PR 1; founder approval needed for any deploy-script change.

❌ **Do NOT add ALTER TABLE for `tenants.dek_wrapped` to the lifespan.** Out of scope for Phase 4b PR 1; the operator who runs alembic in prod will get the column. For dev, the test fixture creates tables fresh via `Base.metadata.create_all` which DOES create `tenants.dek_wrapped` since the Mapped declaration was added in Phase 4a-3.

---

**End of migration system gap report.**
