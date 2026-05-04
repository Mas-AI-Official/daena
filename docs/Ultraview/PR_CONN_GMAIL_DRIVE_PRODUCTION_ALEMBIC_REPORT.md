# PR-CONN-GMAIL-DRIVE-PRODUCTION-ALEMBIC -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** (to be pinned)
**Date:** 2026-05-03
**Sprint:** DAENA-LOCAL-USABILITY-SPRINT-5 (PR-3 of 6)

---

## 1. Goal

Add the missing Alembic migration for the `connector_instances`
schema changes Sprint-4 PR-3 + Sprint-5 PR-1 introduced. Without
this migration:

* Production Postgres deploys would 500 the moment Daena writes
  `owner_email` (column does not exist in PG).
* Two Google accounts under the same operator would still hit the
  ORIGINAL `(tenant, connector, user)` UniqueViolation (constraint
  was relaxed only in the model, not in the live PG schema).

This PR lands migration `010` so a Postgres deploy can `alembic
upgrade head` and reach parity with what `create_all` already gave
the dev SQLite database.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| Do not deploy | YES -- migration is checked into the chain; production application is operator-driven |
| Migration only | YES -- no model / runtime code touched |
| SQLite/dev compatibility | YES -- `op.batch_alter_table` wraps SQLite path; six dedicated tests run against in-memory SQLite |
| Existing null owner_email rows stay valid | YES -- new column is `nullable=True` with no UPDATE forced; pre-PR-1 rows survive |
| Add migration test | YES -- `tests/test_migration_010_owner_email.py` (6 tests pinning revision wiring + upgrade behavior + idempotency + downgrade) |

---

## 3. Surface area

### `backend/migrations/versions/010_add_connector_instance_owner_email.py` (NEW)

* Revision: `010_add_connector_instance_owner_email`
* down_revision: `009_add_workstream_spine_fields`
* Operations performed (idempotent, dialect-aware):
  1. ADD COLUMN `owner_email VARCHAR(254) NULL`
  2. CREATE INDEX `ix_connector_instances_owner_email` on `(owner_email)`
  3. DROP CONSTRAINT (if present) `uq_connector_instances_tenant_connector_user`
     OR `connector_instances_tenant_id_connector_id_user_id_key` -- both
     candidate names tried since the original constraint may be
     SQLAlchemy-named or Postgres-auto-named depending on how it landed.
  4. ADD CONSTRAINT `uq_connector_instances_tenant_connector_user_email`
     on `(tenant_id, connector_id, user_id, owner_email)`
* SQLite branch consolidates ALL ops into a single `batch_alter_table`
  to avoid the inspector-cache trap (an intermediate `op.create_index`
  outside the batch sees stale schema and errors with "no such column").
* Downgrade reverses index + column + constraint inside a SINGLE batch
  for SQLite (index drop must happen before column drop -- otherwise
  the table-recreate copies an index referencing the dropped column).

### `backend/tests/test_migration_010_owner_email.py` (NEW, 6 tests)

1. **Revision chain (1)**: `010` follows `009` (alembic upgrade head reaches it).
2. **Upgrade against pre-Sprint-4-PR-3 schema (1)**:
   * column appears, indexed, relaxed constraint takes effect.
3. **Multi-account permitted (1)**: two rows differing only by
   `owner_email` (masoud@... + daena@...) coexist after upgrade.
4. **Duplicate quad still rejected (1)**: identical
   `(tenant, connector, user, owner_email)` raises
   `IntegrityError` -- relaxing one column did NOT remove uniqueness.
5. **Idempotency (1)**: second `upgrade()` against the upgraded
   schema is a no-op.
6. **Downgrade callable (1)**: dev rollback path runs without raising
   and removes the new column.

Tests use a freshly-spun in-memory SQLite engine PER TEST instead of
the session-scoped `test_engine` fixture so the migration's view is
not polluted by `create_all`'s view of the model.

---

## 4. What did NOT change

* No model code modified (the model already declared the relaxed
  state from Sprint-4 PR-3 + Sprint-5 PR-1).
* No runtime executor branch added.
* No new dependencies, no install, no production deploy.
* No vault, no V2 flag, no secret read.

---

## 5. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_migration_010_owner_email.py -q
6 passed in 0.18s

$ .venv/Scripts/python.exe -m pytest \
    tests/test_skill_executor_phase2.py tests/test_oauth_invoker.py \
    tests/test_skill_executor_oauth_wireup.py \
    tests/test_oauth_account_profiles.py tests/test_skill_consent.py \
    tests/test_plugin_governance_presets.py \
    tests/test_oauth_account_profile_capture.py \
    tests/test_oauth_marketplace.py \
    tests/test_oauth_accounts_endpoint.py \
    tests/test_migration_010_owner_email.py -q
207 passed in 20.33s
```

Test growth Sprint-5 PR-3:
* End of PR-2: 201 in scope
* PR-3 adds: 6 new migration tests = **207 in scope**

---

## 6. Production deploy notes (for the operator -- NOT executed by this PR)

When Daena ships to Cloud Run / production Postgres:

1. CI runs `alembic upgrade head` as part of the deploy step.
2. Migration 010 picks up automatically since 009 -> 010 is wired in.
3. Pre-existing rows survive (column nullable, no backfill).
4. Pre-existing UniqueConstraint (whatever Postgres named it) gets
   dropped via the candidate-name probe.
5. Two-account flows immediately work post-migration.

If migration 010 fails partway (e.g. CI environment has an
unexpected constraint name), the operator must:
1. Inspect via `\d connector_instances` in psql.
2. Add the constraint name to `_OLD_CONSTRAINT_CANDIDATES` in 010.
3. Rerun.

---

## 7. Follow-up PRs

1. **`PR-CONN-CONSENT-API-AND-UI` (Sprint-5 PR-4)** -- expose the
   Asset Shield consent foundation through a safe API + modal.
2. **Production smoke after deploy**: capture a `\d
   connector_instances` snapshot before AND after the migration runs
   in a staging environment to confirm the constraint swap took.
