# DAENA OAuth + Gmail Activation Checklist

Status: REFERENCE (founder-gated to execute). Generated 2026-06-04 from source of truth.
Sources verified in-repo:
- `backend/app/services/integrations/oauth_service.py` (OAUTH_PROVIDERS table, flows)
- `backend/app/api/v1/connector_oauth.py` (authorize / callback routes, redirect_uri build)
- `backend/app/core/config.py` (Settings fields, env-var mapping)
- `backend/app/services/integrations/gmail_client.py` (send path)

This document fills the exact key names, callback paths, and scopes that a live
Google/GitHub login + Gmail send requires. It does NOT contain any secret values.
Executing any provider-console step or live token exchange is a founder action.

---

## 1. How env vars map to Settings

`Settings` in `config.py` uses `SettingsConfigDict(case_sensitive=False)` with NO
`env_prefix`. So each field name maps directly to an env var of the same name,
case-insensitive. Set them in `backend/.env` (local) or Cloud Run secrets (prod).

| Provider | Client-ID env var | Client-secret env var | Settings fields |
|----------|-------------------|------------------------|-----------------|
| Google (Gmail, Calendar, Drive) | `GOOGLE_CLIENT_ID` | `GOOGLE_CLIENT_SECRET` | `google_client_id` / `google_client_secret` |
| GitHub | `GITHUB_CLIENT_ID` | `GITHUB_CLIENT_SECRET` | `github_client_id` / `github_client_secret` |
| Figma | `FIGMA_CLIENT_ID` | `FIGMA_CLIENT_SECRET` | `figma_client_id` / `figma_client_secret` |
| Slack | `SLACK_CLIENT_ID` | `SLACK_CLIENT_SECRET` | `slack_client_id` / `slack_client_secret` |
| Canva | `CANVA_CLIENT_ID` | `CANVA_CLIENT_SECRET` | `canva_client_id` / `canva_client_secret` |

Note: all three Google connectors (`gmail`, `google-calendar`, `google-drive`)
share ONE Google OAuth client (`google_client_id` / `google_client_secret`).

Runtime alternative (no restart): operators can paste client_id/secret via the
Connections > Setup modal; `oauth_service._get_credential` checks the runtime
override store (`oauth_credentials_store.get_override`) BEFORE falling back to the
Settings/env value. Either path works; env is the production-stable path.

`OAUTH_REDIRECT_BASE_URL` (Settings `oauth_redirect_base_url`, default
`http://127.0.0.1:5173`) exists but is NOT used by the connector OAuth router; see
section 3 for how the redirect_uri is actually built.

---

## 2. Callback / redirect routes (register these at the provider)

Router prefix: `/connectors` (mounted under `/api/v1`). From `connector_oauth.py`:

| Purpose | Method + path |
|---------|---------------|
| Get consent URL | `GET /api/v1/connectors/{connector_id}/oauth/authorize` |
| Provider redirect (callback) | `GET /api/v1/connectors/oauth/callback` |
| List supported providers | `GET /api/v1/connectors/oauth/providers` |
| List connected accounts | `GET /api/v1/connectors/oauth/accounts?provider=gmail` |
| Manual token refresh | `POST /api/v1/connectors/{instance_id}/oauth/refresh` |

`connector_id` values (provider slugs): `gmail`, `google-calendar`,
`google-drive`, `github`, `figma`, `slack`, `canva`.

### The Authorized redirect URI to register at each provider

The callback URL is built at request time as:

    redirect_uri = f"{request.base_url}/api/v1/connectors/oauth/callback"

`request.base_url` is the backend origin serving the authorize call (NOT the
frontend, NOT `oauth_redirect_base_url`). So register the redirect URI that
matches the backend origin:

- Local dev:  `http://127.0.0.1:8000/api/v1/connectors/oauth/callback`
- Production: `https://<backend-host>/api/v1/connectors/oauth/callback`
  (e.g. `https://daena.mas-ai.co/api/v1/connectors/oauth/callback` if the
  backend serves that origin; use the actual Cloud Run / proxied backend host)

CAUTION: the redirect_uri used at `authorize` must EXACTLY match the one used at
`exchange_code` (it is round-tripped via the in-memory `_oauth_states` store) AND
must be in the provider's allowed list, or token exchange returns redirect_uri
mismatch. If the frontend and backend differ in origin, ensure the authorize
call is reached at the same backend origin you registered.

OPEN ITEM for prod hardening: `_oauth_states` is an in-process dict
(`connector_oauth.py:36`). On a multi-instance / restarted backend, a callback
can land on a worker that never saw the state and fails with "Invalid or expired
state." For single-instance Cloud Run this is fine; for scaled deploys move state
to Redis/DB before relying on OAuth in production. (Code comment already flags this.)

---

## 3. Scopes requested per provider (from OAUTH_PROVIDERS)

| Provider | auth_url | scopes |
|----------|----------|--------|
| gmail | accounts.google.com/o/oauth2/v2/auth | `gmail.modify`, `gmail.send`, `gmail.readonly` |
| google-calendar | (same Google) | `calendar`, `calendar.events` |
| google-drive | (same Google) | `drive.readonly`, `drive.metadata.readonly` |
| github | github.com/login/oauth/authorize | `repo`, `read:user`, `read:org` |
| figma | figma.com/oauth | `files:read`, `file_variables:read` |
| slack | slack.com/oauth/v2/authorize | `channels:read`, `channels:history`, `chat:write`, `users:read` |
| canva | canva.com/api/oauth/authorize | `design:content:read`, `design:meta:read` |

Google requests `access_type=offline` + `prompt=consent` (extra_auth_params) so a
refresh_token is returned on first consent. Without `prompt=consent` Google omits
the refresh_token on re-consent.

---

## 4. Gmail SEND path (what "send a real email" exercises)

Primary: Gmail **API** (NOT raw SMTP). `gmail_client.py`:
- `GMAIL_API_BASE = https://gmail.googleapis.com/gmail/v1/users/me`
- `send_email()` builds a MIME message, base64url-encodes it, POSTs to
  `{GMAIL_API_BASE}/messages/send` with the OAuth2 access token.
- Requires the `gmail.send` scope (present in the gmail connector scopes above).
- `send_existing_draft()` sends a previously created draft by id.

Fallback: SMTP via `email` + `app_password` credentials (Gmail app password),
used only when an instance is configured with that credential shape instead of
OAuth tokens.

So a live Gmail send verification needs:
1. `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` set.
2. Backend redirect URI registered in the Google Cloud OAuth client.
3. OAuth consent completed for the `gmail` connector (yields tokens with
   `gmail.send` scope, stored encrypted in `ConnectorInstance.credentials`).
4. A send dispatched through the controlled-execution handler
   (`gmail_send_existing_draft` / `gmail_create_draft`), which is governance-gated.

---

## 5. Founder execution checklist (gated)

- [ ] Google Cloud Console: create/confirm OAuth 2.0 Web client; add Authorized
      redirect URI = backend origin + `/api/v1/connectors/oauth/callback`.
- [ ] Add `gmail`, calendar, drive scopes to the OAuth consent screen; publish or
      add test users (your founder emails).
- [ ] GitHub: register OAuth App; set Authorization callback URL to the same
      `/api/v1/connectors/oauth/callback`.
- [ ] Set `GOOGLE_CLIENT_ID/SECRET` and `GITHUB_CLIENT_ID/SECRET` in
      `backend/.env` (local) or Cloud Run secrets (prod). (Founder secret action.)
- [ ] Restart backend (or use Connections > Setup modal to paste creds live).
- [ ] `GET /api/v1/connectors/oauth/providers` -> confirm `configured: true`.
- [ ] Run the consent flow for `gmail`; confirm a CONNECTED ConnectorInstance with
      a non-empty `owner_email`.
- [ ] Create a draft, then dispatch a real send to a founder-owned inbox; confirm
      receipt. (Real external send = founder-gated.)

Nothing in this checklist is auto-executed by the agent: provider-console changes,
secret writes, and live sends are all founder actions.
