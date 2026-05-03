# Daena — Local Production-Ready Smoke Checklist

**Audience:** Masoud, on his laptop, start-of-day or before a demo.
**Purpose:** Run this top-to-bottom in ~5 minutes to know whether
local Daena is in shape to use today.
**Owner:** PR-CONN-LAPTOP-PRODUCTION-SMOKE (sprint PR-4 of 4, 2026-05-03).

If any single item fails — STOP and fix that item before continuing.
The items are ordered so a failure cascades downstream; fixing the
earliest red item usually clears the rest.

---

## How to read this doc

Each section is a numbered checkbox with:
- **What you check** — the operator action
- **Pass criteria** — what good looks like
- **If it fails** — minimal recovery action

A check that requires running a command shows the exact command in
copy-pasteable form. Replace `D:\Ideas\Daena` if your repo path
differs.

---

## Section 1 — Backend launches cleanly

### [ ] 1.1 Backend launcher exists

Run:
```
ls D:\Ideas\Daena\scripts\start-backend-dev.bat
ls D:\Ideas\Daena\scripts\_dev_kill_uvicorn.ps1
```
**Pass:** both files exist.
**If it fails:** check out commit `8544e48` (PR-DEV-BACKEND-LAUNCHER-STABILITY).

### [ ] 1.2 Stop any stale backend FIRST

Run from a Windows terminal or VS Code terminal:
```
powershell -NoProfile -ExecutionPolicy Bypass -File D:\Ideas\Daena\scripts\_dev_kill_uvicorn.ps1
```
**Pass:** prints `(no uvicorn app.main:app processes found)` OR
`Killing PID xxxxx ...` and exits 0.
**If it fails:** check the powershell error; usually means the script
moved or PATH is broken.

### [ ] 1.3 Start backend via launcher

```
cd D:\Ideas\Daena
scripts\start-backend-dev.bat
```
Leave the window open — uvicorn logs stream there.
**Pass:** within 5 seconds you see `INFO: Application startup complete.`
followed by `daena_essentials_ready total_ms=<small>`.
**If it fails:** look for `[Errno 10048]` (port still held — re-run 1.2)
or any Python traceback in the log (usually a missing env var or
broken import).

### [ ] 1.4 Backend health responds

In a NEW terminal:
```
curl -s http://127.0.0.1:8000/health
```
**Pass:** returns `{"status":"healthy","service":"daena-backend",...}`.
**If it fails:** backend isn't actually up yet — wait 5s and retry.
If still failing, re-run 1.2 + 1.3.

### [ ] 1.5 .daena-port file exists

```
cat D:\Ideas\Daena\backend\.daena-port
```
**Pass:** prints `8000`.
**If it fails:** lifespan didn't complete — check the launcher window
for shutdown logs. Re-run 1.2 + 1.3.

---

## Section 2 — Frontend reachable

### [ ] 2.1 Start frontend (if not already running)

Frontend is launched by `start-daena.bat`'s full sequence; for
backend-only iteration you can launch it standalone:
```
cd D:\Ideas\Daena\frontend
npm run dev
```

### [ ] 2.2 Frontend serves

```
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:5173
```
**Pass:** returns `200`.
**If it fails:** Vite dev server isn't running. Re-run 2.1.

### [ ] 2.3 Open the dashboard

Browser → http://localhost:5173.
**Pass:** Daena dashboard renders. No black overlay. No "Backend Not
Found" toast.
**If it fails:** check the browser DevTools Console for the actual
error — usually a stale frontend build talking to a stopped backend
(re-run Section 1).

---

## Section 3 — Connections surface works

### [ ] 3.1 /connections page loads

Browser → http://localhost:5173/connections.
**Pass:** the Brain / Plugins / Advanced tabs render. Plugin cards
show with truth-ladder dots (detected / configured / imported /
reachable / authenticated / callable).
**If it fails:** check DevTools Network tab — the `/api/v1/connections/v2/...`
calls should return 200. If 401, your dashboard session is stale —
log out + log in.

### [ ] 3.2 Provider configure works

Click any plugin card → "Configure" → Account → OAuth Client Config.
**Pass:** the OAuth Client Config card renders with fields for
client_id + client_secret per provider (Google, GitHub, Slack, Figma,
Canva). Existing configs show pill `Configured`.
**If it fails:** hit `/api/v1/account/oauth-clients` directly with
your auth header to see the underlying API error.

### [ ] 3.3 OAuth client config save round-trips

Paste an obviously-test value into a provider's `client_id` (e.g.
`smoke-test-12345`), save, reload the page.
**Pass:** the pill flips to `Configured`. Inspect the response —
client_secret field is NEVER returned (only metadata).
**If it fails:** check the response shape. Per PR-1da1eae, the
endpoint returns `OAuthClientStatus` with `has_client_secret: bool`,
not the value.

---

## Section 4 — MCP install/probe/restore works

### [ ] 4.1 MCP registry reachable

```
curl -s -H "Authorization: Bearer <YOUR_TOKEN>" http://127.0.0.1:8000/api/v1/connections/extensions | head -c 300
```
**Pass:** returns a JSON list of installed MCP extensions. Should
include `playwright`, `windows-mcp`, `shell` and any others from
`%APPDATA%\Claude\claude_desktop_config.json`.
**If it fails:** auth issue OR the bootstrap ran with no
claude_desktop_config — check the launcher log for
`mcp_bootstrap.no_config`.

### [ ] 4.2 MCP probe surfaces connection state

In `/connections`, the truth-ladder dots on each MCP card should be
honest. A green callable dot means the MCP successfully completed
its initialize handshake.
**Pass:** at least the MCPs you actually installed show callable.
**If it fails:** install pull/spawn errors — see launcher log
`mcp_invoker.list_tools_failed` lines.

### [ ] 4.3 MCP backup file exists (defensive)

```
ls "%APPDATA%\Claude\claude_desktop_config.backups\" 2>$null
```
**Pass:** at least one timestamped backup file exists. Daena writes
one before any config edit so install/uninstall is reversible.
**If it fails:** non-blocking, but a fresh install hasn't happened
yet on this machine. Install any MCP from Plugins UI to populate.

---

## Section 5 — Phase 2 read-only skill execution

### [ ] 5.1 Allowlist endpoint returns 19 entries

```
curl -s -H "Authorization: Bearer <YOUR_TOKEN>" http://127.0.0.1:8000/api/v1/connections/v2/skills/allowlist | python -c "import json,sys; d=json.load(sys.stdin); print(f'phase={d[\"phase\"]} entries={len(d[\"entries\"])}')"
```
**Pass:** prints `phase=phase2_readonly entries=19`.
**If it fails:** stale backend — restart via Section 1.2 + 1.3.

### [ ] 5.2 Phase 2.x promoted skills are flagged mcp_tool

```
curl -s -H "Authorization: Bearer <YOUR_TOKEN>" http://127.0.0.1:8000/api/v1/connections/v2/skills/allowlist | python -c "import json,sys; d=json.load(sys.stdin); promoted=[(e['plugin_id'],e['skill_id']) for e in d['entries'] if e['execution_mode']=='mcp_tool']; print('\n'.join(f'{p}:{s}' for p,s in promoted))"
```
**Pass:** prints exactly these 8 lines (4 from PR-1, 4 from PR-2):
```
mcp-github:summarize_repo
mcp-github:triage_issues
mcp-github:inspect_ci_failure
mcp-sentry:summarize_errors
mcp-huggingface:find_model
mcp-huggingface:inspect_paper
mcp-filesystem:find_files
mcp-filesystem:summarize_directory
```
**If it fails:** PR-1/PR-2 didn't land or were reverted. Check
`git log --oneline | head -10`.

### [ ] 5.3 Skill execute on a non-allowlisted skill returns blocked

```
curl -s -X POST -H "Authorization: Bearer <YOUR_TOKEN>" -H "Content-Type: application/json" \
  -d '{"plugin_id":"mcp-fake","skill_id":"delete_everything","operator_inputs":{}}' \
  http://127.0.0.1:8000/api/v1/connections/v2/skills/execute
```
**Pass:** returns `{"accepted":false,"status":"blocked","blocked_reason":"not_in_phase2_allowlist",...}`.
**If it fails:** the executor or its allowlist guard is broken. Re-run
the test suite (Section 7).

---

## Section 6 — OAuth lifecycle works

### [ ] 6.1 Disconnect requires confirm

```
curl -s -X POST -H "Authorization: Bearer <YOUR_TOKEN>" \
  http://127.0.0.1:8000/api/v1/connections/instances/00000000-0000-0000-0000-000000000000/disconnect
```
**Pass:** returns 400 with `{"detail":{"code":"confirmation_required",...}}`.
**If it fails:** the confirm-required gate is missing — PR-da23dd7
didn't land or was reverted.

### [ ] 6.2 Archive endpoint exists

```
curl -s -X POST -H "Authorization: Bearer <YOUR_TOKEN>" \
  http://127.0.0.1:8000/api/v1/connections/instances/00000000-0000-0000-0000-000000000000/archive
```
**Pass:** returns 400 with `confirmation_required` (or 404 if no instance).
**If it fails:** route not registered — restart backend (Section 1.2 + 1.3).

### [ ] 6.3 Refresh-token endpoint exists

```
curl -s -X POST -H "Authorization: Bearer <YOUR_TOKEN>" \
  http://127.0.0.1:8000/api/v1/connections/instances/00000000-0000-0000-0000-000000000000/refresh-token
```
**Pass:** returns 404 (instance not found is correct since we passed
zero UUID) OR returns 200 with `{"success":false,"data":{"reason":"no_refresh_token",...}}`.
**If it fails:** route not registered — restart backend.

---

## Section 7 — Tests pass

### [ ] 7.1 Phase 2 executor + connections suite green

```
cd D:\Ideas\Daena\backend
.venv\Scripts\python.exe -m pytest tests\test_skill_executor_phase2.py tests\test_connections.py
```
**Pass:** `76 passed` (50 executor + 26 connections).
**If it fails:** collect the test output and triage. The two suites
together cover the Phase 2.x + OAuth lifecycle contracts. A failure
here means a code change drifted from a contract — DO NOT IGNORE.

### [ ] 7.2 (Optional) Full backend test sweep

```
cd D:\Ideas\Daena\backend
.venv\Scripts\python.exe -m pytest --tb=no -q 2>&1 | tail -20
```
**Pass:** test count grows over time but the previously-known
quarantined failures (per `PR_CONN_PHASE2_PREFLIGHT_GREEN_REPORT.md`)
should be the ONLY remaining failures.
**If it fails:** new regressions outside the connections/Phase 2 area
— investigate per failure. Not blocking for connections work.

### [ ] 7.3 Frontend type-check clean

```
cd D:\Ideas\Daena\frontend
npx tsc --noEmit
```
**Pass:** zero output (ts-clean) or only known warnings.
**If it fails:** new TS error introduced. Look at the file path in
the error and revert the offending edit.

---

## Section 8 — No stale state

### [ ] 8.1 Only ONE uvicorn process per app.main

```
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | Where-Object { $_.CommandLine -and $_.CommandLine -match 'uvicorn\s+app\.main:app' } | Select-Object ProcessId,@{n='cmd';e={$_.CommandLine.Substring(0, [Math]::Min(80, $_.CommandLine.Length))}} | Format-Table -AutoSize"
```
**Pass:** EXACTLY two PIDs (Windows venv launcher + base interpreter
child — see `DEV_BACKEND_LAUNCHER_STABILITY_REPORT.md` §5 for why
this is normal). NOT four or more PIDs.
**If it fails:** stale backends from prior runs are still alive. Run
the Section 1.2 kill helper to clean up, then re-launch.

### [ ] 8.2 Port 8000 has exactly one listener

```
netstat -aon 2>/dev/null | grep -E ":8000\s.*LISTENING"
```
**Pass:** exactly one line.
**If it fails:** see 8.1.

### [ ] 8.3 No "Backend Not Found" in browser

Reload the dashboard. The header status indicator should show
green / connected. No persistent toast or error overlay.
**If it fails:** browser is talking to a different backend port than
the one currently bound. Check `.daena-port` and frontend's
`VITE_BACKEND_URL` env or `lib/api.ts` baseURL config.

### [ ] 8.4 No black overlay on any page

Click through Dashboard → Chat → Connections → Settings → Account.
**Pass:** every page renders content; no all-black screen.
**If it fails:** usually a route-level error boundary catching an
unhandled exception. Check DevTools Console for the trace.

---

## Section 9 — What's currently usable

If all 8 sections pass, Daena local is in good shape. You can:

- **Chat** with any provider you've configured (Ollama, Claude CLI,
  Codex, Gemini CLI, Anthropic API, OpenAI API, Gemini API, etc.)
- **Run read-only Phase 2.x skills** through the Plugins UI Run button
  (filesystem + huggingface need their MCPs installed via Plugins UI;
  GitHub + Sentry need their MCPs installed too)
- **Manage OAuth connections** via Account > OAuth Client Config:
  paste client_id + client_secret per provider
- **Refresh / disconnect / archive** OAuth connections via the new
  PR-3 endpoints (frontend wiring tracks separately; the backend
  surface is fully test-covered)
- **Inspect MCP plugins** via the truth-ladder dots in /connections
- **View audit log** — every skill execution + connector lifecycle
  action writes a tamper-evident audit row

### What's still NOT done

These are KNOWN gaps as of 2026-05-03; do not assume they work:

1. **No frontend wiring** for the new PR-3 OAuth lifecycle buttons
   (Refresh / Disconnect / Archive). Backend works; UI buttons need
   to be added to the Connections page.
2. **No working `huggingface-mcp` or `mcp-filesystem` MCP server
   installed** in this dev box's claude_desktop_config. The Phase 2.x
   skills correctly return `needs_connection` until installed.
3. **No production deploy** of any of these changes. All the work is
   local-only. Cloud Run still runs an older version.
4. **No live Slack / Gmail / Drive / GitHub integrations** beyond the
   spine + planned-only path. Each one still needs its Phase 2.x
   integration arm PR.
5. **OAuth token refresh requires actual OAuth tokens to test** —
   none are configured on this dev box, so all PR-3 lifecycle
   testing is via unit tests + the new endpoints' shape.

---

## Section 10 — Tomorrow's quick start

To launch Daena tomorrow:

```bash
# backend (single window, no-reload, .venv-pinned)
cd D:\Ideas\Daena
scripts\start-backend-dev.bat

# frontend (separate window)
cd D:\Ideas\Daena\frontend
npm run dev

# browser
start http://localhost:5173
```

OR use the all-in-one (WSL backend + frontend + llama-server):

```
cd D:\Ideas\Daena
start-daena.bat
```

To stop everything:

```
cd D:\Ideas\Daena
stop-daena.bat
```

If something breaks, run this checklist top-to-bottom. The first
failing item is usually the root cause.

---

## Sprint context

This checklist landed as PR-4 of the
DAENA-AUTONOMOUS-LOCAL-PRODUCTION-SPRINT (2026-05-03), which also
shipped:

- **PR-1 `bdb1ca8`**: filesystem + HuggingFace skills run real MCP `tools/call`
- **PR-2 `4f367b3`**: GitHub + Sentry skills run real MCP `tools/call`
- **PR-3 `da23dd7`**: OAuth refresh + disconnect/revoke/archive lifecycle
- **PR-4 `<this commit>`**: this smoke checklist

Backed by the prior preflight PRs:
- **`8544e48`**: Windows backend launcher stability
- **`6dd840f`**: pre-Phase-2 baseline cleanup
- **`707b662`**: Phase 2 read-only skills spine
- **`1da1eae`**: OAuth client config in settings
