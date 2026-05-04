# PR-CONN-FRONTEND-ACCOUNT-PROFILE-PICKER -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** (to be pinned)
**Date:** 2026-05-03
**Sprint:** DAENA-LOCAL-USABILITY-SPRINT-5 (PR-2 of 6)

---

## 1. Goal

Surface the operator's connected Google accounts in the
`SkillExecuteModal` so they can explicitly pick which profile
(masoud.masoori@... vs daena@...) the Gmail / Drive skills should run
as. The picker propagates the selection as `_owner_email` in
`operator_inputs` -- the executor's Sprint-4 PR-3 account-profile gate
already consumes that field.

Without this PR, an operator with both accounts connected has no UI
path to disambiguate them; the executor would refuse with
`oauth_account_profile_required` and the operator would have to
hand-edit JSON in DevTools.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| Show owner_email values only | YES -- response shape pinned to `{instance_id, owner_email, status}`; no token / credentials field is ever serialized |
| If one account exists, default to it | YES -- single CONNECTED row auto-selects; Run button enables once required inputs are filled |
| If multiple accounts exist, require explicit selection | YES -- Run button disabled with explanatory tooltip until operator picks a radio |
| Pass _owner_email into operator_inputs | YES -- `handleRun` adds it before POST; only when the plugin is OAuth-backed AND a selection exists |
| Do not expose tokens | YES -- new `/oauth/accounts` endpoint asserted token-leak-free via canary substring test |
| Do not auto-send / execute without confirmation | YES -- Run button still gated on Sprint-2 `allInputsSupplied` + new `accountSatisfied` |

---

## 3. Surface area

### Backend: `backend/app/api/v1/connector_oauth.py`

* New endpoint:
  `GET /api/v1/connectors/oauth/accounts?provider=<gmail|google-drive|...>`
* Auth-required (CurrentUser).
* Returns `{data: {provider, accounts: [{instance_id, owner_email, status}]}}`.
* Tenant-isolated (filters on `user.tenant_id` AND `user.id`).
* Returns empty list (not error) when the provider's Connector catalog
  row isn't installed -- honest "no accounts" answer.

### Frontend: `frontend/src/pages/connections/SkillExecuteModal.tsx`

* New `PLUGIN_TO_OAUTH_PROVIDER` static map (5 OAuth-backed plugins:
  app-gmail, app-google-drive, app-google-calendar, app-slack,
  app-github). Plugins NOT in this map skip the picker entirely;
  modal renders identically to before.
* `useEffect` fetches `/oauth/accounts?provider=...` on
  (plugin, skill) change for OAuth-backed plugins only.
* Auto-select rule: 1 account -> auto, N accounts -> radio picker, 0
  accounts -> amber warning + Run button stays disabled.
* New `accountSatisfied` + `canRun` derived state -- Run button now
  gates on (`allInputsSupplied` AND picker satisfied AND not loading).
* Tooltip on Run button explains EXACTLY what's missing (inputs vs
  account vs no-connect) so the operator never wonders why it's grey.
* `handleRun` adds `_owner_email` to `operator_inputs` only when the
  plugin is OAuth-backed AND the operator has selected an account.

### Backend tests: `backend/tests/test_oauth_accounts_endpoint.py` (NEW, 6 tests)

1. **Auth required (1)**: anonymous request returns 401/403, never
   200 with data.
2. **Unsupported provider (1)**: `provider=mythos-invented` returns
   400 with explicit `unsupported_provider` code.
3. **Catalog missing (1)**: known provider but no Connector row ->
   200 with empty accounts list (honest, not error).
4. **All statuses returned (1)**: backend returns CONNECTED +
   DISCONNECTED rows; frontend filter is the only place status is
   narrowed.
5. **Token canary leak defense (1)**: encrypted credentials JSONB
   contains LEAK-CANARY substrings for `access_token` /
   `refresh_token` / `Bearer`; response payload is asserted to NEVER
   contain any of them. Structural pin: response keys are exactly
   `{instance_id, owner_email, status}`.
6. **Tenant isolation (1)**: a second tenant's Gmail account NEVER
   appears in the caller tenant's response.

### Frontend type-check

`npx tsc --noEmit`: clean (exit 0).

---

## 4. UX choices that aren't obvious from the diff

* **DISCONNECTED rows excluded in the picker.** The backend returns
  all statuses so future surfaces can show "Disconnected (reauth)";
  this PR's modal is the first consumer and only shows CONNECTED to
  avoid operator confusion ("why is grayed-out account in my picker?").
* **`(account profile unknown)` label.** When `owner_email` is NULL
  (orphan from PR-1's failed-userinfo retention semantic), the picker
  still renders the option so the operator can pick it -- the executor
  will then resolve via the credentials-JSONB `_owner_email` fallback
  added in Sprint-4 PR-3 for back-compat.
* **No picker for non-OAuth plugins.** The modal stays a one-section
  flow for `mcp-*` plugins so a postgres-style call doesn't get a
  meaningless "Run as account" question.

---

## 5. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_oauth_accounts_endpoint.py -q
6 passed in 4.97s

$ .venv/Scripts/python.exe -m pytest \
    tests/test_skill_executor_phase2.py \
    tests/test_oauth_invoker.py \
    tests/test_skill_executor_oauth_wireup.py \
    tests/test_oauth_account_profiles.py \
    tests/test_skill_consent.py \
    tests/test_plugin_governance_presets.py \
    tests/test_oauth_account_profile_capture.py \
    tests/test_oauth_marketplace.py \
    tests/test_oauth_accounts_endpoint.py -q
201 passed in 17.53s

$ npx tsc --noEmit
EXIT=0
```

Test growth Sprint-5 PR-2:
* End of PR-1: 195 in scope
* PR-2 adds: 6 new accounts-endpoint tests = **201 in scope**

---

## 6. What did NOT change

* No allowlist entry modified.
* No executor enforcement change.
* No HTML-form-based OAuth flow opened.
* No write skill enabled.
* The OAuth invoker / consent gate / governance presets are unchanged.
* Phase 2 read_only defense remains the hard wall on writes.

---

## 7. Follow-up PRs

1. **`PR-CONN-GMAIL-DRIVE-PRODUCTION-ALEMBIC` (Sprint-5 PR-3)** --
   production migration so the column survives a non-`create_all`
   deploy.
2. **`PR-CONN-OAUTH-ORPHAN-RECLAIM-UI`** (future): inline "delete
   orphan" affordance in the picker when an instance has
   `owner_email=NULL`.
3. **`PR-CONN-PICKER-STATUS-BADGES`** (future): expose
   DISCONNECTED / NEEDS_REAUTH rows in the picker with a "reconnect"
   shortcut so operators don't have to leave the modal.
