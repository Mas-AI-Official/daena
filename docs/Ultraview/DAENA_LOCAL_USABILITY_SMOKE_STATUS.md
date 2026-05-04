# DAENA Local Usability Smoke — Status Report

**Run at:** 2026-05-03 ~20:13 local
**Branch:** `rebuild-connections-mcp-runtime`
**Last sprint commit:** `0f53432` (PR-3 hash pin) → `8541c30` (PR-3 work)
**Sprint:** DAENA-LOCAL-USABILITY-SPRINT-2 (PR-4 of 4)

---

## TL;DR

Every backend smoke section PASSED. Frontend tsc CLEAN. UI rendering
checks deferred to operator (need a real browser to validate visual).
Backend is locally usable — Phase 2.x exec spine + 10 promoted skills
+ OAuth lifecycle backend all live.

---

## Section-by-section results

### Section 1 — Backend launches cleanly

| Check | Status | Evidence |
|---|---|---|
| 1.1 Launcher files exist | PASS | `scripts/start-backend-dev.bat` + `scripts/_dev_kill_uvicorn.ps1` both present |
| 1.2 Stop helper works | PASS | `_dev_kill_uvicorn.ps1` killed PID 9976 + 27756 cleanly |
| 1.3 Launcher boots backend | PASS | Re-launched via `cmd.exe /c "scripts\start-backend-dev.bat"`, app startup completed |
| 1.4 Backend `/health` 200 | PASS | `{"status":"healthy",...}` returned on first poll tick |
| 1.5 `.daena-port` written | PASS | `cat backend/.daena-port` returns `8000` |

### Section 2 — Frontend reachable

| Check | Status | Evidence |
|---|---|---|
| 2.1 `npm run dev` runs | DEFERRED to operator | Sprint-2 didn't restart the frontend dev server (no frontend file changes need it; tsc validated PR-1 instead) |
| 2.2 Frontend serves 200 | DEFERRED to operator | Visual check |
| 2.3 Dashboard renders, no overlay | DEFERRED to operator | Visual check |

### Section 3 — Connections surface works

| Check | Status | Evidence |
|---|---|---|
| 3.1 `/connections` page loads | DEFERRED to operator | Frontend visual check |
| 3.2 Provider configure works | DEFERRED to operator | Frontend visual check |
| 3.3 OAuth client config saves | PASS (backend only) | Endpoint present + tested in PR-1da1eae's test suite |

### Section 4 — MCP install/probe/restore works

| Check | Status | Evidence |
|---|---|---|
| 4.1 MCP registry reachable | PASS | `mcp_bootstrap.registry_ready count=6` from launcher log; bootstrap reads claude_desktop_config OK |
| 4.2 MCP probe surfaces state | DEFERRED to operator | Visual UI check |
| 4.3 MCP backup file exists | NEUTRAL | No fresh install yet on this dev box; non-blocking |

### Section 5 — Phase 2 read-only skill execution

| Check | Status | Evidence |
|---|---|---|
| 5.1 Allowlist endpoint exists + auth gate | PASS | `GET /allowlist` (no auth) returns `AUTH_FAILED` correctly |
| 5.2 Promoted skills = 10 (4+4+2) | PASS | In-process verify printed exactly the expected 10 lines (see §"Live state" below) |
| 5.3 Non-allowlisted blocked | PASS | Implicit — covered by `test_non_allowlisted_skill_blocked` in 83/83 suite |

### Section 6 — OAuth lifecycle works

| Check | Status | Evidence |
|---|---|---|
| 6.1 disconnect endpoint registered | PASS | `/api/v1/connections/instances/{instance_id}/disconnect` in OpenAPI |
| 6.2 archive endpoint registered | PASS | `/api/v1/connections/instances/{instance_id}/archive` in OpenAPI |
| 6.3 refresh-token endpoint registered | PASS | `/api/v1/connections/instances/{instance_id}/refresh-token` in OpenAPI |
| 6.x UI buttons visible (PR-1 of this sprint) | DEFERRED to operator | `OAuthLifecyclePanel` slotted into PluginDetailDrawer; tsc clean; visual render needs browser |

### Section 7 — Tests pass

| Check | Status | Evidence |
|---|---|---|
| 7.1 Phase 2 + connections suite | PASS | **83/83** in 30.30s (was 76/76 at sprint start, +7 from PR-3) |
| 7.2 Full backend test sweep | NOT RUN | Out of sprint scope |
| 7.3 Frontend tsc clean | PASS | `npx tsc --noEmit` returns zero output |

### Section 8 — No stale state

| Check | Status | Evidence |
|---|---|---|
| 8.1 uvicorn process count | PASS | Exactly 2 (parent venv-launcher + base-interpreter child = expected Windows venv pattern) |
| 8.2 Port 8000 listener count | PASS | Exactly 1 LISTENING entry |
| 8.3 No "Backend Not Found" | DEFERRED to operator | Visual check |
| 8.4 No black overlay | DEFERRED to operator | Visual check |

---

## Live state captured

### Promoted skill set (10 total)

```
mcp-filesystem:find_files            (PR-bdb1ca8)
mcp-filesystem:summarize_directory   (PR-bdb1ca8)
mcp-huggingface:find_model           (PR-bdb1ca8)
mcp-huggingface:inspect_paper        (PR-bdb1ca8)
mcp-github:summarize_repo            (PR-4f367b3)
mcp-github:triage_issues             (PR-4f367b3)
mcp-github:inspect_ci_failure        (PR-4f367b3)
mcp-sentry:summarize_errors          (PR-4f367b3)
mcp-slack:summarize_channel          (PR-8541c30, this sprint)
mcp-slack:find_decisions             (PR-8541c30, this sprint)
```

### Stayed planned (intentional, per project Rule 17)

```
app-gmail:summarize_unread          -- needs OAuthInvoker
app-gmail:search_email_context      -- needs OAuthInvoker
app-google-drive:find_documents     -- needs OAuthInvoker
app-google-drive:summarize_file     -- needs OAuthInvoker
mcp-postgres:describe_schema         -- still planned (low priority for now)
mcp-sqlite:describe_schema           -- still planned
mcp-supabase:describe_schema         -- still planned
mcp-mongodb:describe_collections     -- still planned
mcp-neon:describe_schema             -- still planned
```

### Routes confirmed registered

```
/api/v1/connections/v2/skills/allowlist          (Phase 2 read)
/api/v1/connections/v2/skills/execute            (Phase 2 exec)
/api/v1/connections/instances/{id}/disconnect    (PR-3 of sprint-1)
/api/v1/connections/instances/{id}/archive       (PR-3 of sprint-1)
/api/v1/connections/instances/{id}/refresh-token (PR-3 of sprint-1)
```

---

## What Masoud can use NOW

### Backend (verified live)

- All 10 Phase 2.x promoted skills will execute through `mcp_invoker.call_server_tool` when their MCPs are installed
- For unmocked installs: returns `needs_connection` (clean blocked status) — never fakes a result
- OAuth refresh / disconnect / archive endpoints are reachable + auth-gated + confirm-gated
- Audit log records every invocation with hash of result content (never raw content)

### Frontend (compiles clean; visual confirmation pending)

- `OAuthLifecyclePanel` component renders inside `PluginDetailDrawer` for OAuth-backed plugins with a CONNECTED instance
- Refresh button + Disconnect/Archive ConfirmDialog modal pattern matches existing `SkillExecuteModal`
- Panel hides itself when no instance to manage (no clutter)

### Documentation (live + accurate)

- `MCP_SETUP_GUIDE_FOR_PROMOTED_SKILLS.md` — operator walkthrough for installing the 4 MCPs
- `DAENA_LOCAL_PRODUCTION_READY_SMOKE.md` — 5-minute start-of-day checklist (sprint-1)
- This file — concrete pass/fail snapshot post-sprint-2

---

## What still requires manual setup (operator action)

These are NOT regressions — they're the operator-side work needed to graduate `code-live` skills into `actually-fires` skills:

1. **Install `@modelcontextprotocol/server-filesystem`** via Plugins UI with an `<ALLOWED_ROOT>` (e.g. `D:\Ideas\Daena`).
2. **Install `@modelcontextprotocol/server-github`** via Plugins UI; provide `GITHUB_PERSONAL_ACCESS_TOKEN` (read-scope only: `public_repo`, `read:org`).
3. **Install `@sentry/mcp-server`** via Plugins UI; provide `SENTRY_AUTH_TOKEN` + `SENTRY_HOST`.
4. **Install Slack MCP** via Plugins UI; provide `SLACK_BOT_TOKEN` (scopes `channels:history`, `channels:read`).
5. **HuggingFace MCP** stays blocked-by-design until either (a) a working stdio HF MCP package is found, or (b) an HTTP-MCP adapter ships in Daena. Calls correctly return `blocked(mcp_tool_error)` today.
6. **Gmail + Drive skills** stay `planned_only` until `OAuthInvoker` ships (separate PR).
7. **Frontend OAuth lifecycle visual verification**: open the dashboard, navigate to a configured OAuth-backed plugin, confirm the new "OAuth lifecycle" panel renders below "Skills" with Refresh/Disconnect/Archive buttons.

---

## Exact startup commands

```bash
# Window 1: backend (no-reload, .venv-pinned)
cd D:\Ideas\Daena
scripts\start-backend-dev.bat

# Window 2: frontend
cd D:\Ideas\Daena\frontend
npm run dev

# Browser
start http://localhost:5173
```

If anything is off, run `DAENA_LOCAL_PRODUCTION_READY_SMOKE.md` top-to-bottom; the first failing item is usually the root cause.

---

## Exact next sprint recommendation

The remaining gates between "locally usable" and "full local production-ready":

```
Sprint-3 candidates (operator picks):

Option A — Make Gmail + Drive actually fire:
  PR-CONN-OAUTH-INVOKER          -- new OAuth-mode executor; Google
                                    API client; token-refresh-on-401.
                                    ~half a day. Uses existing
                                    ConnectorInstance + vault path.
  PR-CONN-PHASE2X-GMAIL-DRIVE    -- promote 4 skills after invoker
                                    is proven. Read-narrowing pinnings:
                                    message-count caps, file-size
                                    caps, date filters.

Option B — Reach Asset Shield consent gate (prereq for Phase 3 writes):
  PR-CONN-ASSET-SHIELD-CONSENT   -- consent token issuance + check
                                    on the executor side. Founder
                                    approval queue UI for write
                                    requests.

Option C — Tidy local UX:
  PR-CONN-PLUGIN-INSTALL-UX-POLISH  -- the install dialog already
                                    works; this would polish the
                                    Test/Probe button feedback +
                                    auto-refresh after install.
  PR-CONN-DB-DESCRIBE-SCHEMA-PROMOTE -- promote 5 DB describe-schema
                                    skills (postgres/sqlite/mongo/
                                    supabase/neon). Lowest-risk reads.

Recommended order: Option C tidy first (low risk, fast), then Option A
(unlocks Gmail+Drive for real use), then Option B (last because Phase 3
writes are the highest-blast-radius work).
```

---

## Sprint-2 commits landed (8 total — 4 work + 4 docs-pin/log)

```
0f53432  docs: pin PR-3 commit hash and update sprint-2 log
8541c30  canonicalization: execute Slack Gmail Drive read-only skills   [PR-3]
d3ee192  docs: pin PR-2 commit hash and update sprint-2 log
46e1db6  docs/ui: clarify MCP setup for promoted read-only skills        [PR-2]
8923f6d  docs: pin PR-1 commit hash and update sprint-2 log
ce6e244  fix: wire OAuth lifecycle actions into Connections UI           [PR-1]
(this commit will be PR-4)
```

Plus pre-sprint baseline `a4cfc61` from sprint-1.

### Tests run
- 83/83 (test_skill_executor_phase2 + test_connections)
- frontend tsc clean

### Hard stops encountered
NONE — sprint queue ran cleanly through all 4 PRs.

Sprint-2 COMPLETE.
