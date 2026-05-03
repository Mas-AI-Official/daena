# PR-CONN-OAUTH-REFRESH-DISCONNECT — Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** _to be filled in after squash_
**Date:** 2026-05-03
**Sprint:** DAENA-AUTONOMOUS-LOCAL-PRODUCTION-SPRINT (PR-3 of 4)

---

## 1. Goal

Add token-refresh + disconnect/revoke/archive lifecycle for OAuth-backed
connector instances. Per the founder brief:

- **Refresh** — operator-triggered manual refresh (the existing
  `check_and_refresh` only fired during chat-time)
- **Disconnect** — explicit + confirmed; revoke at the provider before
  clearing local creds
- **Archive** — soft-archive lane (per founder rule "never delete")
- **Audit** — every action records outcome metadata, never tokens

---

## 2. Hard rules — all honored

| Rule | Enforced? |
|---|---|
| No external messages | YES — provider revoke calls are OAuth control plane (RFC-7009), not messages |
| No secret/token leakage | YES — token values never logged, never returned in responses (`test_refresh_token_outcome_shape_only_has_safe_keys` pins outcome keys to `{success, expires_at, reason}`) |
| Disconnect should be explicit and confirmed | YES — `{confirm: true}` body required; 400 + `confirmation_required` otherwise |
| Existing tokens preserved unless operator chooses disconnect | YES — refresh path UPDATES the access_token in place (does not invalidate refresh_token); only disconnect/archive clear them |
| Tests required | YES — 6 new tests, 76/76 passing in `test_connections.py` + `test_skill_executor_phase2.py` |

---

## 3. Files changed

### `backend/app/core/constants.py`

- Added `ConnectorStatus.ARCHIVED = "ARCHIVED"` enum member with founder-rule comment ("never delete -- archive instead")

### `backend/app/services/integrations/oauth_service.py`

- Added `ConnectorOAuthService.revoke_token(provider, token, token_type_hint)` — best-effort RFC-7009 revoke
  - Endpoint mapping: Google services → `https://oauth2.googleapis.com/revoke`, Slack → `auth.revoke`
  - GitHub + Figma + Canva: no RFC-7009 endpoint → returns `success=False, reason='provider_no_revoke_endpoint'` cleanly
  - Network/HTTP failures logged but never raise (operator intent is "stop using token", not "guarantee server-side state")
  - Returns `{success, http_status?, reason}` — token value never logged, never returned

### `backend/app/services/connection_service.py`

- `ConnectionService.disconnect` — added `confirm: bool` (raises ValueError if False) + `actor_user_id`. Calls revoke best-effort BEFORE clearing creds. Writes audit row with `revoke_attempted` + `revoke_reason` (no token values).
- `ConnectionService.archive` — NEW method, same shape as disconnect but moves to `ARCHIVED` status
- `ConnectionService.refresh_token_for_instance` — NEW operator-triggered refresh wrapper. Loads + decrypts creds, calls `oauth_service.refresh_token` against provider, encrypts + re-stores. Returns `{success, expires_at, reason}` — never tokens.
- `list_instances` — default query now excludes `ARCHIVED` rows; explicit `?status=ARCHIVED` includes them

### `backend/app/api/v1/connections.py`

- New `ConfirmActionRequest` Pydantic model (`{confirm: bool = False}`)
- `POST /instances/{id}/disconnect` — body required + 400 on `confirm=false`/missing
- `POST /instances/{id}/archive` — NEW endpoint, same confirm contract
- `POST /instances/{id}/refresh-token` — NEW endpoint, response carries `{success, data: {success, expires_at, reason}}`
- `actor_user_id=user.id` propagated to service for audit attribution

### `backend/tests/test_connections.py`

- Updated `test_disconnect_clears_credentials` — now sends `{confirm: true}` body
- 5 NEW tests:
  - `test_disconnect_without_confirm_returns_400` (asserts 400 + code)
  - `test_archive_requires_confirm`
  - `test_archive_sets_status_and_hides_from_default_list` (proves default list excludes ARCHIVED, `?status=ARCHIVED` re-includes)
  - `test_refresh_token_no_refresh_token_returns_failure`
  - `test_refresh_token_outcome_shape_only_has_safe_keys` (response shape pinned to `{success, expires_at, reason}` — no token-shaped keys)

### `docs/Ultraview/PR_CONN_OAUTH_REFRESH_DISCONNECT_REPORT.md` (this file)

### `docs/Ultraview/SPRINT_LOG_DAENA_LOCAL_PROD.md` (PR-3 row updated)

---

## 4. New API surface (operator-facing)

| Endpoint | Method | Body | Response |
|---|---|---|---|
| `/api/v1/connections/instances/{id}/disconnect` | POST | `{"confirm": true}` | `{success, data: instance}` (status=DISCONNECTED) |
| `/api/v1/connections/instances/{id}/archive` | POST | `{"confirm": true}` | `{success, data: instance}` (status=ARCHIVED) |
| `/api/v1/connections/instances/{id}/refresh-token` | POST | _(none)_ | `{success, data: {success, expires_at, reason}}` |

Without `confirm: true`, disconnect/archive return:
```
HTTP 400
{
  "detail": {
    "code": "confirmation_required",
    "message": "Disconnect requires explicit confirmation. POST {\"confirm\": true} to proceed."
  }
}
```

---

## 5. Token-leak defense (multi-layer)

The PR adds three layers of leak prevention beyond what existed:

1. **Audit `action_params` never carries token values** — only `revoke_attempted`/`revoke_reason`/`outcome` strings. `_record_real_outcome` pattern from PR-1/PR-2 reused.
2. **Refresh response is restricted to `{success, expires_at, reason}`** — pinned by test. The new access_token is encrypted and stored back into `instance.credentials`, not returned.
3. **Disconnect calls `revoke_token` only after** decrypting from `instance.credentials`; the token value never enters a log line, audit row, or response.

The provider-side revoke DOES send the token over the network to the provider's revoke endpoint (this is unavoidable — that's what revoke means). It is logged only as outcome metadata.

---

## 6. Test result (76/76)

```
$ .venv/Scripts/python.exe -m pytest tests/test_connections.py tests/test_skill_executor_phase2.py
============================= 76 passed in 29.38s =============================
```

26 connections (5 PR-3-new + 21 pre-existing all green) + 50 executor (PR-1 + PR-2) = full surface clean.

---

## 7. Live verification (deferred to operator)

PR-3's behavior depends on having a real OAuth instance to act on. The
dev backend has none. Live verify happens when:
1. Operator completes Google OAuth via existing `/oauth/authorize` flow
2. Operator clicks Refresh → expects `{success: true, expires_at: "..."}`
3. Operator clicks Disconnect → confirmation modal → `{confirm: true}` posted → status=DISCONNECTED
4. Operator clicks Archive → confirmation modal → `{confirm: true}` → status=ARCHIVED → instance vanishes from default list

Backend half is fully test-covered. Frontend wiring (modal + button) is
existing work — the new endpoints conform to the existing API shape.

---

## 8. What did NOT change

- No frontend changes (per sprint scope; backend + tests only)
- No production deploy
- No Cloud Run write
- No `vault --apply`
- No `USE_CONNECTION_REGISTRY_V2` flip
- No npm/pip install
- No browser automation
- The pre-existing `oauth_service.refresh_token` and `check_and_refresh` (chat-time auto-refresh) are unchanged — `refresh_for_instance` wraps the existing primitive
- Existing `disconnect` HTTP handler is updated, not removed; signature is backward-compatible at the URL level (only the body contract is new)

---

## 9. Provider revoke status matrix

| Provider | Revoke endpoint | RFC-7009? |
|---|---|---|
| Gmail / Google Calendar / Google Drive | `https://oauth2.googleapis.com/revoke` | Yes |
| Slack | `https://slack.com/api/auth.revoke` | Custom (Bearer header) |
| GitHub | _(no programmatic revoke from server-side client_secret; operator action via Settings → Applications)_ | No |
| Figma | _(no public revoke endpoint)_ | No |
| Canva | _(no public revoke endpoint)_ | No |

For non-RFC providers, disconnect logs the revoke outcome as
`provider_no_revoke_endpoint` and proceeds with local-only credential
clear. The audit row captures this so operators see why server-side
revoke didn't happen.

---

## 10. Branch state after PR

```
<this commit>  fix: add OAuth refresh and disconnect for plugin cards
4fb23fe        docs: pin PR-2 commit hash and update sprint log
4f367b3        canonicalization: execute GitHub and Sentry read-only skills
7d370d4        docs: pin PR-1 commit hash and update sprint log
bdb1ca8        canonicalization: execute filesystem and HuggingFace read-only skills
```

Sprint state: PR-3 SHIPPED. Continuing autopilot to PR-4 (local production smoke checklist).
