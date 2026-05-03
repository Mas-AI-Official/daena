# PR-CONN-PHASE2X-SLACK-GMAIL-DRIVE-READONLY — Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** `8541c30`
**Date:** 2026-05-03
**Sprint:** DAENA-LOCAL-USABILITY-SPRINT-2 (PR-3 of 4)

---

## 1. Goal

Promote the Slack/Gmail/Drive read-only skills if their backend
surface can safely execute today. Per the founder brief: "If
OAuth/API shape is not proven, return needs_connection/planned, not
fake executed."

**Result of analysis:**

| Plugin | Skill | Surface | Promoted? |
|---|---|---|---|
| `mcp-slack` | `summarize_channel` | `mcp` (stdio) | YES — same path as PR-1/PR-2 |
| `mcp-slack` | `find_decisions` | `mcp` (stdio) | YES — same path |
| `app-gmail` | `summarize_unread` | `oauth` (HTTP) | NO — see §3 |
| `app-gmail` | `search_email_context` | `oauth` (HTTP) | NO — see §3 |
| `app-google-drive` | `find_documents` | `oauth` (HTTP) | NO — see §3 |
| `app-google-drive` | `summarize_file` | `oauth` (HTTP) | NO — see §3 |

---

## 2. Hard rules — all honored

| Rule | Enforced? |
|---|---|
| Read-only only | YES — both Slack skills are channel-history reads, no write surface |
| No sending messages | YES — `_args_slack_conversations_history` only carries `channel` + `limit`; no `text`/`message`/`user` arg ever |
| No drafting external emails beyond local summary | YES — Gmail intentionally NOT promoted; Phase 1 chat-draft path stays the only Gmail read |
| No file writes / no deletes / no browser / no payment | YES — Slack MCP's `conversations_history` doesn't touch any of these |
| If OAuth/API shape not proven → `needs_connection`/`planned` | YES — Gmail + Drive STAY `planned_only`; new test `test_pr3_gmail_and_drive_remain_planned_only` pins this |
| Tests required | YES — 7 new tests, 57/57 phase2 + 26/26 connections = 83/83 |

---

## 3. Why Gmail + Drive stayed planned

`mcp-slack`'s `backend_surface` in the allowlist is `"mcp"` — the
existing `_execute_real_mcp_tool` path (via `mcp_invoker.call_server_tool`)
handles it identically to filesystem/HF/GitHub. No new infrastructure.

`app-gmail` and `app-google-drive` declare `backend_surface="oauth"`,
which means an OAuth-mode executor that:
- Loads the operator's stored OAuth tokens from `ConnectorInstance.credentials`
- Decrypts via the vault
- Calls Google's REST API directly with `Bearer <access_token>` header
- Translates the planned `target_tool` (e.g. `messages.list_unread`,
  `files.list`) into actual Google API endpoints + query strings
- Handles pagination + token-refresh-on-401

**None of that exists yet.** Promoting these skills today would mean
the executor would call `_execute_real_mcp_tool`, which would call
`_resolve_mcp_server_key("app-gmail")` → returns nothing → result =
`needs_connection`, claiming "MCP not installed." That's a LIE because
there's no MCP for app-gmail at all — the surface is OAuth.

The honest behavior (per project Rule 17) is to leave them
`planned_only` until an `OAuthInvoker` ships. The new test
`test_pr3_gmail_and_drive_remain_planned_only` fails the moment a
future PR tries to flip them without first building the OAuth path.

**Suggested follow-up PRs (out of this sprint's scope):**
- `PR-CONN-OAUTH-INVOKER` — build the OAuth-mode executor; add
  Google API calls for the 4 target tools (messages.list_unread,
  messages.search, files.list, files.get_content)
- `PR-CONN-PHASE2X-GMAIL-DRIVE-READONLY` — promote the 4 Gmail+Drive
  skills after the invoker is proven, with read-narrowing pinnings
  (e.g. message count caps, file size caps, date filters)

---

## 4. Files changed

### `backend/app/services/connection_v2/skill_executor.py`

- Header docstring extended with PR-3 entry block (and explicit note that Gmail+Drive STAY planned)
- 2 entries flipped to `execution_mode="mcp_tool"` (`mcp-slack:summarize_channel`, `mcp-slack:find_decisions`)
- `_PLUGIN_TO_SERVER_KEY` got `mcp-slack: ('slack', 'slack-mcp', 'mcp-slack', '@modelcontextprotocol/server-slack')`
- New `_args_slack_conversations_history` arg builder with bounded-limit heuristic:
  - Numeric input → `limit = clamp(int, 1, 200)`
  - Time-window string (e.g. `"7d"`) → safe default `limit = 100`
  - Wraps the read narrow (Slack MCP doesn't accept wall-clock time windows directly)
- 2 new entries in `_ARG_BUILDERS` (both Slack skills share `_args_slack_conversations_history`)

### `backend/tests/test_skill_executor_phase2.py`

- 2 new entries in `PROMOTED_TO_MCP_TOOL` registry (Slack only)
- New invariant tests:
  - `test_pr3_promotion_set_is_exactly_slack_two_skills` — pins exact promoted set
  - `test_pr3_gmail_and_drive_remain_planned_only` — explicit defense; fails if Gmail/Drive ever flip without OAuth executor
  - `test_pr3_no_slack_write_skills_promoted` — name-list defense for `draft_reply`/`send_message`/`post_message`/`extract_tasks`/etc.
- 2 new arg-builder tests (`test_arg_builder_slack_summarize_channel_uses_limit_heuristic`, `test_arg_builder_slack_find_decisions_uses_same_history_call`)
- 1 new server-key test (`test_resolve_server_key_slack_default_first`)
- 1 new E2E mocked-invoker test (`test_promoted_slack_summarize_channel_dispatches_history`) — proves channel + bounded limit + no token-shaped fields in args
- Renamed `callable_slack_v2_row` fixture → `callable_planned_v2_row` and switched it to use Drive (`oauth-google-drive`) since Slack is now promoted. Now uses `ConnectionKind.OAUTH_APP` to match catalog. Same intent: provide a callable plugin pointing at a still-PLANNED skill for generic planned-path tests.
- 2 existing tests retargeted from `mcp-slack:summarize_channel` (now real-exec) to `app-google-drive:find_documents` (still planned). Their semantic intent (planned-path verification) preserved.

---

## 5. Read-narrowing decision (Slack)

**Why a bounded `limit` instead of forwarding `time_window` directly:**

The Slack `conversations_history` MCP tool accepts `oldest`/`latest` Unix timestamps but not human time strings. Translating `"7d"` → `oldest=now-604800s` would require timezone-aware date math at the executor layer. Instead, the executor uses a fixed `limit` cap (max 200, default 100) so:

- Numeric operator inputs pass straight through (`"50"` → 50)
- Out-of-range values clamp safely (`"9999"` → 200)
- Time-window strings collapse to the safe default (`"7d"` → 100)

This keeps the read narrow and the executor side simple. A future PR can add timestamp-window support if the operator-visible UX warrants it.

---

## 6. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_skill_executor_phase2.py tests/test_connections.py
83 passed in 30.08s

$ npx tsc --noEmit
(no output -- clean, no change)
```

Test growth across the sprint:
- Sprint-1 ended: 76/76
- PR-3 of Sprint-2 adds: 7 new tests + 2 retargeted = 83/83

---

## 7. Live verification (deferred to operator)

The Slack MCP isn't currently in the user's `claude_desktop_config.json`. So the Slack promoted skills will return `needs_connection` until installed:
1. Open Plugins UI → find Slack card → click Install
2. Provide `SLACK_BOT_TOKEN` (from your Slack app's OAuth & Permissions page; required scopes: `channels:history`, `channels:read`)
3. Click Test → expected `tools/list` includes `conversations_history`, `conversations_list`, `chat_postMessage` (write — blocked by allowlist)
4. Run `mcp-slack:summarize_channel` with `channel = "C12345"` (an actual channel ID) and `time_window = "100"` (last 100 messages)

Documented in `MCP_SETUP_GUIDE_FOR_PROMOTED_SKILLS.md` (PR-2 of this sprint) — Slack section can be extended in a follow-up doc PR.

---

## 8. What did NOT change

- All other 14 allowlist entries stay `planned_only` (Gmail + Drive + databases)
- No new dependencies, no install
- No production deploy
- No `USE_CONNECTION_REGISTRY_V2` flip
- No `vault --apply`
- No secret read/print/grep/log/commit
- No external messages
- No browser automation
- The 4 Gmail/Drive entries' `target_tool` strings unchanged

---

## 9. Branch state after PR

```
<this commit>  canonicalization: execute Slack Gmail Drive read-only skills
d3ee192        docs: pin PR-2 commit hash and update sprint-2 log
46e1db6        docs/ui: clarify MCP setup for promoted read-only skills
8923f6d        docs: pin PR-1 commit hash and update sprint-2 log
ce6e244        fix: wire OAuth lifecycle actions into Connections UI
```

Sprint-2 state: PR-3 SHIPPED. Continuing autopilot to PR-4 (usability smoke).
