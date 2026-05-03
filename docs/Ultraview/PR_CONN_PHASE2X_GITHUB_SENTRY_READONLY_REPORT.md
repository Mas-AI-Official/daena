# PR-CONN-PHASE2X-GITHUB-SENTRY-READONLY — Report

**Branch:** `rebuild-connections-mcp-runtime`
**Commit:** _to be filled in after squash_
**Date:** 2026-05-03
**Sprint:** DAENA-AUTONOMOUS-LOCAL-PRODUCTION-SPRINT (PR-2 of 4)

---

## 1. Goal

Promote four more read-only Phase 2 skills from `planned_only` to
`mcp_tool` real execution:

| Plugin | Skill | MCP tool invoked | Auth surface |
|---|---|---|---|
| `mcp-github` | `summarize_repo` | `get_repository` | token (in MCP env, never crosses executor) |
| `mcp-github` | `triage_issues` | `list_issues` (state=open pinned) | token |
| `mcp-github` | `inspect_ci_failure` | `get_workflow_run_logs` | token |
| `mcp-sentry` | `summarize_errors` | `list_issues` | OAuth/token (in MCP env) |

These four are higher risk than PR-1's filesystem+huggingface
because they involve auth tokens. The token NEVER crosses the
executor boundary — it lives in the MCP server process env via
`GITHUB_PERSONAL_ACCESS_TOKEN` / `SENTRY_AUTH_TOKEN`. The executor
forwards only the operator-supplied scope inputs (owner, repo,
project_slug, time_window).

---

## 2. Hard rules — all honored

| Rule | Enforced? |
|---|---|
| Read-only only | YES — `read_only=True` on every entry, defense-in-depth check at execute-time |
| Token values never shown | YES — `token`/`secret`/`auth`/`password` substrings forbidden in arguments dict (asserted by `test_promoted_github_triage_issues_dispatches_state_open`) |
| No issue creation | YES — only `get_repository` / `list_issues` / `get_workflow_run_logs` are wired; explicit forbidden-write list (`test_pr2_no_github_write_skills_promoted`) catches stealth additions like `create_issue` / `merge_pull_request` |
| No repo edits | YES — same forbidden-write guard |
| No comments | YES — `add_comment` in forbidden list |
| No branch/PR writes | YES — `create_branch` / `merge_pull_request` in forbidden list |
| No external messages | YES — Sentry/GitHub MCPs don't send messages on these read tools |
| Tests required | YES — 11 new tests, 50/50 in `test_skill_executor_phase2.py` pass |

---

## 3. Files changed

### `backend/app/services/connection_v2/skill_executor.py`

- Header docstring extended with PR-2 entry block
- 4 entries flipped to `execution_mode="mcp_tool"` (3 GitHub + 1 Sentry)
- 2 new `_PLUGIN_TO_SERVER_KEY` candidate-tuple entries:
  - `mcp-github` → `('github', 'github-mcp', 'github-mcp-server', 'mcp-github', '@modelcontextprotocol/server-github')`
  - `mcp-sentry` → `('sentry', 'sentry-mcp', 'mcp-sentry', '@sentry/mcp-server')`
- 4 new arg builders:
  - `_args_github_get_repository` — forwards owner+repo
  - `_args_github_list_issues` — forwards owner+repo, **pins `state="open"`** (read-narrowing — never asks GitHub for closed/all history)
  - `_args_github_workflow_run_logs` — forwards owner+repo+run_id
  - `_args_sentry_list_issues` — forwards organizationSlug+projectSlug+`query=age:-{time_window}` (read-narrowing — Sentry MCP scopes by org/project AND age window)
- 4 new entries in `_ARG_BUILDERS` dispatch dict

### `backend/tests/test_skill_executor_phase2.py`

- 4 new entries in `PROMOTED_TO_MCP_TOOL` registry
- 3 new invariant guards:
  - `test_pr2_promotion_set_is_exactly_github_and_sentry` — pins this PR's promoted set
  - `test_pr2_no_github_write_skills_promoted` — name-list defense for `create_issue` / `merge_pull_request` / `create_branch` / etc.
  - `test_pr2_no_sentry_write_skills_promoted` — name-list defense for `assign_issue` / `resolve_issue` / `create_bug_task` / etc.
- 6 new arg-builder + server-key tests
- 2 new E2E mocked-invoker tests:
  - `test_promoted_github_triage_issues_dispatches_state_open` — proves the right tool name + `state=open` arg AND no token-shaped fields in the arguments dict
  - `test_promoted_sentry_summarize_errors_query_window` — proves `projectSlug` + `query=age:-30d` derived from operator inputs
- New `callable_slack_v2_row` fixture for tests that need a still-PLANNED skill subject (after PR-2 promoted github)
- 2 existing tests retargeted from `mcp-github:summarize_repo`/`triage_issues` (now real-exec) to `mcp-slack:summarize_channel` (still planned). Their semantic intent (planned-path verification) preserved exactly.

### `docs/Ultraview/PR_CONN_PHASE2X_GITHUB_SENTRY_READONLY_REPORT.md`

(this file)

### `docs/Ultraview/SPRINT_LOG_DAENA_LOCAL_PROD.md`

PR-2 row updated.

---

## 4. Test result (50/50)

```
$ .venv/Scripts/python.exe -m pytest tests/test_skill_executor_phase2.py
============================= 50 passed in 2.64s ==============================
```

PR-1 was 39 tests. PR-2 adds 11 new tests, retargets 2, and the
49+ pre-existing assertions still hold. The PROMOTED_TO_MCP_TOOL
guard catches stealth promotions in code review.

---

## 5. Live verification (in-process E2E)

Backend running via `scripts/start-backend-dev.bat`. GitHub MCP is
NOT in the user's `claude_desktop_config.json`, so `_resolve_mcp_server_key`
returns the first candidate (`'github'`) without finding it installed.

```python
result = await ex.execute(
    plugin_id='mcp-github', skill_id='triage_issues',
    tenant_id=tid, user_id=uid,
    operator_inputs={'repo_owner':'anthropic','repo_name':'claude-code'},
)
```

**Output:**
```
STATUS:           needs_connection
BLOCKED_REASON:   mcp_not_installed
SUMMARY[:240]:    Plugin mcp-github maps to MCP server 'github' but that
                  server is not installed in the local MCP registry.
                  Install it via the Connections > Plugins UI, then retry.
```

**This is correct cascading behavior:** `needs_connection` (install the
MCP) is distinct from `blocked(mcp_tool_error)` (MCP installed but call
failed — what HF returned in PR-1). The operator can take different
actions per case.

---

## 6. What the operator will see after this PR

| Skill | Without GitHub/Sentry MCP installed | With MCP installed and token configured |
|---|---|---|
| `mcp-github:summarize_repo` | `needs_connection` — modal points at Plugins UI | `executed` — repo metadata summary |
| `mcp-github:triage_issues` | `needs_connection` | `executed` — open issues list (state=open enforced by executor) |
| `mcp-github:inspect_ci_failure` | `needs_connection` | `executed` — workflow run logs |
| `mcp-sentry:summarize_errors` | `needs_connection` | `executed` — issue list scoped to project + age window |

For all OTHER allowlisted skills (Gmail, Drive, Slack, DBs), `status="planned"` still returns. No change.

---

## 7. Read-narrowing decisions (security note)

Two arg builders pin extra constraints to keep the read tightly scoped:

- **`_args_github_list_issues`** pins `state="open"`. Without this, the operator could ask for `state="all"` and pull thousands of closed issues — that's a Phase 3 scope. Open-only matches the operator-visible "triage" intent.
- **`_args_sentry_list_issues`** wraps the `time_window` operator input as Sentry's `query=age:-{window}` filter (e.g. `age:-7d`). Without this, the operator could ask for "all time" and pull a project's entire error history. Age-window matches the operator-visible "summarize errors" intent.

Both pinnings are tested (`test_arg_builder_github_triage_issues_pins_state_open`, `test_arg_builder_sentry_summarize_errors`).

---

## 8. What did NOT change

- All other 12 allowlist entries stay `planned_only` (Gmail, Drive, Slack, DBs)
- No new dependencies, no npm/pip install, no Docker activity
- No production deploy, no Cloud Run write, no `vault --apply`
- No `USE_CONNECTION_REGISTRY_V2` flip
- No secret read/print/grep/log/commit
- Frontend SkillExecuteModal contract unchanged
- The 4 promoted GitHub+Sentry entries' `target_tool` strings unchanged from Phase 2 (`get_repository`, `list_issues`, `get_workflow_run_logs`)

---

## 9. Operator action items (non-blocking, deferred)

- Install `@modelcontextprotocol/server-github` MCP via Plugins UI; configure `GITHUB_PERSONAL_ACCESS_TOKEN` env (read-only scope: `public_repo` + `read:org`)
- Install `@sentry/mcp-server` MCP via Plugins UI; configure `SENTRY_AUTH_TOKEN` + `SENTRY_HOST`

Until installed, all 4 promoted skills return `needs_connection` with the install instruction.

---

## 10. Branch state after PR

```
<this commit>  canonicalization: execute GitHub and Sentry read-only skills
7d370d4        docs: pin PR-1 commit hash and update sprint log
bdb1ca8        canonicalization: execute filesystem and HuggingFace read-only skills
5c0b4f2        docs: pin launcher stability report commit hash
8544e48        chore: stabilize local backend launcher on Windows
```

Sprint state: PR-2 SHIPPED. Continuing autopilot to PR-3 (OAuth refresh + disconnect).
