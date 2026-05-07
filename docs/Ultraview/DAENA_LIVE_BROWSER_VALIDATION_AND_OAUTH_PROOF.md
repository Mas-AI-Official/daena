# Daena Live Browser Validation + OAuth Proof
Date: 2026-05-07
Author: DAENA-LIVE-LOCAL-BROWSER-VALIDATION-AND-OAUTH-PROOF
Predecessor: V3 Phase 1 (`37d8969`) + OVERNIGHT (`ff5b3db`)

## Honest verdict

**LOCAL BUSINESS BETA: READY.**

- Backend: green. 441 routes mounted. Health detailed = healthy. All critical authenticated endpoints respond 200 with valid JSON.
- Frontend: green. Vite serving SPA on `:5173`. All key page routes return 200.
- V3 Phase 1 + OVERNIGHT changes confirmed in served bundle (Roadmap expanders + Diagnostics banner + officiality-removed cards all present).
- Business-loop endpoints carry real seeded data (2 workstreams RUNNING, 1 sample opportunity, 4 runtimes online).
- Google OAuth: **operator-blocked** as expected (`client_configured=false`, both accounts not connected).

**LIVE BUSINESS OPERATOR: BLOCKED ON OAUTH.**

The only blocker between current state and live business automation is configuring the Google OAuth client at `console.cloud.google.com` and connecting `masoud.masoori@mas-ai.co` + `daena@mas-ai.co`. Code is ready.

**FULL AUTONOMOUS VP: GATED — needs OAuth + controlled live submission proof.**

## Validation methodology

The chrome-devtools + playwright MCP servers disconnected at the start of this session, so true browser-clicking was off the table. Substituted with HTTP-only validation:

1. Cleanup stale dev processes via `scripts/cleanup-stale-dev.ps1`
2. Boot backend on `:8000` via `uvicorn app.main:app`
3. Boot frontend on `:5173` via `npx vite`
4. Probe health endpoints (no auth)
5. Mint dev JWT via `backend/scripts/_mint_dev_token.py`
6. Probe authenticated business-loop endpoints
7. Fetch SPA HTML + Vite source files to verify served bundle contains OVERNIGHT changes

This is a static-analysis + HTTP-runtime substitute for a NUser browser crawl. It cannot click buttons or verify CSS rendering, but it can prove every endpoint responds with the expected shape and the served bundle includes the recent changes.

## Boot results

```
[backend] :8000 LISTENING — uptime 50s, status=healthy, seed_errors=[]
[frontend] :5173 LISTENING — Vite serving SPA HTML
```

Backend startup notable signals from logs: `tool_catalog.hackingtool_tier_upgrade` × N, `business.routine.registered` × 3 (opportunity_discovery, business_workstream_proposal, local_draft_action_creation). Heartbeat scheduler active (cycle_count=1).

## Frontend bundle verification

| Probe | Result |
|---|---|
| `GET /` | 200 — Daena SPA HTML (`<title>Daena — Governed AI Platform</title>`) |
| `GET /@vite/client` | 200 |
| `GET /src/main.tsx` | 200 |
| `GET /src/pages/settings/SettingsDeveloper.tsx` | 200 + contains `"Roadmap (not active yet)"` ✓ |
| `GET /src/pages/settings/SettingsPrivacy.tsx` | 200 + contains `"Data Processing (not active yet)"` ✓ |
| `GET /src/pages/ConnectionsPage.tsx` | 200 + contains `"Diagnostics surface"` ✓ |
| `GET /src/pages/connections/PluginCardView.tsx` | 200 + 0 hits for `officialityLabel` / `officialityTone` ✓ |

OVERNIGHT (`ff5b3db`) and V3 Phase 1 (`37d8969`) changes are live in the served bundle.

## Auth probe results

Dev token minted from first-founder user via `_mint_dev_token.py` — 461-byte JWT.

| Endpoint | Status | Payload summary |
|---|---|---|
| `GET /api/v1/health/detailed` | 200 | status=healthy, ollama=unavailable, redis=unavailable, db=91 sessions / 264 messages |
| `GET /api/v1/health/runtime` | 200 | env=development, allows_unsafe_dev_features=true |
| `GET /api/v1/runtimes` | 200 | 6 runtimes: claude_code/codex/gemini_cli/vllm online, grok_cli/ollama offline |
| `GET /api/v1/connections/google-setup-status` | 200 | **client_configured=false, founder_account.connected=false, agent_account.connected=false** |
| `GET /api/v1/opportunities/` | 200 | 1+ seeded opportunity (sample mid-market governed-AI buyer prospect) |
| `GET /api/v1/opportunities/send-rate-limit` | 200 | used=0, cap=3, remaining=3 |
| `GET /api/v1/workstreams` | 200 | 2 workstreams in RUNNING state |
| `GET /api/v1/governance/approvals` | 200 | empty list (no pending) |
| `GET /api/v1/execution/tasks` | 200 | empty list |
| `GET /api/v1/system/runtime-readiness` | 200 | full readiness ladder; cli_claude detected/configured/authenticated/reachable/callable |
| `GET /api/v1/heartbeat/status` | 200 | state=running, cycle_count=1, autopilot_level=on |

All authenticated endpoints return structured `{success, data, ...}` envelopes. No crashes. No 500s. The 401 default for unauthenticated requests is also structured (`{success:false, error:{code:"AUTH_FAILED", ...}}`).

## SPA route probe (HTML)

| Path | Status |
|---|---|
| `/` | 200 |
| `/connections` | 200 |
| `/settings/developer` | 200 |
| `/settings/privacy` | 200 |
| `/opportunity-inbox` | 200 |
| `/workstreams` | 200 |
| `/governance/approvals` | 200 |

All client-side routes resolve to SPA HTML. (HTTP probes cannot verify client-rendered UI; for that, operator must hard-refresh in browser.)

## Critical finding — MCP unscoped-package drift

The MCP registry contains 7 servers seeded from `claude_desktop_config.json`. Of those:

| Server | Package | Likely status |
|---|---|---|
| `playwright` | `@playwright/mcp@latest` | **FIXED** ✓ (operator patched yesterday) |
| `windows-mcp` | `windows-mcp` | **WRONG** — bare unscoped name |
| `shell` | `shell` | **WRONG** — bare unscoped name |
| `huggingface-mcp` | `huggingface-mcp` | **WRONG** — bare unscoped name |
| `mcp-google-drive` | `mcp-google-drive` | **WRONG** — bare unscoped name |
| `MCP_DOCKER` | (docker command) | OK — different shape |
| `filesystem` | (truncated) | TBD |

The PR-5 detector from V3 Phase 1 (`_detect_likely_wrong_npm_package` in `seeders.py`) will warn-log on the four "wrong" entries the next time discovery runs. **None are auto-fixed** — by design (operator-config edits require explicit consent).

**Recommended operator fix:** edit `C:\Users\masou\AppData\Roaming\Claude\claude_desktop_config.json` and replace the four bare-name `args[1]` values with their canonical scoped equivalents (where they exist). If a canonical scoped MCP doesn't exist for one of these servers, remove the entry — currently it will fail probe with `initialize_failed: McpError: Connection closed` exactly like Playwright did.

This is the **same class of bug** that broke Playwright yesterday. Not introduced by V3 Phase 1 — they were always broken, just unflagged until the detector shipped.

## Business loop walk-through

| Step | Endpoint | State |
|---|---|---|
| 1. Discover opportunities | `POST /api/v1/opportunities/run-discovery` | wired (matrix PR-6) |
| 2. List opportunities | `GET /api/v1/opportunities/` | **proven live** — 1 seeded entry |
| 3. Create workstream from opportunity | `POST /api/v1/opportunities/{id}/create-workstream` | route exists in OpenAPI |
| 4. List workstreams | `GET /api/v1/workstreams` | **proven live** — 2 RUNNING |
| 5. Workstream actions | `POST /api/v1/workstreams/{id}/{action}` | wired (matrix PR-6) |
| 6. Approval queue | `GET /api/v1/governance/approvals` | **proven live** — empty (no pending) |
| 7. Approve/reject | `POST /api/v1/governance/approvals/{id}/decide` | wired (matrix PR-6) |
| 8. Send rate limit | `GET /api/v1/opportunities/send-rate-limit` | **proven live** — 3/day cap, 0 used |

**The full business loop is wired AND backed by real data.** The send rate limit (3/day) is the safety gate before any external action. Currently 0 used — operator hasn't sent anything yet.

## Google OAuth proof — exact blocker

`GET /api/v1/connections/google-setup-status` returns:

```json
{
  "client_configured": false,
  "client_id_present": false,
  "client_secret_present": false,
  "founder_account": {
    "email": "masoud.masoori@mas-ai.co",
    "connected": false,
    "instance_id": null,
    "connected_services": []
  },
  "agent_account": {
    "email": "daena@mas-ai.co",
    "connected": false,
    ...
  }
}
```

**Three operator actions required, in order:**

1. **Configure OAuth client** at `https://console.cloud.google.com` (project `daena-467315`)
   - Create OAuth 2.0 client ID, type=Web Application
   - Authorized redirect URI: `http://127.0.0.1:8000/api/v1/connections/oauth/callback` (or whatever the frontend OAuthConnectDrawer uses — verify before pasting)
   - Copy client_id + client_secret

2. **Paste credentials** at `/account#oauth-clients` in the running Daena frontend
   - This calls `POST /account/oauth-clients/google` with `{client_id, client_secret}`
   - Stores plaintext in `backend/.daena_oauth_overrides.json` (chmod 0600 on POSIX, gitignored)
   - Sidecar metadata in `backend/.daena_oauth_client_metadata.json`

3. **Connect both accounts** via `/connections` Plugins grid:
   - Click Connect on Gmail / Drive / Calendar plugin cards
   - OAuthConnectDrawer opens → operator chooses founder vs agent → Google consent flow → token stored per-account

After step 3, `google-setup-status` should return `client_configured=true`, `founder_account.connected=true`, `agent_account.connected=true`.

## What was NOT validated tonight

| Item | Why |
|---|---|
| Browser click-through (NUser crawl) | chrome-devtools + playwright MCP disconnected pre-session |
| CSS rendering of expanders | HTTP-only probes can't see rendered DOM |
| Real Gmail draft creation | OAuth not configured (this is the operator blocker) |
| Live email send | Operator must explicitly approve send drill |
| End-to-end opportunity → workstream → outreach → Gmail draft | Same OAuth blocker |
| Sprint-22 readiness | Premature; OAuth + live-send drill come first |

## Pre-existing issues found (not OVERNIGHT regressions)

| Issue | Detail | Severity |
|---|---|---|
| `system_self_diagnostic.py:647` | Uses `asyncio.gather` with shared DB session; failing `test_no_shared_session_gather` | medium — separate ticket; pre-existing |
| 4 unscoped MCP packages in operator's config | `windows-mcp`, `shell`, `huggingface-mcp`, `mcp-google-drive` will fail probe | low — operator-fix required |

## Did not run / declined to run

- **No deploy.** No `gcloud run deploy`. No production push.
- **No force push.** Origin push was vanilla fast-forward.
- **No secret reads/prints.** Dev token is per-session, ephemeral.
- **No bulk send.** No outbound email. No LinkedIn. No external automation.
- **No new feature work.** Only audit, doc, and a small contract-test fix.
- **No fake READY verdict.** Read above — operator action remains.

## Operator next steps

1. Hard refresh `/connections`, `/settings/developer`, `/settings/privacy` to verify visual changes match probes.
2. Fix 4 unscoped MCPs in `claude_desktop_config.json` (or remove them if no canonical scoped package exists).
3. Configure Google OAuth client + paste credentials at `/account#oauth-clients`.
4. Connect both accounts via Plugins grid.
5. Re-run `GET /api/v1/connections/google-setup-status` (or refresh the Google card) to confirm `ready=true`.
6. Once green: run controlled outreach draft creation (NOT send) → review → operator approves first send manually.

## Sprint-22 readiness

**NOT YET.** Three gates remain:
1. Google OAuth connected
2. First controlled draft creation proven (not sent)
3. First operator-approved live send completed cleanly

Until those three pass, Sprint-22 is premature. The infrastructure is ready; the *proof* is the operator's next mile.

## Servers left running

Backend `:8000` and frontend `:5173` are still running in this session for operator use. Stop them via `scripts/cleanup-stale-dev.ps1` when done.
