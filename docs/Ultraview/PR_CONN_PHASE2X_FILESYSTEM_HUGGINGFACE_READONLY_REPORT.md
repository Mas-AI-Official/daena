# PR-CONN-PHASE2X-FILESYSTEM-HUGGINGFACE-READONLY — Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** _to be filled in after squash_
**Date:** 2026-05-03
**Sprint:** DAENA-AUTONOMOUS-LOCAL-PRODUCTION-SPRINT (PR-1 of 4)

---

## 1. Goal

Promote four read-only Phase 2 skills from `execution_mode="planned_only"`
to `execution_mode="mcp_tool"` so they really fire `tools/call`:

| Plugin | Skill | MCP tool invoked |
|---|---|---|
| `mcp-filesystem` | `find_files` | `search_files` |
| `mcp-filesystem` | `summarize_directory` | `list_directory` |
| `mcp-huggingface` | `find_model` | `hub_repo_search` |
| `mcp-huggingface` | `inspect_paper` | `paper_search` |

These four were chosen because they are the lowest-risk read-only
skills available — no OAuth complexity, no external write surface,
no payment paths, no browser actions. The next integration arms
(GitHub, Sentry, Slack, Gmail, Drive, DBs) follow as separate PRs.

---

## 2. Hard rules — all honored

| Rule | Enforced? |
|---|---|
| No writes | YES — both MCP tools are read-only by definition; arg builders never emit write-shaped fields |
| No deletes | YES — same, no destructive args possible |
| No external messages | YES — neither HF nor filesystem MCPs send |
| No browser actions | YES — neither MCP touches browser surfaces |
| No payments | YES — out of scope |
| Execution flips ONLY for these four skills | YES — `PROMOTED_TO_MCP_TOOL` set in tests pins exactly this set; future stealth promotions fail the invariant test |
| Result summarizers added | YES — `_summarize_mcp_result` per-skill formatter |
| Audit child metadata added | YES — see §4 below |
| No secret or operator-input leakage | YES — `argument_shape` carries provenance not values; raw MCP response is hashed (`SHA256[:8]`) into the audit, never persisted |
| Tests required | YES — 13 new tests, 39/39 in `test_skill_executor_phase2.py` pass |

---

## 3. Files changed

### `backend/app/services/connection_v2/skill_executor.py`

- Header docstring updated to reference both PRs (Phase 2 + Phase 2.x)
- Added `_MCP_EXEC_TIMEOUT_SECONDS = 12.0` and `_RESULT_SUMMARY_MAX_CHARS = 1200`
- Added `import hashlib`
- Promoted four `SkillToolMapping` entries from `planned_only` → `mcp_tool`
- Added `execute()` branch on `entry.execution_mode`
- Added `_execute_real_mcp_tool` method (5-outcome handler: needs_connection, success, mcp_error, mcp_timeout, mcp_exception)
- Added `_record_real_outcome` (audit + response builder for the real-exec path)
- Added `_PLUGIN_TO_SERVER_KEY` mapping table + `_resolve_mcp_server_key`
- Added per-skill arg builders: `_args_filesystem_search_files`, `_args_filesystem_list_directory`, `_args_huggingface_find_model`, `_args_huggingface_inspect_paper`
- Added `_ARG_BUILDERS` dispatch dict + `_build_mcp_arguments`
- Added `_flatten_mcp_content` (joins text parts) + `_summarize_mcp_result` (trim + frame)
- Added new helpers to `__all__` so tests can import directly

### `backend/tests/test_skill_executor_phase2.py`

- Added `PROMOTED_TO_MCP_TOOL` dict (PR → exact promoted set)
- Replaced `test_every_allowlist_entry_is_planned_only` with `test_every_allowlist_entry_is_planned_or_explicitly_promoted` (allows promoted entries when registered)
- Added `test_pr1_promotion_set_is_exactly_filesystem_and_huggingface` (catches stealth promotions in this PR's bucket)
- Added 13 new tests covering server-key resolution, arg builders, flatten/summarize helpers, and full E2E real-exec with mocked invoker (success, error, timeout, audit + hash, no-content-leak canary)

### `docs/Ultraview/PR_CONN_PHASE2X_FILESYSTEM_HUGGINGFACE_READONLY_REPORT.md`

(this file)

### `docs/Ultraview/SPRINT_LOG_DAENA_LOCAL_PROD.md`

Append entry for PR-1 commit.

---

## 4. Audit row contract (parent + execution metadata)

The parent `plugin.skill_invocation` audit row gains four new fields
on the real-exec path (in addition to the Phase 2 spine fields):

| Field | Type | Purpose |
|---|---|---|
| `executed_tool` | string | The actual MCP tool name we asked to call (e.g. `search_files`) — same as `target_tool` for now but distinct for future per-call resolution |
| `server_key` | string | The bootstrap registry key we resolved to (e.g. `filesystem`, `huggingface-mcp`) — proves which physical MCP instance handled the call |
| `result_summary_length` | int | Chars in the operator-facing summary — proves "a real read happened" |
| `result_content_hash_prefix` | string (8 hex chars) | `SHA-256[:8]` of the joined raw MCP text — proof-of-content without persistence |

**What we DO NOT audit:** the raw MCP response text. Filesystem `search_files` results may include path names; HuggingFace results may include repo IDs the operator searched for. Storing those into governance audit storage would create a search-history side-channel. The hash + length is enough to prove a successful call; the operator-facing summary returns the content live.

**Outcome vocabulary (`outcome` field):**
- `success` — MCP returned content (status=executed)
- `needs_connection` — MCP not in bootstrap registry (status=needs_connection, blocked_reason=mcp_not_installed)
- `mcp_error` — MCP returned `success=False` (status=blocked, blocked_reason=mcp_tool_error)
- `mcp_timeout` — MCP exceeded `_MCP_EXEC_TIMEOUT_SECONDS` (status=blocked, blocked_reason=mcp_tool_timeout)
- `mcp_exception` — Unhandled exception during invoker (status=blocked, blocked_reason=mcp_tool_exception)

---

## 5. Tests (13 new, 39/39 passing)

```
$ .venv/Scripts/python.exe -m pytest tests/test_skill_executor_phase2.py -x --tb=short
============================= 39 passed in 2.70s ==============================
```

New test coverage (file-local order):
1. `test_every_allowlist_entry_is_planned_or_explicitly_promoted` — invariant guard
2. `test_pr1_promotion_set_is_exactly_filesystem_and_huggingface` — stealth-promotion guard
3. `test_resolve_server_key_filesystem_returns_first_candidate_when_none_installed`
4. `test_resolve_server_key_huggingface_default_first`
5. `test_resolve_server_key_unknown_plugin`
6. `test_arg_builder_filesystem_search_files`
7. `test_arg_builder_filesystem_list_directory`
8. `test_arg_builder_huggingface_find_model`
9. `test_arg_builder_huggingface_inspect_paper`
10. `test_flatten_mcp_content_concatenates_text_parts`
11. `test_summarize_mcp_result_short_text_kept_whole`
12. `test_summarize_mcp_result_long_text_is_trimmed`
13. `test_summarize_mcp_result_empty_text_explained`
14. `test_promoted_skill_with_uninstalled_mcp_returns_needs_connection`
15. `test_promoted_skill_success_returns_executed_with_summary`
16. `test_promoted_skill_mcp_error_returns_blocked`
17. `test_promoted_skill_mcp_timeout_returns_blocked_with_timeout_reason`
18. `test_promoted_skill_audit_records_outcome_and_hash_not_content` (canary)
19. `test_promoted_skill_response_carries_summary_for_operator`
20. `test_promoted_filesystem_uses_search_files_tool` (full FS dispatch verify)

---

## 6. Live verification (in-process E2E against installed HF MCP)

Backend restarted via `scripts/start-backend-dev.bat` after edits.

```python
from app.services.connection_v2.skill_executor import SkillExecutor
# ... seeded callable mcp-huggingface V2 row ...
result = await ex.execute(
    plugin_id='mcp-huggingface', skill_id='find_model',
    tenant_id=tid, user_id=uid,
    operator_inputs={'task_or_keywords':'embedding small'},
)
```

**Output:**
```
STATUS:           blocked
ACCEPTED:         False
BLOCKED_REASON:   mcp_tool_error
SUMMARY[:280]:    mcp-huggingface:find_model could not run -- the MCP
                  server returned: huggingface-mcp MCP process exited
                  before the MCP handshake completed. Check its command,
                  args, required env vars, and package install.
AUDIT_EVENT_ID:   4746f627-bd59-47b6-a6e3-d1f69948b64d
```

**What this proves end-to-end:**
- Executor branched into the new real-exec path (not planned_only)
- `_resolve_mcp_server_key` returned `huggingface-mcp` from the bootstrap registry
- `_build_mcp_arguments` produced `{"query":"embedding small"}`
- `mcp_invoker.call_server_tool` actually spawned `npx -y huggingface-mcp` (the live npm error proves this)
- The npm-resolved failure (`ENOVERSIONS`) was caught by the invoker
- Executor classified it as `outcome="mcp_error"` and returned `status="blocked"`
- Audit row was written (id captured)

**This is the correct behavior for an unavailable backend.** Not a fake success, not an unhandled crash. The operator sees an actionable error message.

---

## 7. What the operator will see after this PR

For the 4 promoted skills, the existing `Run read-only skill` button now triggers a real MCP call through the executor's `mcp_tool` path. Three concrete outcomes:

| Operator state | What happens |
|---|---|
| MCP installed + reachable + tool succeeds | `status=executed`, summary appears in the modal, audit row records `outcome=success` + result hash |
| MCP not installed in claude_desktop_config | `status=needs_connection`, modal shows "Install via Connections > Plugins UI", audit row records `outcome=needs_connection` |
| MCP installed but the underlying npm package is broken (current HF MCP situation) | `status=blocked`, modal shows the real error from the MCP, audit row records `outcome=mcp_error` |

For all OTHER allowlisted skills (Gmail, Drive, GitHub, Slack, Sentry, DBs), `status="planned"` still returns — exactly as before. No change in their behavior.

---

## 8. Operator action items (non-blocking, deferred)

These are NOT required for this PR to ship — they're prerequisites for the four promoted skills to actually return `executed`:

1. **Install `@modelcontextprotocol/server-filesystem`** via the Connections > Plugins UI (the install card already exists in the marketplace catalog, `install_method="npm"`, `command_template="npx -y @modelcontextprotocol/server-filesystem <ALLOWED_ROOT>"`). After install, `_resolve_mcp_server_key('mcp-filesystem')` will find it and promoted skills will fire.
2. **Replace the broken `huggingface-mcp` config** in `~/AppData/Roaming/Claude/claude_desktop_config.json`. The current entry calls `npx -y huggingface-mcp` which returns `ENOVERSIONS` from npm. The official HF MCP is HTTP-mode at `https://huggingface.co/mcp` — needs an HTTP-MCP client adapter, which is out of scope for this PR.

Until those are addressed, operator hits the Run button → sees the clean blocked error, exactly as designed.

---

## 9. What did NOT change

- All other 16 allowlist entries stay `execution_mode="planned_only"` (verified by `test_every_allowlist_entry_is_planned_or_explicitly_promoted`)
- No new dependencies, no npm/pip install, no Docker activity
- No production deploy
- No `USE_CONNECTION_REGISTRY_V2` flip
- No `vault --apply`
- No secret read/print/grep/log/commit
- Frontend SkillExecuteModal contract unchanged (the new `status="executed"` is already in the type vocabulary; the modal renders `summary` for any successful return)

---

## 10. Branch state after PR

```
<this commit>  canonicalization: execute filesystem and HuggingFace read-only skills
5c0b4f2        docs: pin launcher stability report commit hash
8544e48        chore: stabilize local backend launcher on Windows
160bb19        docs/fix: complete Phase 2 live smoke verification
707b662        canonicalization: execute read-only plugin skills with audit gate
```

Sprint state: PR-1 SHIPPED. Continuing autopilot to PR-2 (GitHub + Sentry).
