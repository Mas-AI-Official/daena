# CONNECTIONS_LIVE_SMOKE_AFTER_RESTORE

Local live smoke of `/connections` after the PR-CONN-MCP-INSTALL-RESTORE
chain landed. Backend + frontend brought up fresh on the
`rebuild-connections-mcp-runtime` branch tip (`641df40`). No deploy,
no V2 flag flip, no V1 deletion, no vault apply, no secrets printed.

## Runtime state

### Pre-smoke shell inventory (3 stale dev processes found)

OS-level scan via `Get-NetTCPConnection -State Listen` and
`Get-CimInstance Win32_Process` on the 5173 / 5174 / 8000 ports
revealed three stale dev-server processes:

| PID    | Role                       | Started      | Status                     |
| ------ | -------------------------- | ------------ | -------------------------- |
| 8712   | Vite (port 5173, IPv6 only) | 2026-05-01 17:06 | Stale (predated the entire PR chain by ~24h) |
| 20840  | Vite (port 5174, IPv6 only) | 2026-05-02 17:23 | Newer but pre-`641df40`    |
| 29048  | Backend uvicorn (parent reloader, port 8000) | 2026-05-02 19:17 | Pre-`641df40`; missed reload  |

The backend was launched in `--reload` mode (confirmed by
`Started reloader process [29048] using WatchFiles` + worker `[9796]`
in its log) but `WatchFiles` never re-imported `cli_mcp_writer`,
`cli_mcp_backups`, `browser_probe`, or `oauth_marketplace`. The
endpoints from `4df3d83`, `45ec228`, `3af8601`, and `641df40` were
all 404 against the live process. Hot-reload did not catch the new
modules added after the original boot.

`Stop-Process` on the parent reloader (`29048`) did not free port 8000
because the worker (`9796`) had inherited the listening socket. Killing
the worker freed the port. All three processes were then stopped
safely (no `--force` on data, no DB touched, no var/ deletion).

### Restart

Backend relaunched via `cd /d/Ideas/Daena/backend && ./.venv/Scripts/python.exe run.py`.
First attempt with the global `C:\Python311\python.exe` died on
`ModuleNotFoundError: No module named 'structlog'` -- corrected to use
the project-local `.venv` per CLAUDE.md Tooling Rule. Backend now reports
`status=warming` then `status=healthy` on `/api/v1/health`, listens on
`127.0.0.1:8000`, and writes `.daena-port = 8000` after FastAPI startup
completes.

Frontend relaunched via `cd /d/Ideas/Daena/frontend && /c/Program\ Files/nodejs/npm run dev`.
(Bash `cmd /c "npm.cmd run dev"` died immediately with cmd printing only
its banner -- the direct npm path is the working invocation on this
host.) Vite ready on `http://localhost:5173/` (IPv6 loopback only;
`127.0.0.1` returns 000 -- this is Vite's default and not a regression).
Vite proxy seeded with `127.0.0.1:8000` and self-heals on
`backend/.daena-port` change.

### Backend freshness verified via OpenAPI

`curl http://127.0.0.1:8000/openapi.json` enumerates the full marketplace
surface from the PR chain:

```
/api/v1/connections/v2/marketplace/cards
/api/v1/connections/v2/marketplace/install-plan/{entry_id}
/api/v1/connections/v2/marketplace/install-plan/{entry_id}/preview      <- 4df3d83
/api/v1/connections/v2/marketplace/install-plan/{entry_id}/apply        <- 4df3d83
/api/v1/connections/v2/marketplace/install-backups                      <- 641df40
/api/v1/connections/v2/marketplace/install-backups/restore              <- 641df40
/api/v1/connections/v2/marketplace/browser-probe/{entry_id}             <- 45ec228
/api/v1/connections/v2/marketplace/oauth/{entry_id}/start               <- 3af8601
```

All eight endpoints return `401 AUTH_FAILED` when probed without a
token (correct gate behavior); `cards` returns `200` with 55 entries
when probed via the live frontend session.

CLI runtime probes are reachable through the existing
`/{connection_id}/probe` route via `PROBE_REGISTRY` -- not a separate
marketplace endpoint -- which is by design for pre-seeded V2 rows.

### Probe registry coverage

`backend/app/services/connection_v2/probes/__init__.py :: install_all_probes()`
registers 5 of 6 expected kinds:

| Kind          | Probe class       | Registered? |
| ------------- | ----------------- | ----------- |
| `api_provider` | `ProviderProbe`   | yes         |
| `mcp_server`  | `McpServerProbe`  | yes         |
| `cli_runtime` | `CliRuntimeProbe` | yes         |
| `oauth_app`   | `OAuthAppProbe`   | yes         |
| `skill_pack`  | `SkillPackProbe`  | yes         |
| `local_model` | NONE              | MISSING     |

Note: the browser pre-install probe is intentionally NOT in the per-kind
registry because it is a marketplace-side check (`marketplace/browser-probe/{entry_id}`),
not a runtime liveness probe -- that distinction is correct.

## Live UI smoke (12 verifications)

Authenticated as a freshly-registered FOUNDER user
`smoke-after-restore@example.com` (created via `/api/v1/auth/register`
with `tenant_name=smoke-after-restore`) -- no founder credentials were
printed or grepped. JWT seeded into `localStorage['daena_token']` via
Chrome DevTools MCP `evaluate_script`.

| #   | Check                                                                  | Result | Evidence |
| --- | ---------------------------------------------------------------------- | ------ | -------- |
| 1   | Backend fresh and on latest commit (`641df40`)                         | PASS   | OpenAPI exposes all 8 marketplace endpoints from the PR chain |
| 2   | Frontend fresh + proxying to right backend                             | PASS   | Vite ready in 1425ms, proxy target `http://127.0.0.1:8000`, mutates on `.daena-port` change |
| 3   | `/connections` shows Brain / Plugins / Advanced only                   | PASS   | `Brain` + `Plugins` always visible; `Advanced` appears only when `Show advanced` checkbox is on -- no other top-level tabs |
| 4   | Plugins grid loads cards                                               | PASS   | 55 cards rendered; counts: `0 connected / 0 needs auth / 0 installed / 55 available` (honest empty-tenant state) |
| 5   | A provider card opens detail drawer                                    | PASS   | Anthropic API "Details" -> drawer with capabilities, env var NAMES, install steps, vendor doc link |
| 6   | A provider Configure button goes to `/account/api-keys`                | PASS   | "Open Settings -> API Keys" inside provider drawer navigated to `/account/api-keys` |
| 7   | An MCP card opens install drawer                                       | FAIL   | All 17 MCP cards render `Install (disabled)`; the button is also disabled inside the detail drawer. `MCPInstallDrawer` is wired in `PluginCardView.tsx` but never reachable because backend returns `action_enabled=false` for every entry. |
| 8   | Install drawer has Restore previous backup link                        | BLOCKED | Cannot reach the install drawer (depends on #7). The drawer source contains the link (`MCPInstallDrawer.tsx` imports `MCPRestoreDrawer` and renders the "Restore previous backup..." link in every step), so the gap is purely action-mapping, not the drawer itself. |
| 9   | Browser/Computer-Use card shows Verify locally section                 | PASS   | Playwright drawer has `VERIFY LOCALLY` heading + safety advisory + `Verify locally` button (NOT disabled). Source check confirms section is rendered for every browser/computer-use kind. |
| 10  | No "Backend error" or "Not Found" visible                              | PASS   | `document.body.innerText` contains zero matches for `Backend error / Not Found / Failed to load / probe_unavailable`; console has zero errors and zero warnings; all `/api/v1/connections/v2/...` requests returned `200`. |
| 11  | No V1/V2 wording in normal view                                        | PASS   | `document.body.innerText` contains zero `V1` / `V2` / `connection_v2` strings while on the Plugins tab. |
| 12  | Advanced contains registry / debug / legacy only                       | PASS   | `AdvancedPanel` source enumerates 9 sections: Registry overview, Runtimes (V2), MCP servers (V2), OAuth apps (V2), Browser tools (V2), Local models (V2), Skill packs (V2), Legacy V1 panels, Discovery + endpoints. Amber banner reads "Advanced registry / debug view -- Internal V2 / V1 surfaces. Normal users should use the Plugins tab". |

## Live-blocking finding (will be repaired in PR-CONN-LIVE-PARITY-REPAIR)

JS audit of every primary action across all 55 cards:

```
Setup guide (disabled): 38
Install (disabled):     17
```

Every primary action is disabled. There are zero `Connect`, zero
`Configure`, zero `Test` buttons. The MCP install flow is end-to-end
implemented but the action mapping never enables the entry button.
The provider/subscription cards never reach `Configure` even though
`backend/.env` has provider keys for Gemini, Groq, Perplexity, and
vLLM (per the boot log `provider_keys=...configured: True...`).

This is the live parity gap the founder flagged. It will be repaired
in the next PR (PR-CONN-LIVE-PARITY-REPAIR), which will:

- repair the `action_enabled` / action-kind mapping in the backend
  marketplace card builder so MCP entries with a writer-supported
  `command_template` surface `Install`, OAuth apps with provider
  config surface `Connect` (or `Configure` if client config missing),
  API providers with a known key surface `Test` (or `Configure` if
  missing), and so on;
- register the missing `local_model` probe so Ollama / vLLM cards
  can be probed through the same registry as everything else;
- audit the Advanced "Runtimes (V2)" panel for any stale
  `probe_unavailable: no real probe implementation for kind 'cli_runtime'`
  message and add a regression test;
- preserve "Coming soon" badges only where no backend path exists
  (Browserbase, Cloudflare OAuth, GitLab, Hugging Face, Jira,
  MongoDB, Netlify, Notion OAuth, Perplexity Search, Redis,
  Sentry OAuth, Shopify, Stripe Connect, Vercel) and convert the
  rest to real actions;
- check + fix the modal black-screen bug if reproducible.

This smoke does not change product code. The action-mapping fix is
non-trivial (requires backend builder changes plus probe registration
plus tests) and belongs in the dedicated repair PR rather than a
silent inline edit.

## What was NOT changed

- No production deploy.
- No `USE_CONNECTION_REGISTRY_V2` flip.
- No vault `--apply`.
- No V1 file deletion.
- No secret printed or grepped (the founder rule on secrets
  prevented inspecting `.env` values; only the env-key NAMES were
  observed via boot log / OpenAPI surface).
- No new tabs added.
- No marketplace UI rewrite.
- No external scans, emails, DMs, webhooks, or messages.
- No probe truth flipped to `connected/callable` without a real probe.

## Cleanup

The transient smoke-test FOUNDER user
`smoke-after-restore@example.com` and tenant `smoke-after-restore`
remain in `daena_dev2.db`. They are dev-only artefacts; can be
deleted by the founder at any time. No production credentials were
provisioned and no external services were contacted.

## Files touched

This smoke produced exactly one file:

```
docs/Ultraview/CONNECTIONS_LIVE_SMOKE_AFTER_RESTORE.md   (this report)
```

No product code was modified.

## Stop and report

Smoke complete. 10/12 verifications pass; the two failures are
both downstream of the same `action_enabled=false` gating defect
which is the explicit subject of the next PR. Awaiting next direction.
