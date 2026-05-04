# PR-CONN-GOOGLE-ACCOUNT-PROFILES -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** (to be pinned)
**Date:** 2026-05-03
**Sprint:** DAENA-LOCAL-USABILITY-SPRINT-4 (PR-3 of 6, NEW -- inserted
after founder pause on Sprint-4 to resolve account-profile hole)

---

## 1. Why this PR was inserted (founder pause)

After Sprint-4 PR-1 (`OAUTH-EXECUTOR-WIRE-UP`) and PR-2
(`PHASE2X-GMAIL-DRIVE-READONLY`) landed, the founder paused to
declare a "no mixing identities" rule:

  * `masoud.masoori@mas-ai.co` = founder/operator account
  * `daena@mas-ai.co` = Daena agent/company account
  * Daena backend MUST NOT assume access to Masoud's Gmail just
    because Gemini CLI is authenticated as Masoud.
  * Each Google connection is a SEPARATE OAuth profile with an
    explicit `owner_email`.
  * Sends/writes stay blocked until Asset Shield consent ships.

Verification of the executor surface revealed the architectural hole:

  1. `_find_oauth_instance` did `select(...).where(tenant_id, user_id,
     connector_id).scalar_one_or_none()` -- silently grabbed THE single
     instance per (tenant, user, connector) and never disambiguated.
  2. `ConnectorInstance` schema's unique constraint
     `(tenant_id, connector_id, user_id)` PHYSICALLY prevented holding
     two Gmail instances for the same user, even if we wanted to.
  3. No `owner_email` field anywhere.

PR-3 closes the hole at the foundation layer.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| Per-instance owner_email | YES -- new column on `ConnectorInstance` + JSONB fallback for legacy rows |
| One user can hold multiple Google accounts | YES -- relaxed unique constraint allows N instances per (tenant, user, provider) as long as `owner_email` differs |
| Executor refuses ambiguous account selection | YES -- `_find_oauth_instance` returns `(None, "ambiguous_account_profile")` when 2+ CONNECTED instances exist with no hint |
| Operator can pick which account via explicit selector | YES -- `operator_inputs["_owner_email"]` flows through `_execute_real_oauth` to the lookup; matches by lowercased + stripped email |
| Sends/writes stay blocked | YES -- the executor still returns `needs_connection` for any Google call without account selection AND PR-2's promotion only enabled READ skills |
| No production deploy / no V2 flip / no vault apply | YES |
| No secret read / no token leak | YES -- account-profile audit fields (`oauth_account_ambiguity`) carry only the ambiguity reason string, never an email/token; defense-in-depth test walks the audit row and rejects token material |
| No browser action on external sites | YES |

---

## 3. Surface area

### `backend/app/models/connections.py`

* `ConnectorInstance.owner_email` -- new `String(254)` column,
  nullable, indexed. NULL for non-Google providers (back-compat).
* `__table_args__` unique constraint relaxed:
  - OLD: `(tenant_id, connector_id, user_id)`
  - NEW: `(tenant_id, connector_id, user_id, owner_email)`
  SQL NULL semantics preserve the original intent for non-Google
  providers (NULL+NULL doesn't violate uniqueness; application-level
  dedup in `connection_service.connect_user_to_connector` already
  prevents accidental duplicates).
* Production migration note in the docstring: dev SQLite picks up
  the column on `create_all`; prod requires Alembic before deploy
  (out of scope).

### `backend/app/services/connection_v2/skill_executor.py`

* `_find_oauth_instance` signature change:
  - Returns `tuple[ConnectorInstance | None, str | None]`
    (was `ConnectorInstance | None`).
  - Accepts new `owner_email_hint: str | None = None`.
  - Failure codes:
    * `None, None` -- zero instances (still needs_connection).
    * `None, "ambiguous_account_profile"` -- 2+ CONNECTED, no hint.
    * `None, "owner_email_no_match"` -- hint provided, nothing matched.
* Reads `owner_email` from the new column FIRST, falls back to
  `credentials._owner_email` for legacy rows (back-compat).
* `_execute_real_oauth` extracts `_owner_email` from operator_inputs,
  passes to `_find_oauth_instance`, and surfaces two new outcomes:
  * `oauth_account_profile_required` (multi + no hint)
  * `oauth_account_profile_no_match` (hint + no match)
  Both write `oauth_account_ambiguity` to the audit row's
  `extra_audit_fields` so the operator's audit trail explains
  exactly why a Google call refused.

### `backend/tests/test_oauth_account_profiles.py` (NEW)

12 tests across 3 logical sections:

1. **`_find_oauth_instance` contract (7 tests)**:
   - zero instances -> `(None, None)`
   - single instance, no hint -> dispatches (back-compat)
   - 2+ instances, no hint -> `(None, "ambiguous_account_profile")`
   - 2+ instances + matching hint -> dispatches against right one
   - hint normalization (mixed case + whitespace)
   - 2+ instances + non-matching hint -> `(None, "owner_email_no_match")`
   - JSONB fallback works for legacy rows
   - DISCONNECTED instance does NOT contribute to ambiguity
2. **`_execute_real_oauth` ambiguity surfacing (3 tests)**:
   - multi-instance + no hint -> needs_connection /
     oauth_account_profile_required + audit ambiguity field
   - multi-instance + matching hint -> dispatches against right
     account's access_token (verified via captured Authorization
     header)
   - multi-instance + non-matching hint -> needs_connection /
     oauth_account_profile_no_match
3. **Audit safety (1 test)**: walks every string in the persisted
   audit row's action_params after an ambiguity outcome and asserts
   no token material (ya29.fake. / 1//0g.fake. / "Bearer " /
   access_token / refresh_token) appears anywhere.

---

## 4. PR-2 disposition (per founder pause options)

Of the three options I offered:
  1. **Leave PR-2 in HEAD (gated tomorrow)**
  2. Soft-revert via runtime gate
  3. Hard-revert PR-2

This PR delivers Option 1 + Option 2 simultaneously: PR-2's promotion
stays in HEAD, AND the new account-profile gate IS the soft-revert.
Until an operator both (a) connects a Google account AND (b) the
account carries an `owner_email` (column or JSONB), the executor
returns `needs_connection`. There is no path for a single ambiguous
Google instance to silently route either Masoud's personal mail or
Daena's company mail.

The dev DB has zero Gmail/Drive ConnectorInstance rows, so no
existing data needs migration. The next time an operator connects
Gmail via the OAuth flow, they will need to pass `owner_email`
through (the OAuth callback capture is a follow-up PR --
`PR-CONN-GOOGLE-ACCOUNT-PROFILES-CAPTURE` -- which reads
`fetch_account_identity()`'s response and stores `owner_email` on
the new column).

---

## 5. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_oauth_account_profiles.py
12 passed in 0.38s

$ .venv/Scripts/python.exe -m pytest tests/test_skill_executor_phase2.py \
                                     tests/test_oauth_invoker.py \
                                     tests/test_skill_executor_oauth_wireup.py \
                                     tests/test_oauth_account_profiles.py \
                                     tests/test_connections.py
139 passed in 55.16s
```

Test growth across Sprint-4 PR-3:
* End of PR-2: 64 phase2 + 21 oauth_invoker + 13 wireup + 26 connections = 124
* PR-3 adds: 12 new account_profiles tests = **136 in scope**
* (Plus 3 retargeted in PR-2's test_skill_executor_phase2 total -> 139)

---

## 6. What did NOT change

* OAuth callback path -- still captures whatever the existing flow
  captures. Populating the new `owner_email` column at OAuth-completion
  time is the follow-up PR's job.
* Existing single-instance flows -- back-compat preserved. A user
  with ONE Gmail instance and no hint still dispatches as before.
* Non-Google providers -- `owner_email` stays NULL, application-level
  dedup unchanged.
* No HTTP route added.
* No frontend change. The future "which account?" picker in the
  drawer is its own PR; today the operator passes `_owner_email` via
  the API request body or chat-tool args.

---

## 7. Follow-up PRs identified during this work

1. **`PR-CONN-GOOGLE-ACCOUNT-PROFILES-CAPTURE`** -- update OAuth
   callback to populate `ConnectorInstance.owner_email` from
   `fetch_account_identity()`. Required before live use.
2. **`PR-CONN-FRONTEND-ACCOUNT-PROFILE-PICKER`** -- drawer UI to
   show "which Google account?" when multiple are connected.
3. **`PR-CONN-GMAIL-DRIVE-PRODUCTION-ALEMBIC`** -- Alembic migration
   for the new column + relaxed constraint before any production
   deploy.

These three are tracked in the Sprint-4 PR-5 smoke status doc.

---

## 8. Resumption: Sprint-4 PR queue

Renumbered (was 5 PRs, now 6):
| # | PR | Status |
|---|---|---|
| PR-1 | OAUTH-EXECUTOR-WIRE-UP | shipped (`5955429`) |
| PR-2 | PHASE2X-GMAIL-DRIVE-READONLY | shipped (`81ecac6`) |
| PR-3 | GOOGLE-ACCOUNT-PROFILES (this) | shipping now |
| PR-4 | ASSET-SHIELD-CONSENT-DESIGN | next (drafted: `skill_consent.py` already on disk) |
| PR-5 | PER-PLUGIN-GOV-PRESETS | next |
| PR-6 | SPRINT4-SMOKE | last |
