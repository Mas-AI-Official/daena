# Sprint Log — DAENA-LOCAL-USABILITY-SPRINT-2

**Started:** 2026-05-03 (~19:50 local)
**Branch:** `rebuild-connections-mcp-runtime`
**Mode:** Bounded autopilot (founder authorization 2026-05-03)
**Pre-sprint commit:** `a4cfc61` (Sprint-1 sprint log finalized)

---

## Hard stops (paste from authorization)

1. Production deploy / Cloud Run / GCP write
2. `USE_CONNECTION_REGISTRY_V2=true` flip
3. `vault --apply`
4. Secret read/print/grep/log/commit
5. External email / DM / webhook / message
6. Payment / refund / subscription / write
7. Browser action on external sites
8. V1 / legacy file deletion
9. npm/pip/docker install not in operator-confirmed flow
10. Test failure not clearly pre-existing + quarantined
11. Unexpected secret-risk file in git status
12. Architectural uncertainty (two paths equally risky)

---

## Pre-flight (2026-05-03 19:50)

| Check | Result |
|---|---|
| dirty count | 209 (no new from sprint) |
| backend `/health` | 200 |
| Phase 2 routes registered | YES (`allowlist`, `execute`) |
| OAuth lifecycle routes registered | YES (`disconnect`, `archive`, `refresh-token`) |

---

## Sprint queue

| # | PR | Status | Commit | Tests | Notes |
|---|---|---|---|---|---|
| 1 | PR-CONN-OAUTH-LIFECYCLE-FRONTEND | shipped | `ce6e244` | tsc clean + 76/76 backend | live UI verify deferred (no real OAuth instance on dev box) |
| 2 | PR-CONN-MCP-INSTALL-OPERATOR-GUIDE | shipped | `46e1db6` | n/a (docs only) | covers FS+HF+GitHub+Sentry; HF flagged as blocked-until-HTTP-adapter |
| 3 | PR-CONN-PHASE2X-SLACK-GMAIL-DRIVE-READONLY | shipped | `8541c30` | 83/83 phase2+connections | Slack 2 promoted; Gmail+Drive deliberately stay planned (need OAuthInvoker first) |
| 4 | PR-LOCAL-DAENA-USABILITY-SMOKE | shipped | `15d1667` | live smoke run | every backend section PASS; visual sections deferred to operator |

---

## Append log (one line per commit)

<!-- HH:MM | PR-N | <commit> | <one-line-summary> -->
- 19:55 | PR-1 | ce6e244 | OAuthLifecyclePanel + slot in PluginDetailDrawer (Refresh / Disconnect / Archive buttons + ConfirmDialog), tsc clean + 76/76 backend
- 20:02 | PR-2 | 46e1db6 | MCP setup guide for FS+HF+GitHub+Sentry promoted skills (4-step Install->Test->Connected->Run framing)
- 20:09 | PR-3 | 8541c30 | promote 2 Slack skills to mcp_tool, defend Gmail+Drive as planned-only-until-OAuthInvoker, 7 new tests + 2 retargeted, 83/83 suite green
- 20:18 | PR-4 | 15d1667 | local usability smoke run + status doc -- every backend section PASS, 10 promoted skills confirmed live, sprint COMPLETE

---

## Sprint-2 final report

### Commits landed
- 4 work PRs + 4 docs-pin/log updates
- See `DAENA_LOCAL_USABILITY_SMOKE_STATUS.md` "Sprint-2 commits landed" for full list

### Tests run
- 83/83 (test_skill_executor_phase2 + test_connections)
- frontend tsc clean

### What Masoud can use NOW
- Backend Phase 2.x exec spine + 10 promoted skills + OAuth lifecycle endpoints (all live, all auth-gated)
- Frontend OAuth lifecycle UI panel (compiles + types-clean; visual verify deferred to operator)
- Two operator-facing docs:
  - `MCP_SETUP_GUIDE_FOR_PROMOTED_SKILLS.md` (sprint-2 PR-2)
  - `DAENA_LOCAL_USABILITY_SMOKE_STATUS.md` (sprint-2 PR-4)

### What still requires manual setup
- Install `@modelcontextprotocol/server-filesystem` + `-server-github` + `@sentry/mcp-server` + Slack MCP via Plugins UI
- Provide tokens (GitHub PAT, Sentry token, Slack bot token) — minimum scopes documented in setup guide
- Replace broken `huggingface-mcp` config OR accept blocked-by-design for HF skills until HTTP-MCP adapter ships
- Visually verify the OAuth lifecycle panel renders in browser

### Hard stops encountered
NONE.

### Exact startup commands (tomorrow)
```
cd D:\Ideas\Daena
scripts\start-backend-dev.bat       # window 1: backend
cd D:\Ideas\Daena\frontend
npm run dev                          # window 2: frontend
start http://localhost:5173          # browser
```

### Suggested next sprint
Recommended order from `DAENA_LOCAL_USABILITY_SMOKE_STATUS.md`:
1. Option C — DB describe-schema promotion + plugin install UX polish (low risk, fast)
2. Option A — `OAuthInvoker` + Gmail/Drive promotion (unlocks Gmail+Drive)
3. Option B — Asset Shield consent (gates Phase 3 writes)
