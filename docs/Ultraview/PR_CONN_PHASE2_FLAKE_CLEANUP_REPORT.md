# PR-CONN-PHASE2-FLAKE-CLEANUP -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Date:** 2026-05-04
**Sprint:** DAENA-LAPTOP-USABLE-TODAY-SPRINT-7 (PR-6 of 7)

---

## 1. Goal

Clean up the known cross-test flake so future overnight sprints
have a clean signal:

```
FAILED tests/test_skill_executor_phase2.py::test_execute_endpoint_blocks_non_allowlisted
   sqlalchemy.exc.IntegrityError: UNIQUE constraint failed: tenants.id
```

The flake is documented in `docs/Ultraview/DAENA_LOCAL_USABILITY_SPRINT6_SMOKE.md`
section 13 and the Sprint-6 PR-5 report.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| No change to executor behavior | YES -- only the test fixture changed |
| No new entries to PHASE2_ALLOWLIST | YES -- diff touches only `tests/test_skill_executor_phase2.py` and a new pin test |
| No change to the executor's `read_only` defense | YES -- not touched |
| No change to test_tenant_id / test_user_id values | YES -- conftest unchanged |
| Pre-existing other-suite tests continue to pass | YES -- 110/110 in the relevant cluster |

---

## 3. Root cause

`tests/conftest.py:126` defines `test_tenant_id` as a shared fixed
UUID `11111111-1111-1111-1111-111111111111`. The `test_engine` is
session-scoped, so any test that COMMITS a row with this id leaves
the row in the DB for the rest of the suite. Sprint-5 PR-4's
`test_skill_consent_api` does exactly that.

When `test_skill_executor_phase2::seeded_jwt_user` then runs after
that suite, it tries to INSERT a Tenant with the same id. SQLite
raises `IntegrityError: UNIQUE constraint failed: tenants.id`,
the fixture errors out, and the test that depended on the fixture
is recorded as `ERROR` rather than `passed`.

---

## 4. Fix

`tests/test_skill_executor_phase2.py::seeded_jwt_user` now does a
probe-then-insert. Same shape as `test_consent_db_persistence.py`'s
`_seed_user`:

```python
tenant = (
    await db_session.execute(
        select(Tenant).where(Tenant.id == test_tenant_id),
    )
).scalar_one_or_none()
if tenant is None:
    tenant = Tenant(...)
    db_session.add(tenant)
    await db_session.flush()

# Same guard for User.
```

The fixture's contract is unchanged: it returns a `(tenant, user)`
tuple bound to the JWT in `auth_headers`. Tests that depend on it
see exactly the same data as before.

---

## 5. Surface area

### Modified

`backend/tests/test_skill_executor_phase2.py` -- `seeded_jwt_user`
fixture made idempotent.

### Added

`backend/tests/test_phase2_fixture_idempotency.py` -- 1 test that
pins the probe-then-insert shape via source-level inspection. If a
future PR removes the idempotency guard, this test fires loudly
even when the suite happens to be ordered favorably.

---

## 6. Test result

Before fix (reproduced):
```
$ .venv/Scripts/python.exe -m pytest tests/test_skill_consent_api.py tests/test_skill_executor_phase2.py -q
75 passed, 1 error in 6.34s

ERROR tests/test_skill_executor_phase2.py::test_execute_endpoint_blocks_non_allowlisted
  IntegrityError: UNIQUE constraint failed: tenants.id
```

After fix:
```
$ .venv/Scripts/python.exe -m pytest tests/test_skill_consent_api.py tests/test_skill_executor_phase2.py -q
76 passed in 5.79s

$ .venv/Scripts/python.exe -m pytest tests/test_phase2_fixture_idempotency.py tests/test_skill_executor_phase2.py tests/test_skill_consent_api.py -q
77 passed in 6.04s

# Broader sprint-relevant cluster:
$ .venv/Scripts/python.exe -m pytest tests/test_skill_executor_phase2.py tests/test_skill_consent_api.py tests/test_consent_db_persistence.py tests/test_marketplace_diagnostic.py tests/test_oauth_orphan_reclaim.py -q
110 passed in 9.56s
```

**Sprint progression:** PR-5 ended at 316 in scope.
PR-6 adds 1 idempotency-pin test = **317 in scope**, plus the
previously-flaky test now reliably passes whatever the suite order.

---

## 7. What did NOT change

* `PHASE2_ALLOWLIST` -- unchanged.
* Executor's `read_only` defense -- unchanged (Sprint-6 PR-5 floor
  intact).
* `test_tenant_id` / `test_user_id` fixture values -- unchanged.
* Any other test fixture -- only `seeded_jwt_user` was touched.
* Phase 3 writes -- still impossible.

---

## 8. Follow-up PRs

1. **`PR-CONN-CONFTEST-IDEMPOTENT-SEED-HELPER`** -- the same
   probe-then-insert pattern is repeated in `test_consent_db_persistence`
   and now `test_skill_executor_phase2`. A shared helper in conftest
   would DRY this. Defer until a third call site appears.
2. **`PR-CONN-PER-TEST-TRANSACTION-ROLLBACK`** -- the deeper fix is to
   wrap each test in a savepoint that rolls back at teardown so
   committed rows don't leak across tests at all. That's a bigger
   change that would also accelerate the suite. Defer until the
   suite size makes it worth the migration.
