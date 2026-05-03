# PR-CONN-OAUTH-CONNECT -- Connect OAuth apps from plugin marketplace

**Branch:** rebuild-connections-mcp-runtime
**Date:** 2026-05-02
**Founder brief:** Add a safe OAuth Connect flow from the Plugins
marketplace for OAuth-backed app cards, reusing the existing OAuth
service/vault storage. Browse plugin -> Connect app -> authorize ->
test -> Connected only if token/probe succeeds.

---

## TL;DR

The Plugins grid can now start an OAuth Connect flow for `oauth_app`
catalog entries through one new endpoint + a new drawer. The flow
reuses ALL existing OAuth machinery: client_id/secret resolution
(env -> `oauth_credentials_store`), URL generation
(`ConnectorOAuthService.generate_auth_url`), code-exchange + AES vault
storage (`/api/v1/connectors/oauth/callback`). The only new pieces
are: (1) a catalog-id -> provider-id bridge, (2) a `_v2_marketplace`
flag in the in-memory state store so the existing callback ALSO
imports a V2 row after writing tokens to V1, (3) an `OAuthAppProbe`
that follows `vault_ref` back to the V1 ConnectorInstance to verify
the token.

- 1 new API endpoint:
  `POST /api/v1/connections/v2/marketplace/oauth/{entry_id}/start`
- 2 new backend modules: `oauth_marketplace.py` bridge,
  `oauth_app_probe.py` probe
- 1 patched callback in `connector_oauth.py` (single conditional block)
- 1 new frontend drawer: `OAuthConnectDrawer.tsx`
- 19 + 13 = 32 new unit + integration tests, all pass; 296 V2
  regression tests pass; frontend tsc clean.
- Zero em-dashes added. Zero V1 file deleted. Zero new top-level tabs.

**Hard rules honored:** no production deploy, no V2 flag flip, no
vault apply, no V1 deletion, no secret printing, no external scans/
messages, no auto-install, no duplicate token storage (V2 row carries
`vault_ref` pointing at V1 ConnectorInstance.id), no fake OAuth
success (`callable=true` requires the OAuthAppProbe to succeed),
client_secret/access_token/refresh_token never appear in
UI/logs/payloads.

---

## Supported OAuth providers

| Catalog id | Provider id | Scopes |
|---|---|---|
| `app-gmail` | `gmail` | gmail.modify, gmail.send, gmail.readonly |
| `app-google-calendar` | `google-calendar` | calendar, calendar.events |
| `app-google-drive` | `google-drive` | drive.readonly, drive.metadata.readonly |
| `app-github` | `github` | repo, read:user, read:org |
| `app-figma` | `figma` | files:read, file_variables:read |
| `app-slack` | `slack` | channels:read, channels:history, chat:write, users:read |
| `app-canva` | `canva` | design:content:read, design:meta:read |

These mirror exactly what `oauth_service.OAUTH_PROVIDERS` already
supports. Adding a new provider is a one-entry edit there +
optionally a catalog entry; the marketplace endpoint resolves
`app-<provider>` -> provider id by stripping the `app-` prefix
(with `-oauth` suffix tolerated for future providers like
`app-notion-oauth`).

**Coming-soon entries** (`app-notion-oauth`, `app-stripe-oauth`,
`app-cloudflare-oauth`, `app-sentry-oauth`) all have `install_method=
coming-soon` and return `unsupported_provider` from the start endpoint
because they are NOT in `OAUTH_PROVIDERS`. The drawer surfaces the
honest "not yet wired" copy with a pointer to the provider's MCP
equivalent.

---

## Start / callback flow

### `POST /api/v1/connections/v2/marketplace/oauth/{entry_id}/start`

Request: empty body (the redirect URI is computed server-side from
the request base URL so a misconfigured client cannot trick Daena
into sending consent to a third-party callback).

Response (success):
```json
{
  "success": true,
  "provider": "github",
  "authorization_url": "https://github.com/login/oauth/authorize?client_id=...&redirect_uri=...&scope=repo+read%3Auser+read%3Aorg&state=xyz",
  "redirect_uri": "http://your-host/api/v1/connectors/oauth/callback",
  "scopes": ["repo", "read:user", "read:org"],
  "state_ref": "<opaque-32-byte-csrf-token>",
  "failure_reason": null
}
```

Response (configure required):
```json
{
  "success": false,
  "provider": "gmail",
  "authorization_url": null,
  "redirect_uri": "http://your-host/api/v1/connectors/oauth/callback",
  "scopes": [...],
  "state_ref": null,
  "failure_reason": "configure_required: google_client_id not set -- paste your gmail OAuth client credentials in Settings -> API Keys before starting Connect."
}
```

Status codes:
- `200` -- success or structured failure (UI matches `failure_reason` prefix)
- `404` -- catalog entry not found
- `400` -- entry exists but `kind != oauth_app`

### Callback (existing, V1)

`GET /api/v1/connectors/oauth/callback?code=...&state=...` is
unchanged from V1. The patch I added is a single `if state_data.get("_v2_marketplace")` block right after V1 successfully writes
tokens to `ConnectorInstance.credentials`. The block calls
`oauth_marketplace.import_v2_row_after_callback()` which:

1. Imports / updates `ConnectionV2(kind=oauth_app, slug=oauth-<provider>)`
   for the caller's tenant. Idempotent on (tenant_id, kind, slug).
2. Sets `vault_ref = str(connector_instance.id)` so the OAuth probe
   can dereference back to the V1 row's encrypted token blob.
3. Stamps `configured=true, configured_at=now, authenticated=true,
   authenticated_at=now` -- the truth ladder lifts to "tokens
   received" but `callable=false` until the probe runs.
4. Stores `_account_identity` (masked email / handle) in the V2 row
   config so the UI can show "Connected as op***@example.com" without
   re-running userinfo.

Failure of the V2 import is logged but does NOT fail the callback --
the V1 token write already succeeded, and a missing V2 row is a UX
nicety that the operator can fix with a discovery refresh.

---

## Vault / OAuth store reuse

Founder rule 12: do not duplicate secret storage. Pinned by
implementation:

| Layer | Storage |
|---|---|
| OAuth client_id / client_secret (per-provider, per-installation) | `oauth_credentials_store.py` runtime overrides + env fallback |
| Access / refresh tokens (per-tenant, per-user) | V1 `ConnectorInstance.credentials` (AES-encrypted via `app.core.vault.encrypt_dict`) |
| V2 row link to the encrypted blob | `ConnectionV2.vault_ref = str(connector_instance.id)` |

The OAuth probe uses the **same** `app.core.vault.decrypt_dict` to
read tokens back. Zero new encryption code, zero new secret tables,
zero risk of drift between two stores.

---

## V2 row mapping

After a successful Connect flow:

```python
ConnectionV2(
    tenant_id=user.tenant_id,
    kind=ConnectionKind.OAUTH_APP,
    slug="oauth-<provider>",  # e.g. "oauth-gmail"
    display_name="Gmail",
    auth_method=AuthMethod.OAUTH_MANAGED,
    config={
        "kind": "oauth_app",
        "redirect_uri": "v1:connector_instance:<uuid>",  # NOT a real URL
        "scopes": [...],  # from OAUTH_PROVIDERS
        "_provider": "gmail",
        "_account_identity": "op***@example.com",  # masked
        "_v1_connector_instance_id": "<uuid>",
        "_seeded_by": "v2_marketplace_oauth_callback",
    },
    vault_ref="<connector_instance_uuid>",  # the link to encrypted blob
    configured=True, configured_at=<now>,
    authenticated=True, authenticated_at=<now>,
    callable=False,  # probe must prove this
)
```

`config` carries NO secret material. The `redirect_uri` field uses a
sentinel `v1:connector_instance:<uuid>` value (NOT a real URL) so the
probe knows where to find the tokens without anyone confusing it with
a callback URL. The `vault_ref` is the canonical link.

---

## Token / probe truth behavior

OAuth `oauth_app` truth-ladder transitions:

| Event | detected | configured | imported | reachable | authenticated | callable |
|---|---|---|---|---|---|---|
| Catalog entry only (no V2 row) | - | - | - | - | - | - |
| V2 row imported via /discovery/refresh (no token yet) | T | F | T | F | F | F |
| OAuth Connect flow completes (tokens written) | T | T | T | F | T | F |
| OAuthAppProbe runs (token present + not expired) | T | T | T | T | T | T |
| Token expires (next probe) | T | T | T | T | F (token_expired) | F |

Probe failure prefixes:
- `token_missing` -- vault_ref points at a row that was deleted or has no creds
- `token_expired` -- `expires_at` is in the past
- `refresh_failed` -- (reserved for follow-up PR; today maps to expired)
- `userinfo_failed` -- opt-in userinfo round-trip failed
- `unsupported_provider` -- `_provider` missing or not in OAUTH_PROVIDERS
- `vault_ref_missing` -- callback never wrote the link
- `vault_decrypt_failed` -- KEK mismatch between V1 write and V2 read

**Userinfo verification is OPT-IN.** `OAuthProbeOptions(verify_userinfo=False)` is the default so the probe stays cheap + offline-safe.
The opt-in path uses `ConnectorOAuthService.fetch_account_identity`
which already exists for V1 -- it hits the provider's userinfo
endpoint with a 6 s timeout and never logs the token. Tests cover
both branches.

---

## Secret-handling proof

Founder rules 5 + 13: never print, commit, or expose `client_secret`,
`access_token`, `refresh_token`, auth code, or state token in UI/logs.

**Implementation:**

- **Start endpoint payload**: contains `authorization_url` (which
  embeds the *public* `client_id` by OAuth design), `redirect_uri`
  (*public*), `scopes` (*public*), and the opaque `state_ref` (a
  CSRF token that is not a secret-bearing identifier on its own).
  Never carries `client_secret`. Pinned by `TestNoLeak.test_response_payload_never_has_client_secret` -- plants `sk-do-not-leak-9999`
  as Slack's client_secret, calls the start endpoint, asserts the
  sentinel does not appear anywhere in `res.text`.
- **OAuth probe capability spec**: built by `_safe_spec()` which
  enumerates the allowed fields (`provider`, `token_type`, `scope`,
  `account_identity`, `expires_at`). `access_token` and
  `refresh_token` are read into local variables for the
  presence/expiration check, then dropped on function return. Pinned
  by `TestNoLeak.test_capability_spec_omits_token_values` -- plants
  sentinel access + refresh tokens, asserts neither appears in the
  spec JSON.
- **Probe failure_reason**: `_reason()` builds a structured
  `prefix: detail` string with bounded length. Detail strings come
  from local variables that DO NOT carry token material -- e.g.
  `f"token expired at {expires_at_str}"` carries the timestamp
  (public) but not the token (secret). Pinned by `TestNoLeak.test_failure_reason_never_carries_token`.
- **Structured logs**: `logger.info("v2_oauth_marketplace.start", ...)`
  carries `catalog_entry_id`, `provider`, `redirect_uri` --
  intentionally NOT `auth_url` itself (would re-embed `client_id`).
  `logger.info("v2_oauth_marketplace.row_imported", ...)` carries
  `account_identity_present=bool(...)` instead of the value. The
  V1 callback's existing `connector_oauth.connected` log is
  unchanged.
- **State store**: uses `secrets.token_urlsafe(32)` (CSPRNG, 256 bits
  of entropy). State is treated as a one-shot CSRF token; it's
  never persisted to disk and is popped from the in-memory store
  the moment the callback runs.

---

## Frontend flow

**No new tabs.** Brain / Plugins / Advanced layout unchanged.

```
Plugin card "Connect" button (oauth_app entries only)
  -> opens OAuthConnectDrawer
       Step 1 (preflight): show provider, scopes, redirect URI;
                            "Open consent page" button
       Step 2 (awaiting):  popup opened with provider's authorization URL;
                            drawer listens for postMessage from /connectors/oauth/callback HTML
       Step 3 (success):   "Tokens received" copy + "Test on the plugin card" hint
       Step 4 (failed):    honest failure copy
                            - configure_required -> Configure deep-link to /account/api-keys
                            - unsupported_provider -> "use the MCP equivalent" hint
                            - other -> generic failure with redirect URI re-displayed
                              for the operator to verify in the provider's dev portal
       Done -> dispatches `daena:retry-pending` so marketplace cards refresh
```

**Honesty:**

- "Connected" pill ONLY appears when `v2_truth.callable.value === true`
  AND no recent failure -- the existing PluginCard adapter; the
  drawer doesn't override.
- After the drawer's success state, the plugin card still shows
  "Needs auth" or "Installed" until the next `/marketplace/cards`
  poll surfaces the V2 row. Then it shows "Connected" only after
  the operator (or an automated probe) hits Test and the OAuth probe
  proves the token.
- Tokens NEVER touch the frontend. The browser only opens the
  consent URL in a popup; the provider redirects directly to Daena's
  backend callback, which writes encrypted tokens to V1 and returns
  HTML that posts a non-secret success message to the opener.

---

## Tests run

### New: `test_oauth_marketplace.py` (19 tests, 100% pass)

| Class | Tests | What it pins |
|---|---|---|
| `TestProviderIdMapping` | 11 | catalog id -> provider id (parametrized over 7 supported); coming-soon returns None; supported set == OAUTH_PROVIDERS keys; canonical slug |
| `TestStartOauthBridge` | 3 | happy-path returns auth URL + state; configure_required when client missing; unsupported entry returns clear reason |
| `TestStartEndpoint` | 4 | endpoint happy path; unknown entry -> 404; non-oauth entry -> 400; configure_required path |
| `TestNoLeak` | 1 | sentinel client_secret never appears in response payload |

### New: `test_oauth_app_probe.py` (13 tests, 100% pass)

| Class | Tests | What it pins |
|---|---|---|
| `TestVaultRefMissing` | 1 | empty vault_ref -> vault_ref_missing |
| `TestUnsupportedProvider` | 1 | no _provider in config -> unsupported_provider |
| `TestV1InstanceMissing` | 1 | missing V1 ConnectorInstance -> token_missing |
| `TestTokenExpired` | 1 | past expires_at -> token_expired (no token leak) |
| `TestHappyPath` | 2 | future expiration -> success; no expires_at (GitHub) treated as non-expiring |
| `TestNoLeak` | 2 | capability spec omits access/refresh tokens; failure_reason never carries token |
| `TestUserinfoVerification` | 2 | opt-in success keeps probe successful; failure blocks callable |
| `TestRegistryWiring` | 3 | install_oauth_app_probe registers; install_all_probes includes oauth; idempotent |

### Regression

```
.venv/Scripts/python.exe -m pytest tests/ -k "connection_v2 or
  connection_registry or mcp_server_probe or cli_runtime_probe or
  cli_mcp_writer or marketplace_install or skill_pack or
  provider_probe or oauth_app_probe or oauth_marketplace" -q
# -> 296 passed, 3974 deselected in 21.59s
```

No pre-existing test failed after the OAuth bridge + probe landed.

### Frontend

```
cd frontend && npx tsc --noEmit
# -> exit 0 (clean)
```

`OAuthConnectDrawer.tsx`, updated `PluginCardView.tsx`, and the new
`startMarketplaceOAuth` hook in `useMarketplace.ts` all type-check
under strict TypeScript.

---

## Files changed

| Path | Lines | Purpose |
|---|---|---|
| `backend/app/services/connection_v2/oauth_marketplace.py` | +247 | NEW: catalog id -> provider id bridge, start helper, callback hook |
| `backend/app/services/connection_v2/probes/oauth_app_probe.py` | +287 | NEW: OAuthAppProbe + token presence/expiration check + opt-in userinfo |
| `backend/app/services/connection_v2/probes/__init__.py` | +6 | wire install_oauth_app_probe into install_all_probes |
| `backend/app/api/v1/connections_v2.py` | +75 / -1 | new POST /marketplace/oauth/{entry_id}/start endpoint |
| `backend/app/api/v1/connector_oauth.py` | +20 | callback patch: import V2 row when state has _v2_marketplace flag |
| `backend/app/schemas/connection_v2.py` | +25 | NEW: OAuthStartRequest + OAuthStartResponse models |
| `backend/tests/test_oauth_marketplace.py` | +290 | NEW: 19 bridge + endpoint tests |
| `backend/tests/test_oauth_app_probe.py` | +275 | NEW: 13 probe tests |
| `frontend/src/hooks/useMarketplace.ts` | +35 | NEW: startMarketplaceOAuth hook + types |
| `frontend/src/pages/connections/OAuthConnectDrawer.tsx` | +395 | NEW: 4-step OAuth Connect drawer |
| `frontend/src/pages/connections/PluginCardView.tsx` | +30 / -2 | route oauth_app `connect` action to OAuthConnectDrawer |
| `docs/Ultraview/PR_CONN_OAUTH_CONNECT_REPORT.md` | NEW | this report |

Total: ~1700 lines added, ~3 lines deleted, 0 V1 file deleted.

---

## Remaining blockers (deferred to future PRs)

| Future PR | Goal | Why deferred |
|---|---|---|
| `PR-CONN-OAUTH-REFRESH` | Auto-refresh access tokens via the existing `ConnectorOAuthService.refresh_token` when probe sees `token_expired` AND a refresh_token is present | Refresh logic exists in V1's `check_and_refresh`; needs a tenant-context wrapper + audit-log entry per refresh. Out of scope for "Connect" PR. |
| `PR-CONN-OAUTH-NOTION` | Wire Notion / Stripe / Cloudflare / Sentry OAuth in `OAUTH_PROVIDERS` | Each needs its own auth_url, token_url, scope set, and (for Notion) bot vs user-token handling. Per-provider research. |
| `PR-CONN-OAUTH-USERINFO-DEFAULT` | Flip `verify_userinfo=True` on the default probe options | Today off so probes stay offline-safe; flipping requires per-provider rate-limit consideration + opt-out for air-gapped operators. |
| `PR-CONN-OAUTH-DISCONNECT` | "Disconnect" button on connected OAuth cards that revokes tokens (when provider supports it) + archives the V2 row | Per-provider revocation endpoints differ; needs the same rigor as Connect. |
| `PR-CONN-OAUTH-PER-USER-V2` | Multiple V2 oauth_app rows per provider per tenant (e.g. two GitHub accounts) | Today the V2 slug is `oauth-<provider>` (one per tenant). Needs slug schema extension + UI for "add another account". |
| `PR-CONN-OAUTH-STATE-PERSIST` | Move `_oauth_states` from in-memory dict to Redis / DB | Today uses the same in-memory dict V1 uses (founder rule 12: don't duplicate). Production-deploy hardening. |

---

## Why this is the right shape

1. **Reuse > rewrite.** Every OAuth code path the operator's tokens
   travel through is V1's existing path: `_get_credential` for the
   client config, `generate_auth_url` for the consent URL,
   `exchange_code` for the token swap, `encrypt_dict` for vault
   storage. The bridge is ~245 lines that adds a `_v2_marketplace`
   flag + a row import; nothing else changed.
2. **vault_ref is the link, not the storage.** V2 rows reference V1
   ConnectorInstance.id rather than copying the encrypted blob. This
   means when V2 eventually fully replaces V1, the migration can
   mass-rewrite `vault_ref` to point at the new storage with no
   re-encryption pass.
3. **Probe runs against the same blob V1 wrote.** No two-store
   inconsistency possible. If V1's vault key changes, V2's probe
   fails the same way V1's runtime would -- one source of truth for
   "is this token usable."
4. **Failure surface mirrors PR-CONN-MCP-INSTALL-INTO-CLI.** Same
   prefix-string protocol (`token_missing:`, `token_expired:`,
   `configure_required:`, etc.) so the frontend can match on prefix
   without parsing free-form text. Adding a new failure mode is a
   one-constant addition.
5. **Drawer never asks for secrets.** The operator's only inputs are:
   click "Open consent page", approve at the provider, optionally
   click "Configure" to deep-link to vault-backed Settings. No paste
   field for client_secret or access_token in Connections.

---

## Commit

```
canonicalization: connect OAuth apps from plugin marketplace
```

Stops here. Awaiting next direction.
