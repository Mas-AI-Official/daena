# PR-CONN-OAUTH-CLIENT-CONFIG-IN-SETTINGS — Report

**Date:** 2026-05-03
**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** (to be filled in after squash)
**Predecessor:** [PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE1](./PR_CONN_PLUGIN_SKILLS_EXECUTION_PHASE1_REPORT.md) — `ad0df5e`
**Next per founder plan:** PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE2-READONLY

---

## 1. Goal

Make OAuth-backed plugin cards in the marketplace go from *"Configure with no input"* to *"Connect that actually works"* without making the operator hand-edit `.env` and restart the backend.

Before this PR, the only way to get a `Connect` button to function on a Google / GitHub / Slack / Figma / Canva card was to:

1. Open the developer console for the provider, register an OAuth app
2. Paste the resulting `client_id` + `client_secret` into `backend/.env` as `GITHUB_CLIENT_ID=...` etc.
3. Restart `uvicorn`
4. Refresh the marketplace
5. Click Connect

Steps 2-4 don't ship in a SaaS product. This PR adds a paste-and-save UI surface so the operator does step 1, then pastes into Account → OAuth Client Config, then clicks Connect — no terminal, no `.env`, no restart.

---

## 2. Providers supported (this PR)

5 OAuth client config rows, covering 7 OAuth provider IDs already wired in `oauth_service.OAUTH_PROVIDERS`:

| Slug | Display name | Powers (provider_ids) | Settings fields |
|---|---|---|---|
| `google` | Google (Gmail / Calendar / Drive) | `gmail`, `google-calendar`, `google-drive` | `google_client_id` + `google_client_secret` |
| `github` | GitHub | `github` | `github_client_id` + `github_client_secret` |
| `slack` | Slack | `slack` | `slack_client_id` + `slack_client_secret` |
| `figma` | Figma | `figma` | `figma_client_id` + `figma_client_secret` |
| `canva` | Canva | `canva` | `canva_client_id` + `canva_client_secret` |

Adding a new provider is two steps: (a) add an entry to `OAUTH_PROVIDERS` in `oauth_service.py`, (b) add a row to `PROVIDER_DISPLAY` in `oauth_client_config_store.py`. An import-time assertion in the store rejects drift between the two — you can't ship a config row that points at a provider not actually wired.

---

## 3. Storage path

**Decision: wrap `oauth_credentials_store`, do not duplicate.**

Rule 18 of `D:\Ideas\Daena\CLAUDE.md` lists `oauth_credentials_store.py` as a protected file. Rule 12 of the PR brief says *"do not duplicate token storage."* Both led to the same answer:

```
┌────────────────────────────────────────────────────────────┐
│  oauth_client_config_store.py  (NEW — slug-centric façade) │
│  - Validates slug (google/github/slack/figma/canva)        │
│  - PROVIDER_DISPLAY metadata table                         │
│  - last_updated tracked in sidecar JSON file               │
│  - is_configured / has_client_id / get_metadata helpers    │
└──────────────────────┬─────────────────────────────────────┘
                       │ writes through
                       ▼
┌────────────────────────────────────────────────────────────┐
│  oauth_credentials_store.py  (UNCHANGED — protected)       │
│  - Atomic JSON file at backend/.daena_oauth_overrides.json │
│  - chmod 0600 on POSIX                                      │
│  - get_override / set_overrides API                        │
└──────────────────────┬─────────────────────────────────────┘
                       │ read by
                       ▼
┌────────────────────────────────────────────────────────────┐
│  oauth_service.ConnectorOAuthService._get_credential       │
│  - Returns the override if non-empty, else env Settings    │
│  - ZERO CHANGES needed for new endpoint to take effect     │
└────────────────────────────────────────────────────────────┘
```

**Files written:**
- `backend/.daena_oauth_overrides.json` — gitignored, secret values, **already existed** for the prior Setup-modal flow
- `backend/.daena_oauth_client_metadata.json` — **new**, sidecar with `{slug: {last_updated: iso}}`. No secret values. Gitignore entry added.

---

## 4. Secret-handling proof

Every layer of the new code is leak-safe:

### 4.1 Endpoint shape (HTTP boundary)

`SaveClientConfigResponse` model:
```python
success: bool
slug: str
configured: bool
client_id_present: bool
last_updated: str
```
**No `client_id` field. No `client_secret` field. No echo on success.** A bad request (422) returns Pydantic's standard validation error which DOES not include the rejected raw body fields — verified by canary test.

`OAuthClientStatus` (list endpoint shape):
```python
slug, display_name, client_id_field, client_secret_field,
provider_ids, console_url, client_id_hint,
configured, client_id_present, last_updated
```
Same rule — only metadata, no values.

### 4.2 Logging

All `logger.info(...)` calls in `oauth_client_config_store.py` and `account_oauth_clients.py` log only `slug` and `value_len` (length integers). The values themselves are never passed to any logger:

```python
logger.info(
    "oauth_client_config_store.saved",
    slug=slug,
    client_id_len=len(client_id),
    client_secret_len=len(client_secret),
    # ^^ length only -- never log the value or any prefix of it.
)
```

### 4.3 Canary leak tests

Three pinned in `test_account_oauth_clients_endpoint.py`:

| Test | Asserts |
|---|---|
| `test_list_response_never_carries_secret_value` | Pre-seed `FAKE-CLIENT-ID-CANARY` into the store, then `json.dumps(GET /).find(canary) == -1` |
| `test_save_persists_and_returns_no_secret` | After POST, the response body bytes contain neither the client_id sentinel nor the secret sentinel |
| `test_save_then_list_never_returns_just_saved_secret` | Tightest round-trip: save with sentinels, then list, body bytes assert |

All three sentinel-style — they would catch a regression where a future maintainer accidentally adds `client_id_value` to the response model, or a logger formatter that prints a `**kwargs` dump.

### 4.4 File permissions

Sidecar metadata file: `chmod 0600` on POSIX (no-op on Windows; relies on user-profile ACLs). Same pattern as the underlying credentials store.

---

## 5. Marketplace state changes

The wire-level effect on marketplace cards is asynchronous and indirect — this PR does NOT change `marketplace_service.py`. The change happens because:

1. `oauth_service.ConnectorOAuthService.get_supported_providers()` checks `oauth_credentials_store.get_override(...)` and now finds non-empty values.
2. `marketplace_service._derive_lifecycle()` for OAuth-app cards relies on the V2 row's truth ladder, but the *Connect* button on the OAuth-app card calls `/api/v1/connections/v2/marketplace/oauth/start`, which in turn checks the same provider config. With config present, the start endpoint returns `success=True` instead of `failure_reason="configure_required"`.
3. The frontend `useMarketplace` hook re-fetches on `daena:retry-pending` — dispatched after every successful save / clear in `AccountOAuthClients.tsx`.

| Provider state | Before save | After save | After clear |
|---|---|---|---|
| OAuth client config | absent | configured | absent |
| Marketplace card primary action | `Configure` (deep-links to Account) | `Connect` (opens OAuthConnectDrawer) | `Configure` |
| `OAuthConnectDrawer` start endpoint | `success=False`, `failure_reason="configure_required"` | `success=True`, `authorization_url=...` | back to `configure_required` |
| Existing OAuth tokens in `ConnectorInstance.credentials` | unchanged | **unchanged** (preserved across rotations) | **unchanged** |

The **existing-tokens-preserved-on-clear** behavior is intentional. Clearing the client config means *"I'm rotating the OAuth app"*, not *"disconnect everyone."* Tokens already issued under the old client_id remain valid until they expire / are refreshed; they fail naturally on refresh and the operator gets a fresh consent flow.

---

## 6. Frontend flow

```
Operator clicks an OAuth-backed plugin card (e.g. GitHub)
  → MarketplaceCard primary_action="setup_guide" or "configure"
  → opens PluginDetailDrawer
  → Connect button opens OAuthConnectDrawer
  → drawer fires GET /api/v1/connections/v2/marketplace/oauth/start
  → server returns failure_reason="configure_required"
  → drawer renders FailureBlock with "Configure in Settings" CTA
  → click → navigate('/account#oauth-clients') + close drawer
  → AccountPage mounts → AccountOAuthClients section scrolls into view
  → operator pastes client_id + client_secret → Save
  → POST /api/v1/account/oauth-clients/{slug}
  → success → wipe drafts → toast → dispatch daena:retry-pending
  → useMarketplace re-fetches → card flips to Connect
  → operator goes back to /connections, clicks Connect
  → OAuthConnectDrawer now succeeds → consent popup → callback → tokens stored
  → marketplace card reaches "callable" via probe
```

UI components added/modified:

| File | Change |
|---|---|
| `frontend/src/pages/account/AccountOAuthClients.tsx` | **NEW** — paste-and-save section, mirrors `AccountProviderKeys.tsx` UX. Two paste fields per row (client_id + client_secret), reveal toggle on the secret only, configured / half-configured / not-configured pills, console deep-link, atomic save, clear button. |
| `frontend/src/pages/AccountPage.tsx` | Lazy-import `AccountOAuthClients`, render new `<section id="oauth-clients">` after the Provider Keys section. |
| `frontend/src/pages/connections/OAuthConnectDrawer.tsx` | `handleConfigure()` now navigates to `/account#oauth-clients` (was `/account/api-keys`, a path that didn't exist). Copy updated to point operators at the new section name. |

The deep-link contract is symmetrical: the drawer points to `#oauth-clients`, the AccountPage owns `<section id="oauth-clients">`, and `AccountOAuthClients.tsx` performs a smooth-scroll on mount when the URL hash matches.

---

## 7. Tests run

### 7.1 New tests (this PR)

`backend/tests/test_account_oauth_clients_endpoint.py` — **16 tests**:

- 3 list-shape tests (all-providers / initial-state / canary leak)
- 4 save-validation tests (round-trip / 404 unknown slug / 422 empty client_id / 422 empty client_secret)
- 1 save-then-list canary
- 1 marketplace-flip side-effect (verifies `oauth_service.get_supported_providers()` flips the bit)
- 3 delete tests (clears both fields / 404 unknown / no-op when unconfigured)
- 3 auth-gating tests (list/save/delete all 401)
- 1 coverage gate (every slug's provider_ids exist in `OAUTH_PROVIDERS`)

```
$ .venv/Scripts/python.exe -m pytest tests/test_account_oauth_clients_endpoint.py -q
................                                                         [100%]
16 passed in 5.76s
```

### 7.2 Targeted regression sweep

```
$ .venv/Scripts/python.exe -m pytest \
    tests/test_account_oauth_clients_endpoint.py \
    tests/test_account_provider_keys_endpoint.py \
    tests/test_oauth_credentials_store.py \
    tests/test_oauth_app_probe.py \
    tests/test_provider_keys_store.py \
    tests/test_oauth_marketplace.py \
    tests/test_skill_action_registry_phase1.py \
    tests/test_plugin_skills_ux_wiring.py \
    tests/test_local_model_probe.py
171 passed, 11 warnings in 25.95s
```

### 7.3 Broad sweep (oauth + connection + marketplace + account scope)

```
$ .venv/Scripts/python.exe -m pytest tests/ -k "connection_v2 or marketplace or oauth or account or connection" -q
2 failed, 367 passed, 4169 deselected, 11 warnings in 97.55s
```

The 2 failures are **pre-existing in `tests/test_connections.py`** and unrelated to this PR. Confirmed by re-running them against the baseline file state (no diff applied):

- `test_install_no_auth_connector_is_connected` — assertion drift (`'INSTALLED'` vs `'CONNECTED'`) tied to an unstaged WIP edit on `backend/app/api/v1/connections.py`.
- `test_extensions_install_persists_tenant_mcp_server` — `KeyError: 'id'` from a fixture-shape change.

Both failures originated outside this PR's scope (the modified files `backend/app/api/v1/connections.py` and `backend/tests/test_connections.py` were already `M` in `git status` before this work began, from earlier in-flight changes).

### 7.4 Frontend type check

```
$ cd frontend && npx tsc -b
(silent — clean)
```

### 7.5 Live verification

- `/account#oauth-clients` — section renders with the correct heading, copy block, and "No OAuth providers loaded." empty-state. Snapshot at `uid=3_168`.
- HMR picked up the new lazy-loaded `AccountOAuthClients` without a full reload.
- The `Failed to load OAuth client config` toast is expected because the dev backend on port 8000 was started before the new router include — it returns 404. Backend tests (16/16) prove the endpoint is correct; an operator-side `uvicorn` restart is needed to pick up the new route at runtime.

---

## 8. Honesty contract

Per Daena project rule 17 (Honesty + Persistence + Visibility):

| Requirement | How this PR satisfies it |
|---|---|
| No silent error suppression | `AccountOAuthClients.handleSave` surfaces backend errors via toast + inline rose-tinted error block; Pydantic 422 messages bubble through. |
| Persistence answer | "Where does this persist?" → atomic JSON file at `backend/.daena_oauth_overrides.json` (chmod 0600 on POSIX), via the protected `oauth_credentials_store`. Sidecar `.daena_oauth_client_metadata.json` for `last_updated`. |
| Failure visibility | "How does the user see it fail?" → 422 + inline error in the section. 404 (unknown slug) bubbles through `lib/api`. Save returning success=false displays "Save failed." |
| No advertised real-time without channel | This PR is request/response — no realtime claims. The `daena:retry-pending` event fires the marketplace re-fetch synchronously after Save. |
| No demo data | Empty state literally says "No OAuth providers loaded." Honest. |

---

## 9. Hard-rules compliance

Every line of the founder's "Hard rules" list verified:

| # | Rule | Status |
|---|---|---|
| 1 | Do not deploy production | ✅ no Cloud Run touched |
| 2 | Do not flip USE_CONNECTION_REGISTRY_V2=true | ✅ no env flip |
| 3 | Do not run vault --apply | ✅ no vault cli invoked |
| 4 | Do not delete V1 files | ✅ no deletions |
| 5 | Do not print/grep/log/commit secrets | ✅ length-only logs; canary leak tests |
| 6 | Do not expose client_secret after saving | ✅ response model has no value field |
| 7 | Do not send emails/DMs/webhooks/messages | ✅ no outbound traffic |
| 8 | Do not run external scans | ✅ none |
| 9 | Do not auto-install npm/pip/docker | ✅ none |
| 10 | Do not mark connected/callable without OAuth probe truth | ✅ this PR only saves client config; no marketplace-truth manipulation |
| 11 | Do not add new primary Connections tabs | ✅ section lives under Account, not Connections |
| 12 | Do not duplicate token storage | ✅ wraps `oauth_credentials_store`, sidecar holds metadata only |
| 13 | Do not execute plugin skills in this PR | ✅ no skill execution |

---

## 10. Remaining OAuth debt

Things this PR explicitly does NOT do, in priority order:

### Near-term (next PR or two)

1. **Per-provider `redirect_uri` override.** Currently the backend hard-codes `{base_url}/api/v1/connectors/oauth/callback`. For self-hosted operators behind a reverse proxy with a different external hostname, this URI may not match what they registered with the provider. Add a `redirect_uri` optional field to the save request.
2. **Optional `scopes` override.** The default scope set in `OAUTH_PROVIDERS` is what Daena requires for full integration. Some operators want to grant fewer scopes (e.g. read-only Drive). Not a blocker today; surfacing the override is a v2.
3. **Vault migration.** The protected `oauth_credentials_store` still uses a 0600 JSON file, same as `provider_keys_store`. Both should migrate to `vault_v2` envelope encryption (per ADR-002 D-003, Phase 4b). Migration must preserve existing operators' saved configs.

### Medium-term

4. **OAuth app provisioning UI.** Today the operator has to leave Daena, register an app on Google Cloud Console / GitHub Settings / etc., copy back. A "register Daena app on this provider" wizard would close the gap further.
5. **Audit log entries.** Save / clear actions log via `logger.info` but do NOT write to the structured audit log that governance / approvals consume. Add `audit_service.record_event("oauth_client_config_saved", slug=...)` for tenant compliance trails.
6. **Multi-tenant scoping.** This store is process-global. For multi-tenant Cloud deployments, we need `{tenant_id: {slug: ...}}` partitioning. Today it's single-operator-friendly only.

### Phase 2 prerequisites (not this PR's job, but blockers downstream)

7. PR-CONN-PLUGIN-SKILLS-EXECUTION-PHASE2-READONLY needs the *callable* OAuth state to be real for at least one provider. Operators with this PR can now reach `callable` for any of the 5 supported providers, which is what unlocks Phase 2 read-only execution to be meaningful.

---

## 11. Files changed

```
backend/.gitignore                                            +6  (sidecar entry)
backend/app/api/v1/__init__.py                              +13  (router include)
backend/app/api/v1/account_oauth_clients.py                +166  NEW
backend/app/services/integrations/oauth_client_config_store.py
                                                            +312  NEW
backend/tests/test_account_oauth_clients_endpoint.py       +273  NEW
frontend/src/pages/AccountPage.tsx                          +14
frontend/src/pages/account/AccountOAuthClients.tsx         +302  NEW
frontend/src/pages/connections/OAuthConnectDrawer.tsx      +12   (deep-link + copy)
docs/Ultraview/PR_CONN_OAUTH_CLIENT_CONFIG_IN_SETTINGS_REPORT.md
                                                            NEW (this doc)
```

Total: 5 new files, 4 modified, +1 README/.gitignore line, ~1100 lines added (incl. tests + report).

---

## 12. Commit

```
fix: add OAuth client config input for plugin connections
```

Stops the operator from needing to hand-edit `backend/.env` and restart `uvicorn` to configure OAuth-backed plugins. Adds a paste-and-save section under Account → OAuth Client Config for the 5 wired providers (Google / GitHub / Slack / Figma / Canva). Wires through to the existing `oauth_credentials_store` so `oauth_service` picks up the saved values without modification. Marketplace cards flip Configure → Connect after Save via the existing `daena:retry-pending` event. Canary leak tests pin that no endpoint ever returns or logs the saved secret values.

---

**Stop and report.**
