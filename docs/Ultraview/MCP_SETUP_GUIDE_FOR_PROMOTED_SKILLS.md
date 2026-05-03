# MCP Setup Guide — Promoted Read-Only Skills

**Purpose:** Get the four MCP servers installed locally so the
read-only skills shipped in Sprint-1 (PR-1 + PR-2) can return
`executed` instead of `needs_connection`.

**Audience:** Masoud, on his laptop, ~10 minutes total for all four.

**Prerequisites:**
- Daena backend + frontend running (see `DAENA_LOCAL_PRODUCTION_READY_SMOKE.md` Section 1 + 2)
- Node.js + npm available on PATH (for `npx`-based installs)
- Provider tokens ready where applicable (GitHub PAT, Sentry token, HF token if private repos needed)

---

## The 4-step flow (memorize this)

For every MCP below, the loop is the same:

```
Install  →  Test  →  Connected  →  Run skill
```

1. **Install**: open Daena Plugins UI → find the plugin card → click "Install". This writes a `mcpServers.<server_key>` entry into `~/AppData/Roaming/Claude/claude_desktop_config.json`. Daena's bootstrap registry picks it up on next refresh.
2. **Test**: in the same plugin drawer, click "Test" / "Probe". This spawns the MCP via stdio, runs the MCP `initialize` handshake, and lists `tools/list`. If it works, the truth-ladder dot for `reachable` + `callable` flips green.
3. **Connected**: the plugin card shows status `connected` with the truth-ladder fully lit. From here, skills tagged for this plugin become eligible for the Run button.
4. **Run skill**: in the plugin drawer, find a green-dot skill row → click "Run". Operator-input fields appear; fill them; click confirm. The executor calls the MCP and returns the operator-visible summary.

If any step fails, **STOP at that step** — the next step won't help.

---

## 1. Filesystem MCP

**Plugin card name in Daena UI:** "Filesystem" (id `mcp-filesystem`)

**npm package:** `@modelcontextprotocol/server-filesystem`

**Install command** (what Daena writes to `claude_desktop_config.json`):
```
npx -y @modelcontextprotocol/server-filesystem <ALLOWED_ROOT>
```
You provide `<ALLOWED_ROOT>` during the Install dialog. The MCP refuses operations outside that root — choose wisely.

**Recommended root for this dev machine:**
```
D:\Ideas\Daena
```
(Or a project subdirectory. Avoid `C:\Users` or your whole home — the MCP's read tools traverse everything inside the root.)

**Required env vars:** none.

**Auth:** none (it's local filesystem).

**Probe step:** click "Test" in the plugin drawer. Expected `tools/list` response includes:
- `read_file`, `read_multiple_files`, `list_directory`, `directory_tree`, `search_files`, `get_file_info`, `list_allowed_directories` (read tools)
- `write_file`, `edit_file`, `create_directory`, `move_file` (write tools — Daena's allowlist BLOCKS these in Phase 2.x)

**After install, the following promoted skills work:**
- `mcp-filesystem:find_files` — calls `search_files` with `{path, pattern}`
- `mcp-filesystem:summarize_directory` — calls `list_directory` with `{path}`

**Try it:**
- Skill: `find_files`
- Operator inputs: `root_path = "D:/Ideas/Daena"`, `name_or_glob = "*.md"`
- Expected result: list of paths to markdown files under the root.

**Common failures:**
- `npm error code ENOVERSIONS` → the package name in `args` is wrong. Check that `claude_desktop_config.json` has `args: ["-y", "@modelcontextprotocol/server-filesystem", "D:\\Ideas\\Daena"]`.
- `MCP process exited before handshake` → usually means npx couldn't fetch the package (network issue) or the path is invalid.

---

## 2. Hugging Face MCP

**Plugin card name in Daena UI:** "Hugging Face" (id `mcp-huggingface`)

**Hosted endpoint:** `https://huggingface.co/mcp` (HTTP MCP, not stdio)

**Important caveat:** the official HF MCP is HTTP-mode, not stdio. The current Daena `mcp_invoker` only speaks stdio. So even after "install", calls will fail until either (a) an HTTP-MCP adapter ships in Daena, or (b) you find a stdio-mode HF MCP package.

**Today's reality:** the npm package `huggingface-mcp` (the one currently in some users' `claude_desktop_config.json`) returns `npm error code ENOVERSIONS` — it doesn't exist on the npm registry. Calls return `blocked(mcp_tool_error)` with the npm error in the summary. This is correct cascading behavior — not a fake success.

**Required env vars (when wired):** `HF_TOKEN` (read-scope for private repos; public catalog calls work anonymously).

**Auth:** API token from `https://huggingface.co/settings/tokens` — read scope is sufficient for `find_model` + `inspect_paper`.

**Action item until HTTP MCP support lands:** leave the `huggingface-mcp` entry out of `claude_desktop_config.json`, or accept that the two promoted HF skills will return `blocked(mcp_tool_error)` consistently. This is documented behavior, not a regression.

**Promoted skills (when wired):**
- `mcp-huggingface:find_model` — calls `hub_repo_search` with `{query}`
- `mcp-huggingface:inspect_paper` — calls `paper_search` with `{query}`

---

## 3. GitHub MCP

**Plugin card name in Daena UI:** "GitHub" (id `mcp-github`)

**npm package:** `@modelcontextprotocol/server-github`

**Install command:**
```
npx -y @modelcontextprotocol/server-github
```

**Required env vars:** `GITHUB_PERSONAL_ACCESS_TOKEN`

**Auth:** create a GitHub PAT at `https://github.com/settings/tokens`. Required scopes for the promoted Phase 2.x read-only skills:
- `public_repo` (read public repos — covers most use)
- `read:org` (org membership lookup)
- `read:user` (your own profile)

DO NOT grant `repo` (full read-write) — the Phase 2.x allowlist won't let Daena write anyway, and a narrower token reduces blast radius if it ever leaks.

**How to provide the token:** the install dialog in the Plugins UI accepts the token; it's stored ONLY in the MCP server's process env via `claude_desktop_config.json`. Daena's executor never sees the token.

**Probe step:** click "Test". Expected `tools/list` includes `get_repository`, `list_issues`, `get_workflow_run_logs`, `search_repositories`, etc. Write tools (`create_issue`, `merge_pull_request`, `create_branch`) are present in the MCP but Daena's allowlist BLOCKS them.

**Promoted skills:**
- `mcp-github:summarize_repo` — calls `get_repository` with `{owner, repo}`
- `mcp-github:triage_issues` — calls `list_issues` with `{owner, repo, state: "open"}` (read-narrowed)
- `mcp-github:inspect_ci_failure` — calls `get_workflow_run_logs` with `{owner, repo, run_id}`

**Try it:**
- Skill: `triage_issues`
- Operator inputs: `repo_owner = "anthropic"`, `repo_name = "claude-code"`
- Expected result: list of open issues with labels + comment counts.

---

## 4. Sentry MCP

**Plugin card name in Daena UI:** "Sentry" (id `mcp-sentry`)

**npm package:** `@sentry/mcp-server`

**Two install modes:**

### 4a. Self-hosted (token-based, recommended for local dev)

Install command:
```
npx -y @sentry/mcp-server
```

Required env vars:
- `SENTRY_AUTH_TOKEN`
- `SENTRY_HOST` (e.g. `https://sentry.io` or your self-hosted Sentry URL)

Auth: Sentry → Settings → Auth Tokens → New Internal Integration. Required scopes for the promoted skill:
- `org:read`
- `project:read`
- `event:read`

DO NOT grant write scopes (`project:write`, `event:write`, `team:write`) — same blast-radius logic as GitHub.

### 4b. Hosted OAuth (operator action via Sentry's web UI)

Hosted endpoint: `https://mcp.sentry.dev/mcp` (OAuth device-code flow).

If you prefer OAuth, the install dialog will redirect you to Sentry's
device-code page. Daena does NOT auto-open this; you have to click the
link explicitly.

**Probe step:** click "Test". Expected `tools/list` includes `list_issues`, `get_event`, `search_events`. Write tools (`create_bug_task`, `assign_issue`, `resolve_issue`) are blocked by Daena's allowlist.

**Promoted skill:**
- `mcp-sentry:summarize_errors` — calls `list_issues` with `{organizationSlug, projectSlug, query: "age:-{time_window}"}` (read-narrowed by org + project + age window)

**Try it:**
- Skill: `summarize_errors`
- Operator inputs: `organization_slug = "mas-ai"`, `project_slug = "daena-backend"`, `time_window = "7d"`
- Expected result: top issues from the last 7 days with frequency + first/last seen.

---

## After all four are installed

Re-run `DAENA_LOCAL_PRODUCTION_READY_SMOKE.md` Section 5.2 — the
promoted-set verification should still print exactly 8 lines (4 from
PR-1, 4 from PR-2). Now Section 5.3's "block non-allowlisted" still
returns `blocked`, but you can also try the actual promoted skills:

```bash
# triage GitHub issues
curl -s -X POST -H "Authorization: Bearer <YOUR_TOKEN>" -H "Content-Type: application/json" \
  -d '{"plugin_id":"mcp-github","skill_id":"triage_issues","operator_inputs":{"repo_owner":"anthropic","repo_name":"claude-code"}}' \
  http://127.0.0.1:8000/api/v1/connections/v2/skills/execute
```

Expected: `{"accepted": true, "status": "executed", "summary": "..."}`.

If you still get `needs_connection`, the MCP isn't installed where Daena expects. Check `~/AppData/Roaming/Claude/claude_desktop_config.json`.

If you get `blocked` with `blocked_reason: "mcp_tool_error"`, the MCP IS installed but the call failed — the summary will quote the underlying MCP's error message.

If you get `blocked` with `blocked_reason: "mcp_tool_timeout"`, the MCP took longer than 12s to respond. Could be a slow network, a large repo, or a hung MCP. Check the launcher's stdout window for the MCP's logs.

---

## Token security notes

- Tokens live in `claude_desktop_config.json` ONLY when you provide them through Daena's install dialog.
- Daena's executor never reads the token from the config — it just calls the MCP, which spawns with the env vars set.
- Daena's audit log records the action's metadata (plugin_id, skill_id, outcome, content hash) but never the token, never the response body.
- Per Sprint-1 PR-3 (`da23dd7`), if you click "Disconnect" on a token-backed connector, Daena calls a best-effort revoke at the provider when supported (Google/Slack do; GitHub/Figma/Canva don't expose RFC-7009 revoke). For GitHub specifically: if you suspect a token leak, revoke at `https://github.com/settings/tokens` directly.

---

## When something looks wrong

1. Restart the backend via `scripts\start-backend-dev.bat` — picks up new claude_desktop_config without app restart.
2. Open the launcher window's stdout — `mcp_bootstrap.adapter_ready` lines confirm what got loaded.
3. The truth-ladder dots in the Plugins UI are honest (per project Rule 17). If a dot is gray, the underlying capability genuinely failed — not a UI bug.
4. Hit `/api/v1/connections/v2/skills/allowlist` directly with your auth header to confirm the promoted set is what you expect.

If you're stuck, the smoke checklist (`DAENA_LOCAL_PRODUCTION_READY_SMOKE.md`) is the ordered triage path: top-to-bottom, the first failing item is usually the root cause.
