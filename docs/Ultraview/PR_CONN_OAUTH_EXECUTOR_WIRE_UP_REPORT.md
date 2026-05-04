# PR-CONN-OAUTH-EXECUTOR-WIRE-UP -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** (to be pinned)
**Date:** 2026-05-03
**Sprint:** DAENA-LOCAL-USABILITY-SPRINT-4 (PR-1 of 5)

---

## 1. Goal

Wire `OAuthInvoker.invoke()` (Sprint-3 PR-4 foundation) into
`SkillExecutor.execute()` so that an allowlist entry with
`backend_surface="oauth"` AND `execution_mode="mcp_tool"` dispatches
to a real OAuth GET path. This PR ships the WIRING ONLY -- no Phase 2
OAuth allowlist entry is yet promoted; PR-2 of this sprint flips
Gmail/Drive.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| No Gmail/Drive promotion in this PR | YES -- Sprint-2 invariant `test_pr3_gmail_and_drive_remain_planned_only` STILL passes |
| No send email | YES -- only OAuth GET methods exist in OAUTH_METHOD_ALLOWLIST (Sprint-3 PR-4) |
| No file modify/delete | YES -- only `files.list` + `files.get_metadata` |
| No browser | YES -- pure server-side httpx GET |
| No external messages | YES |
| No token leak | YES -- `extra_audit_fields` HARDCODES rejection of any field name containing `access_token`, `refresh_token`, `bearer`, `secret`. Defense-in-depth test walks the persisted audit row and asserts no token-shaped value appears |
| Token refresh on 401 only through existing refresh path | YES -- `OAuthInvoker.invoke()` uses `ConnectorOAuthService.refresh_token` (the existing path); executor never touches refresh logic itself |
| Audit row follows existing skill_invocation contract | YES -- routes through `_record_real_outcome`; same action_type, same result/risk/governance_tier values |
| No raw token or response body stored in audit | YES -- payload is JSON-serialized with `default=str`, capped at 8KB BEFORE hashing, only the SHA256[:8] prefix lands in the audit row |

---

## 3. Surface area

### `backend/app/services/connection_v2/skill_executor.py`

**Dispatch change in `SkillExecutor.execute()`** (Step 5):

```python
if entry.execution_mode == "mcp_tool":
    if entry.backend_surface == "oauth":
        return await self._execute_real_oauth(...)
    return await self._execute_real_mcp_tool(...)
```

Backwards-compatible: every existing mcp + mcp_tool entry still
routes to `_execute_real_mcp_tool` unchanged. Defense test
`test_dispatch_mcp_mcp_tool_still_routes_to_mcp_branch` pins this.

**New method `_execute_real_oauth`** mirrors the MCP path's outcome
shape:

| Invoker outcome | final_status | blocked_reason |
|---|---|---|
| Method not in allowlist | blocked | oauth_method_not_allowlisted |
| No ConnectorInstance | needs_connection | oauth_not_connected |
| Missing access_token | needs_connection | oauth_credentials_missing |
| 401 -> refresh -> 401 | needs_connection | oauth_auth_expired |
| Vendor 5xx | blocked | oauth_vendor_error |
| Network error / timeout | blocked | oauth_network_error / oauth_timeout |
| Response too large | blocked | oauth_response_too_large |
| Success | executed | "" |

**New helper `_find_oauth_instance`** -- maps OAuth provider key to
seeded Connector.name via `_OAUTH_PROVIDER_TO_CONNECTOR_NAME`, then
finds the user's CONNECTED ConnectorInstance for that connector.
DISCONNECTED / ARCHIVED instances return None (force re-connect).

**New helper `_summarize_oauth_payload`** -- shape-first summary of
the response. Renders `N file(s)` / `N message id(s)` + first few
labels. NEVER includes message bodies, file contents, or any header
that could leak PII.

**New module-level `_OAUTH_PROVIDER_TO_CONNECTOR_NAME`** mapping:

```python
{
    "gmail": "Gmail",
    "google-drive": "Google Drive",
    "google-calendar": "Google Calendar",
    "slack": "Slack",
}
```

`test_oauth_provider_mapping_covers_invoker_allowlist` pins that
every provider used in `OAUTH_METHOD_ALLOWLIST` has a mapping.

**`_record_real_outcome` extended with `extra_audit_fields`** --
optional dict for the OAuth path to carry `oauth_provider`,
`oauth_refreshed`, `oauth_truncated`, `oauth_status_code`. The
pass-through HARDCODES rejection of any field name containing
`access_token` / `refresh_token` / `bearer` / `secret` substring,
even if a future contributor accidentally tries to log one.

### `backend/tests/test_skill_executor_oauth_wireup.py` (NEW)

13 tests across 4 logical sections:

1. **Dispatch routing (2 tests)** -- backend_surface=oauth + mcp_tool routes to OAuth branch; backend_surface=mcp + mcp_tool still routes to MCP branch.
2. **`_execute_real_oauth` direct outcome (7 tests)**:
   - no instance -> needs_connection / oauth_not_connected
   - missing access_token -> needs_connection / oauth_credentials_missing
   - happy path -> executed + summary references message ids
   - 401-refresh-200 -> executed (2 GET calls confirmed)
   - 401-refresh-401 -> needs_connection / oauth_auth_expired
   - response too large -> blocked / oauth_response_too_large
   - vendor 503 -> blocked / oauth_vendor_error
3. **Token-leak audit defense (2 tests)** -- happy path executes, then walks every string in the persisted audit row's action_params and asserts that the seeded access_token / refresh_token / "Bearer " / "ya29.c.fake" / "1//0g_fake" / token-named keys do NOT appear; second test confirms `oauth_provider` + `oauth_refreshed` ARE recorded.
4. **Provider mapping consistency (2 tests)** -- every provider in `OAUTH_METHOD_ALLOWLIST` has a Connector mapping; the forbidden-substring filter catches token-shaped keys without false positives.

---

## 4. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_skill_executor_oauth_wireup.py
13 passed in 0.39s

$ .venv/Scripts/python.exe -m pytest tests/test_skill_executor_phase2.py tests/test_oauth_invoker.py tests/test_skill_executor_oauth_wireup.py
98 passed in 3.08s
```

Test growth across Sprint-4 PR-1:
* End of Sprint-3: 64 phase2 + 21 oauth_invoker = 85
* PR-1 of Sprint-4 adds: 13 new wireup tests = 98 total in scope

The Sprint-2 invariant `test_pr3_gmail_and_drive_remain_planned_only`
STILL passes -- proof that no premature promotion sneaked in.

---

## 5. What ships, what doesn't

### Ships
* `_execute_real_oauth` method -- full OAuth-mode skill execution path
* `_find_oauth_instance` helper -- provider -> connector -> instance
* `_summarize_oauth_payload` -- shape-first PII-safe summary
* `extra_audit_fields` extension to `_record_real_outcome` with
  token-name defense
* Provider -> Connector mapping for Gmail / Drive / Calendar / Slack
* 13 new tests across 4 logical sections

### Does NOT ship in this PR (PR-2 territory)
* `app-gmail:summarize_unread` promotion (still planned_only)
* `app-gmail:search_email_context` promotion (still planned_only)
* `app-google-drive:find_documents` promotion (still planned_only)
* `app-google-drive:summarize_file` promotion (still planned_only)
* Update of `test_pr3_gmail_and_drive_remain_planned_only` invariant
  -- PR-2 will rename + flip its assertion to "promoted" once the
  matching `target_tool` strings line up with OAUTH_METHOD_ALLOWLIST.

### Promotion-readiness checklist for PR-2

For each Gmail/Drive entry that PR-2 promotes, the entry's
`target_tool` MUST equal a `method_id` in `OAUTH_METHOD_ALLOWLIST`.
The current Phase 2 allowlist values (and their required mappings):

| Phase 2 entry target_tool | OAUTH_METHOD_ALLOWLIST method_id | Action for PR-2 |
|---|---|---|
| `app-gmail:summarize_unread` -> `messages.list_unread` | `app-gmail:messages.list_unread` | rename Phase 2 target_tool from current value to `messages.list_unread` |
| `app-gmail:search_email_context` -> `messages.search` | `app-gmail:messages.search` | same |
| `app-google-drive:find_documents` -> `files.list` | `app-google-drive:files.list` | same |
| `app-google-drive:summarize_file` -> `files.get_metadata` | `app-google-drive:files.get_metadata` | same |

PR-2 will update these target_tool strings AND flip
`execution_mode="planned_only"` -> `"mcp_tool"` AND add the 4 keys to
`PROMOTED_TO_MCP_TOOL` AND replace the Sprint-2 invariant.

---

## 6. What did NOT change

* No backend route added (the executor's existing `/connections/v2/skills/execute` already routes through `SkillExecutor.execute()`).
* No frontend change.
* No vault, credentials store, or OAuth client config touched.
* No production deploy, no V2 flag flip, no secret read.
* No new dependencies.
* The Sprint-2 invariant `test_pr3_gmail_and_drive_remain_planned_only` actively defends against premature promotion -- it stays green after this PR.
