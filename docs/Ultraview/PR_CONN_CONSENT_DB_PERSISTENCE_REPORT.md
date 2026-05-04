# PR-CONN-CONSENT-DB-PERSISTENCE -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Date:** 2026-05-04
**Sprint:** DAENA-OVERNIGHT-LOCAL-PRODUCTION-SPRINT-6 (PR-5 of 8)

---

## 1. Goal

Sprint-4 + Sprint-5 shipped the Asset Shield consent gate with an
in-memory `ConsentStore` that survives only one FastAPI process.
On a Cloud Run deploy with multiple replicas, a grant minted on
replica A is invisible to replica B. PR-5 introduces a
`consent_grants` table + `DBConsentStore` so grants survive
restarts and multi-instance deploy. The in-memory store remains as
the executor's read path (no behavior change there) but the API
endpoint now writes to BOTH stores so a future PR can flip the
executor over without a coordinated cutover.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| Do not enable writes | YES -- pinned in `test_db_grant_does_not_unlock_phase2_read_only_defense`: PHASE2_ALLOWLIST has zero `read_only=False` entries; consent only flips the gate, not the floor |
| Single-use grants | YES -- `acknowledge` flips `consumed_at`; second call returns None. Pinned in `test_acknowledge_single_use` |
| TTL enforced | YES -- `find_active` filters expired; `acknowledge` raises `SkillConsentExpired`. Pinned in two tests |
| Tenant-bound | YES -- every query filters on `tenant_id` first; cross-tenant lookup returns None. Pinned in `test_grant_in_tenant_a_invisible_to_tenant_b` |
| No PII / token / secret fields | YES -- the row schema has only metadata columns. Pinned in `test_consent_grant_row_has_no_token_shaped_columns` |
| Existing in-memory tests still pass | YES -- 97/97 in scope (Sprint-5 in-memory tests + Sprint-6 PR-5 DB tests) |
| Alembic migration added | YES -- `migrations/versions/011_add_consent_grants.py` (idempotent, mirrors PR-3 of Sprint-5 pattern) |
| Do not deploy | YES -- migration awaits `alembic upgrade head` on the deploy machine |

---

## 3. Surface area

### Backend

#### `backend/app/models/consent_grant.py` (NEW)

* `ConsentGrant` model with TenantMixin + TimestampMixin.
* Columns: `id`, `tenant_id`, `user_id`, `plugin_id`, `skill_id`,
  `category`, `expires_at`, `consumed_at`, `created_at`,
  `updated_at`. Nothing else.
* Composite index `ix_consent_grants_match_lookup` on
  `(tenant_id, plugin_id, skill_id, category)` for the hot lookup.
* Index `ix_consent_grants_expires_at` for future GC sweeps.

#### `backend/app/models/__init__.py`

* Imported + added to `__all__` so Alembic auto-discovers the table.

#### `backend/migrations/versions/011_add_consent_grants.py` (NEW)

* `revision = "011_add_consent_grants"`,
  `down_revision = "010_add_connector_instance_owner_email"`.
* Idempotent `_table_exists` + `_index_exists` guards so a
  partially-applied schema (e.g. dev SQLite via `create_all`) is
  safe to re-run.
* SQLite + Postgres both use plain `CREATE TABLE` -- no batch
  required because there's no ALTER on existing rows.
* Downgrade drops indexes then table (dev rollback only per
  CLAUDE.md hard law #2).

#### `backend/app/services/connection_v2/skill_consent.py`

* New `DBConsentStore` class with the same public contract as the
  in-memory `ConsentStore`:
  * `grant(tenant_id, user_id, plugin_id, skill_id, category, ttl_seconds)`
    -> `SkillConsentGrant`
  * `find_active(tenant_id, plugin_id, skill_id, category)`
    -> `SkillConsentGrant | None`
  * `acknowledge(grant_id, *, tenant_id=None)`
    -> `SkillConsentGrant | None`
  * `clear()` (test helper)
* Tenant-aware `acknowledge` accepts an optional `tenant_id` filter
  so a guessed grant_id from another tenant cannot be consumed.
* TZ-aware comparison normalizes naive SQLite timestamps to UTC.

#### `backend/app/api/v1/skill_consent_api.py`

* `POST /grant` now writes to BOTH stores:
  1. `DBConsentStore.grant` (durable; visible to other replicas
     after migration).
  2. `get_default_store().grant` (in-memory; the executor still
     reads from this on `/skills/execute`).
* The dual-write pattern makes the cutover safe -- a follow-up PR
  can swap the executor's read path to the DB store without any
  coordination with the API.

### Tests

#### `backend/tests/test_consent_db_persistence.py` (NEW, 8 tests)

1. **Grant + find round-trip** (`test_grant_then_find_returns_same_grant`)
2. **Single-use** (`test_acknowledge_single_use`)
3. **Expired filtered from find** (`test_expired_grant_filtered_from_find`)
4. **Expired raises in acknowledge** (`test_acknowledge_expired_raises`)
5. **Tenant isolation** (`test_grant_in_tenant_a_invisible_to_tenant_b`)
6. **Schema has no token-shaped fields** (`test_consent_grant_row_has_no_token_shaped_columns`)
7. **API mint persists to DB** (`test_api_mint_persists_to_db`)
8. **DB grant doesn't unlock Phase 2 floor** (`test_db_grant_does_not_unlock_phase2_read_only_defense`)

---

## 4. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_consent_db_persistence.py -q
8 passed in 1.23s

$ .venv/Scripts/python.exe -m pytest \
    tests/test_consent_db_persistence.py \
    tests/test_skill_consent.py \
    tests/test_skill_consent_api.py \
    tests/test_marketplace_diagnostic.py \
    tests/test_marketplace_coming_soon_classifier.py \
    tests/test_oauth_orphan_reclaim.py \
    tests/test_oauth_account_profile_capture.py \
    tests/test_oauth_accounts_endpoint.py \
    tests/test_plugin_governance_presets_api.py -q
97 passed in 14.41s

$ npx tsc --noEmit
EXIT=0
```

Sprint progression:
* End of PR-4: 252 in scope
* PR-5 adds: 8 new DB-store tests = **260 in scope**

A pre-existing flake exists in
`test_skill_executor_phase2.py::test_execute_endpoint_blocks_non_allowlisted`
when run AFTER any test that commits a tenant with the
`test_tenant_id` UUID (`11111111-...`). The flake originated from
Sprint-5 PR-4's `test_skill_consent_api.py` -- confirmed by
`git stash` regression: the same error reproduces on
`master + 7ed01d0` without PR-5 changes. Out of scope for PR-5;
captured here for the smoke doc.

---

## 5. What did NOT change

* Executor read path: still consults `get_default_store()` (the
  in-memory store). The dual-write pattern keeps the executor
  unchanged so this PR ships zero risk to live executions.
* Phase 2 read_only defense: untouched.
* PHASE2_ALLOWLIST: still zero non-read-only entries.
* No new HTTP endpoint (`/skill-consent/grant` already existed).
* Frontend: no changes (the API contract is identical from the
  caller's POV).

---

## 6. Operator action required for production

1. `alembic upgrade head` on the deploy machine to create the new
   `consent_grants` table.
2. No env var / config change.
3. No restart sequencing -- the dual-write is forward-compatible
   with replicas that haven't seen this PR yet (they continue using
   the in-memory store).

---

## 7. Follow-up PRs

1. **`PR-CONN-CONSENT-EXECUTOR-DB-CUTOVER`** -- flip the executor's
   read path from `get_default_store()` to `DBConsentStore`. Requires
   threading a session through `SkillExecutor`. Defer until the
   table is in production for >= 1 sprint cycle so we can
   compare the dual-write rates and confirm no surprises.
2. **`PR-CONN-CONSENT-EXPIRED-GC`** -- background sweep that
   deletes rows with `expires_at < now() - 24h`. The `find_active`
   filter already ignores them; this is purely housekeeping.
3. **`PR-CONN-CONSENT-AUDIT-LOG-LINK`** -- include the consent
   grant_id in the existing audit row that the executor writes
   when consent is consumed, so the operator can trace any
   write-class action back to the explicit approval.
