# PR-CONN-PHASE2X-GMAIL-DRIVE-READONLY -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** (to be pinned)
**Date:** 2026-05-03
**Sprint:** DAENA-LOCAL-USABILITY-SPRINT-4 (PR-2 of 5)

---

## 1. Goal

Promote the 4 Gmail/Drive read-only Phase 2 entries to
`execution_mode="mcp_tool"` now that
`PR-CONN-OAUTH-EXECUTOR-WIRE-UP` (Sprint-4 PR-1) wired
`OAuthInvoker` into `SkillExecutor._execute_real_oauth`.

| Plugin | Skill | Invoker method | Promoted? |
|---|---|---|---|
| `app-gmail` | `summarize_unread` | `messages.list_unread` (no inputs) | **PROMOTED** |
| `app-gmail` | `search_email_context` | `messages.search` (`query`) | **PROMOTED** |
| `app-google-drive` | `find_documents` | `files.list` (no inputs, capped 30) | **PROMOTED** |
| `app-google-drive` | `summarize_file` | `files.get_metadata` (`file_id`) -- METADATA ONLY | **PROMOTED** |

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| Read-only only | YES -- all 4 entries `read_only=True`; allowlist invariant + new `test_sprint4_no_gmail_drive_write_skills_promoted` (16-name forbidden list) defends |
| Gmail: no send / draft / label modify / delete | YES -- only list_unread + search method ids in OAuth invoker; `send_message`, `draft_reply`, `modify_label`, `trash_message` etc. all in forbidden list |
| Drive: no upload / update / delete / permission changes | YES -- only files.list + files.get_metadata; `files.create`, `files.update`, `files.delete`, `permissions.*`, etc. all in forbidden list |
| Response caps required | YES -- inherited from OAuthInvoker (Sprint-3 PR-4): byte cap 64KB default, item caps per method (Drive list=30, Gmail messages=20, metadata=8KB/1) |
| Query / time / file limits required | YES -- Gmail: hardcoded q="is:unread" + maxResults=20; Drive list: pageSize=30 (no operator query); Drive metadata: file_id only, byte cap 8KB |
| No full file content unless capped and safe | YES -- `summarize_file` deliberately routes to `files.get_metadata` not get_content; reads_summary explicitly notes body summarization arrives in a follow-up PR with size + permission caps |
| If token missing or OAuth not connected, return needs_connection | YES -- Sprint-4 PR-1 wireup translates `OAuthCredentialsMissingError` and missing-instance to `needs_connection / oauth_credentials_missing` and `needs_connection / oauth_not_connected` respectively |
| Tests proving Gmail/Drive no longer planned | YES -- `test_sprint4_gmail_and_drive_now_promoted` is the inverse of the Sprint-2 PR-3 invariant |
| Update old invariant that kept Gmail/Drive planned | YES -- the Sprint-2 PR-3 `test_pr3_gmail_and_drive_remain_planned_only` is REPLACED with `test_sprint4_gmail_and_drive_now_promoted` (asserts `mcp_tool` instead of `planned_only`) |

---

## 3. Honest scope notes (operator-visible)

### Drive `find_documents`: no operator query (yet)

The Sprint-3 PR-4 `OAuthInvoker.files.list` does NOT accept an
operator `q` parameter. Drive's q syntax has injection surface that
needs a dedicated PR (allowlisted q-syntax patterns: `name contains
'foo'`, `mimeType =`, `modifiedTime >`, etc.). For PR-2 the skill
returns the first 30 files in Drive's default ordering (most recent).

The reads_summary explicitly notes this so the operator sees the
limit in the drawer. Future PR will add safe q-syntax support.

### Drive `summarize_file`: metadata only (not body)

The Sprint-3 PR-4 `OAuthInvoker.files.get_metadata` deliberately
holds back the body-content path because content download has its
own size + permission surface. For PR-2 the skill returns the file's
name + mimeType + size + modifiedTime.

The skill_id stays `summarize_file` for catalog stability; the
reads_summary explains what gets returned today vs. what's coming.

### Gmail `messages.search`: no time_window field (operator builds it)

Gmail's `q` syntax accepts time filters inline (`newer_than:7d`,
`after:2024/01/01`, etc.). PR-2 drops the separate `time_window`
required input -- the operator constructs the full Gmail q string.
This avoids dual-encoding ambiguity.

---

## 4. Files changed

### `backend/app/services/connection_v2/skill_executor.py`

* 4 Gmail/Drive entries flipped to `execution_mode="mcp_tool"`.
* `target_tool` strings aligned to `OAuthInvoker.OAUTH_METHOD_ALLOWLIST`:
  - `app-gmail:summarize_unread` -> `messages.list_unread`
  - `app-gmail:search_email_context` -> `messages.search`
  - `app-google-drive:find_documents` -> `files.list`
  - `app-google-drive:summarize_file` -> `files.get_metadata`
    (note: was `files.get_content` -- changed to metadata-only per
    OAuth invoker scope decision)
* `required_inputs` aligned with invoker contracts:
  - Gmail summarize_unread: `()` (was `("label_or_query", "time_window")`)
  - Gmail search: `("query",)` (was `("query", "time_window")`)
  - Drive find: `()` (was `("query", "folder_id_or_root")`)
  - Drive summarize: `("file_id",)` (was `("file_id_or_url",)`)
* `reads_summary` updated for honesty: explicitly notes scope limits
  + future-PR placeholders.

### `backend/tests/test_skill_executor_phase2.py`

* `PROMOTED_TO_MCP_TOOL`: 4 new entries tagged with PR id.
* `test_pr3_gmail_and_drive_remain_planned_only` REPLACED by:
  - `test_sprint4_gmail_and_drive_now_promoted` -- asserts mcp_tool + oauth surface
  - `test_sprint4_gmail_drive_target_tools_match_invoker_allowlist` -- pins target_tool / method_id alignment
  - `test_sprint4_no_gmail_drive_write_skills_promoted` -- 16-name forbidden write list
  - `test_sprint4_promotion_set_is_exactly_four` -- PR-2 promotion set drift defender
* `callable_planned_v2_row` fixture retargeted from Drive to mcp-postgres
  (mcp-postgres stays planned_only by Sprint-3 PR-3 design; it is the
  new generic still-planned subject for these tests).
* 2 retargeted tests:
  - `test_allowlisted_callable_skill_returns_planned`
  - `test_audit_row_records_outcome_and_no_secret_values`

### `backend/tests/test_oauth_invoker.py`

* `test_phase2_oauth_entries_still_planned` REPLACED by
  `test_phase2_oauth_entries_now_route_through_invoker` -- pins that
  every promoted oauth entry has a matching method in the invoker
  allowlist.

---

## 5. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_skill_executor_phase2.py tests/test_oauth_invoker.py tests/test_skill_executor_oauth_wireup.py
101 passed in 5.42s
```

Test growth across Sprint-4 PR-2:
* End of Sprint-4 PR-1: 64 phase2 + 21 oauth_invoker + 13 wireup = 98
* PR-2 adds: 3 net new (4 added: now_promoted / target_tools_match /
  no_writes / promotion_set_exact; 1 deleted: pr3_remain_planned).
* Total in scope: **101 passing**

---

## 6. Live verification (deferred to operator)

The 4 promoted skills will fire end-to-end ONLY when:

1. Operator connects Gmail / Drive via the Plugins UI OAuth flow
   (Settings -> OAuth Clients -> add Google client, then per-plugin
   Connect). This persists `ConnectorInstance.credentials.access_token`
   + `refresh_token` for the user.
2. The connector instance is `status=CONNECTED` (matches
   `_find_oauth_instance` filter).
3. The OAuth method's required_inputs are supplied (only Gmail
   search + Drive get_metadata need any).

Without the OAuth connection, the executor returns
`needs_connection / oauth_not_connected` cleanly -- never fakes a
result.

---

## 7. What did NOT change

* OAuth credential storage / encryption / refresh path -- reused unchanged.
* `_execute_real_oauth` itself -- shipped in PR-1.
* `OAuthInvoker.OAUTH_METHOD_ALLOWLIST` -- already had the 4 method ids.
* No new dependencies, no install, no production deploy.
* `vault --apply` -- not touched.
* No Phase 3 write surfaces enabled.
* Calendar (`app-google-calendar`) entries -- still planned_only; PR-2
  scope was Gmail + Drive only.
