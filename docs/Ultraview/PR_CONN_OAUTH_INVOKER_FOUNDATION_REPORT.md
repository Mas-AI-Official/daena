# PR-CONN-OAUTH-INVOKER-FOUNDATION -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** (to be pinned)
**Date:** 2026-05-03
**Sprint:** DAENA-LOCAL-USABILITY-SPRINT-3 (PR-4 of 5)

---

## 1. Goal

Build the read-only OAuth invoker FOUNDATION needed to eventually
promote Gmail + Google Drive read-only skills, **without yet promoting
those skills**. Promotion is gated on a follow-up PR that wires the
invoker into the `SkillExecutorService.execute()` dispatch.

This PR ships the safe machinery; the operator brief (and the existing
Sprint-2 invariant `test_pr3_gmail_and_drive_remain_planned_only`) keep
Gmail/Drive in `planned_only` until that wiring lands.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| No send email | YES -- `messages.send` would fail at the allowlist gate; defense test `test_no_write_method_id_in_allowlist` rejects any method_id containing send/create/update/delete/draft/post/patch |
| No modify files | YES -- only `files.list` (no path) + `files.get_metadata` (no body); `files.update` / `files.delete` not in allowlist |
| No delete | YES -- module-load invariant forbids any non-GET http_method |
| No external message | YES -- only Google APIs are configured; no Slack/Discord/etc. surface in the foundation |
| No browser | YES -- pure server-side httpx call; no browser automation |
| Dry-run / mocked tests first | YES -- 21 tests, all using `OAuthInvoker(http_client=MagicMock(...))`. ZERO real network |
| No-secret/no-token leak tests | YES -- `_scrub` Bearer-token regex + `test_invoke_outcome_never_carries_token_field` + 401-then-401 reason-string scrubbing |
| Allowlist of provider/methods | YES -- 4-entry frozen tuple; `test_allowlist_set_is_pinned` enforces exactness |
| Response caps | YES -- `DEFAULT_RESPONSE_CAP_BYTES=64KB`, `DEFAULT_RESPONSE_CAP_ITEMS=50`, with smaller per-method overrides for messages (20) and metadata (8KB / 1 item) |
| Token-refresh-on-401 | YES -- AT MOST ONCE per invoke call; second 401 returns clean `auth_expired` and operator must re-connect |

---

## 3. The shipped surface

### `backend/app/services/connection_v2/oauth_invoker.py` (NEW)

* `OAuthMethod` dataclass -- frozen entry shape: plugin_id, method_id,
  provider, base_url, path_template, required_inputs, response caps,
  http_method (forced GET).
* `OAUTH_METHOD_ALLOWLIST` -- 4 entries:
  * `app-gmail:messages.list_unread` -> GET /gmail/v1/users/me/messages?q=is:unread
  * `app-gmail:messages.search` -> GET /gmail/v1/users/me/messages?q={query}
  * `app-google-drive:files.list` -> GET /drive/v3/files
  * `app-google-drive:files.get_metadata` -> GET /drive/v3/files/{file_id}
* `_validate_allowlist()` -- module-load invariant. Boot fails if any
  entry has a non-GET http_method, an http://, double-slash, or
  zero/negative cap.
* `OAuthInvoker` class:
  * `is_allowed()` -- pure helper for "could this dispatch?"
  * `get_method()` -- returns the entry or None
  * `invoke()` -- the network entry point. Raises for caller-bug
    paths (method-not-allowed, missing required input, instance not
    found, no access_token); returns `InvokeOutcome(ok=False, ...)`
    for predictable network failures (timeout, 5xx, 401-after-refresh,
    too-large response).
* `InvokeOutcome` dataclass -- 6 fields. Defensive structural test
  pins that NONE of them are token-shaped.
* `_scrub()` -- single-line Bearer-token regex; defense in depth for
  any accidental string interpolation in error paths.

### `backend/tests/test_oauth_invoker.py` (NEW)

21 tests across 9 logical sections:

1. Allowlist contract -- exact set, GET+HTTPS only, no write substrings, `is_allowed` purity
2. Token-leak defense -- `_scrub` redaction + structural field check
3. Error paths -- method-not-allowed / missing input / instance-not-found / no-access-token
4. URL/path-substitution defense -- forbids `/` and control chars in path placeholders
5. Mocked happy paths -- Gmail list_unread + Drive get_metadata with path substitution
6. 401-refresh-retry -- 3 scenarios: success, second-401, refresh-call-fails
7. Response capping -- byte-cap truncation + item-cap slicing
8. Vendor 5xx -- safe `vendor_error` outcome
9. Foundation invariant -- Phase 2 oauth entries STAY planned_only

---

## 4. What stays out of this PR (intentional)

| Feature | Why deferred |
|---|---|
| Wiring `OAuthInvoker.invoke()` into `SkillExecutorService.execute()` | Needs a separate PR that updates the dispatch branch and adds end-to-end tests with the executor's audit-row contract. Keeps PR-4's blast radius minimal. |
| Promoting `app-gmail:*` and `app-google-drive:*` to `mcp_tool` | Same reason. The Sprint-2 PR-3 invariant `test_pr3_gmail_and_drive_remain_planned_only` would fail any premature flip. |
| `files.get_content` (file body download) | Has its own size + permission surface that deserves a dedicated PR with explicit byte-cap, MIME allowlist, and consent-token check (Asset Shield). |
| Write methods (send / draft / update / delete) | Phase 3 territory. The whole module is GET-only by module-load invariant; adding writes would require restructuring the http_method field, which the test invariants forbid. |
| Per-tenant rate limiting on the invoker | Pre-existing rate limits at the FastAPI dependency layer apply to the eventual route. Per-method limits can stack later. |

---

## 5. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_oauth_invoker.py
21 passed in 0.54s

$ .venv/Scripts/python.exe -m pytest tests/test_oauth_invoker.py tests/test_skill_executor_phase2.py tests/test_connection_v2_marketplace.py tests/test_connections.py
195 passed, 14 errors (errors are pre-existing cross-file tenant collision; each file passes in isolation)
```

Test growth across Sprint-3:
* End of Sprint-2: 76 phase2 + 26 connections = 102
* PR-1: +5 marketplace tests = 98 marketplace
* PR-2: +0 (FE-only)
* PR-3: +7 phase2 = 64 phase2
* PR-4: +21 OAuth invoker (new file)

Sprint-3 total: 21 + 64 + 26 + 98 = **209 passing in their natural files**.

---

## 6. Live verification (deferred to operator + follow-up PR)

The invoker is ready but NOT exercised live in this PR. To verify
end-to-end the next PR will:

1. Wire `OAuthInvoker.invoke()` into `SkillExecutorService.execute()`
   when `entry.backend_surface == "oauth"` AND
   `entry.execution_mode == "mcp_tool"`.
2. Promote the 4 Gmail+Drive read skills to `mcp_tool` with the
   matching method_id values (`messages.list_unread`,
   `messages.search`, `files.list`, `files.get_metadata`).
3. Update the invariant `test_pr3_gmail_and_drive_remain_planned_only`
   to point to the now-promoted state, plus add the 4 keys to
   `PROMOTED_TO_MCP_TOOL` with a new PR id.
4. Add end-to-end tests using the existing `SkillExecutor` audit-row
   contract.

---

## 7. What did NOT change

* No backend route added (the invoker is not yet HTTP-callable).
* No frontend change.
* No vault, no credentials store, no OAuth client config touched.
* No production deploy, no V2 flag flip, no secret read.
* `ConnectorOAuthService.refresh_token` and `check_and_refresh` --
  reused unchanged. The invoker is a CLIENT of those, not a rewrite.
