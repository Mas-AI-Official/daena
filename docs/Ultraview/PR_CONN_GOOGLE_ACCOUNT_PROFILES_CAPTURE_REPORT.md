# PR-CONN-GOOGLE-ACCOUNT-PROFILES-CAPTURE -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** (to be pinned)
**Date:** 2026-05-03
**Sprint:** DAENA-LOCAL-USABILITY-SPRINT-5 (PR-1 of 6)

---

## 1. Goal

Auto-populate `ConnectorInstance.owner_email` during the OAuth callback so
the executor's `_find_oauth_instance` gate (Sprint-4 PR-3) and the upcoming
account-picker UI (Sprint-5 PR-2) both see real account labels without
ever decrypting the credentials JSONB blob.

Sprint-4 PR-3 added the column + relaxed unique constraint but left the
column NULL on every callback. Sprint-5 PR-1 closes that loop by reading
the provider's userinfo response (already fetched by Session-11
`fetch_account_identity`) and writing the normalized email to the indexed
top-level column.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| Use existing `fetch_account_identity()` | YES -- no new HTTP path; the function pre-existed |
| Store normalized lowercase owner_email | YES -- new `_normalize_owner_email` helper: strip + lowercase + 254-char cap |
| Do not store profile picture or unnecessary PII | YES -- only `email` field is read from userinfo; the Session-11 `fetch_account_identity` already returns just the email/handle string |
| Do not print tokens | YES -- the only thing logged is `account_identity`, which is the email/handle, never the access/refresh token |
| Identity failure does not break OAuth | YES -- swallowed in pre-existing try/except; `owner_email` stays NULL, row still CONNECTED |
| No external sends/writes | YES -- this PR only adds a column write inside the existing transaction |

---

## 3. Surface area

### `backend/app/api/v1/connector_oauth.py`

* New `_normalize_owner_email(identity)` helper -- pure function, defensively
  capped to 254 chars, returns None for falsy/whitespace input
* In `oauth_callback`: after `fetch_account_identity`, normalize the
  identity and pass it as the new `ConnectorInstance.owner_email`
  argument
* The `select(ConnectorInstance)` lookup now matches on
  `owner_email == normalized_owner_email` so two distinct accounts under
  the same `(tenant, connector, user)` triple get separate rows
  (mirrors the Sprint-4 PR-3 unique constraint exactly)

### `backend/tests/test_oauth_account_profile_capture.py` (NEW, 14 tests)

1. **Pure-function `_normalize_owner_email` (5 tests)**:
   * Falsy/blank -> None (parametrized over None / "" / "   " / "\n\t  ")
   * Mixed-case lowercased
   * Surrounding whitespace stripped
   * Over-long input clamped to 254
   * Handle-style identity (no @-sign) still normalized
2. **Callback happy path (1)**: Google userinfo email lands in column
   lowercased
3. **Callback identity failure (1)**: Empty userinfo -> column stays NULL
   but row is CONNECTED
4. **Idempotent re-callback (1)**: Same account re-OAuthed -> same row
   updated, no duplicate
5. **Two distinct accounts (1)**: masoud@ + daena@ -> two distinct rows
   (the founder-mandated invariant)
6. **Orphan-NULL retention (1)**: First callback fails userinfo, second
   callback succeeds with a real email -> orphan NULL row stays, new
   identified row appears, operator reconciles via UI
7. **No token leakage in column (1)**: Even with adversarial userinfo,
   the column never contains access/refresh token material

### Behavior intentionally NOT shipped

* No backfill of NULL owner_email rows when a later callback succeeds.
  We cannot prove identity continuity from the OAuth code alone, so
  the orphan stays for manual reconciliation. Documented in test
  `test_callback_after_identity_failure_creates_separate_row_not_backfill`.
* No production Alembic migration -- that is Sprint-5 PR-3.
* No frontend picker UI -- that is Sprint-5 PR-2.

---

## 4. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_oauth_account_profile_capture.py -q
14 passed in 4.67s

$ .venv/Scripts/python.exe -m pytest \
    tests/test_skill_executor_phase2.py \
    tests/test_oauth_invoker.py \
    tests/test_skill_executor_oauth_wireup.py \
    tests/test_oauth_account_profiles.py \
    tests/test_skill_consent.py \
    tests/test_plugin_governance_presets.py \
    tests/test_oauth_account_profile_capture.py \
    tests/test_oauth_marketplace.py -q
195 passed in 12.16s
```

Test growth Sprint-5 PR-1:
* End of Sprint-4: 162 in scope (per Sprint-4 smoke)
* PR-1 adds: 14 new account-profile-capture tests + 19 oauth_marketplace
  pre-existing tests now in confirmed-passing scope = **195 in scope**

---

## 5. What did NOT change

* No allowlist entry modified
* No executor branch added
* No runtime behavior change for any existing read-only flow
* No new dependencies, no install, no production deploy
* No vault, no V2 flag, no secret read
* The Phase 2 read_only defense + Sprint-4 PR-4 consent gate remain the
  only enforcement layers

---

## 6. Follow-up PRs

1. **`PR-CONN-FRONTEND-ACCOUNT-PROFILE-PICKER` (Sprint-5 PR-2)** -- UI
   that reads `owner_email` and lets the operator pick which account to
   use when running Gmail/Drive skills.
2. **`PR-CONN-GMAIL-DRIVE-PRODUCTION-ALEMBIC` (Sprint-5 PR-3)** --
   Alembic migration so production Postgres deployments pick up the
   column without a `create_all` reset.
3. **`PR-CONN-OAUTH-ORPHAN-RECLAIM-UI`** (future): one-click "delete
   orphan" affordance in the connections page when the operator sees a
   `owner_email=NULL` Google instance.
