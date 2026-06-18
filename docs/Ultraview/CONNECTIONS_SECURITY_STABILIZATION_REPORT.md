# Connections and Security Stabilization Report

Date: 2026-04-30

## Connections Findings

- The previous `/connections` page was centered on RuntimeTruthRegistry rows.
- The old `Import` action on that page called `POST /api/v1/runtime/import`, which only marked an item persisted in Daena's runtime truth JSON. It did not import from Claude, Codex, Gemini, or a plugin source.
- A real connector catalog already exists at `GET /api/v1/connections/catalog`. Current seeded count is 116 connectors.
- A smaller backend plugin catalog exists at `GET /api/v1/connections/plugin-catalog`. Current code-defined count is 23 plugins, several with MCP packages.
- A real MCP import path already exists at `GET /api/v1/mcp-sync/detected` plus `POST /api/v1/mcp-sync/import`. This reads CLI configs and runs `InstallScanner` before registry persistence.
- Main Brain support existed in `/api/v1/runtimes` and `PUT /api/v1/runtimes/primary`, but the new Connections page had lost the dedicated control.

## Fixes Applied

- Replaced the top-level Connections page with three tabs only:
  - Main Brain
  - Plugins
  - MCP Servers
- Restored Main Brain selection via `GET /api/v1/runtimes` and `PUT /api/v1/runtimes/primary`.
- Extended `PUT /api/v1/runtimes/primary` to accept configured API provider values such as `OPENAI`, `ANTHROPIC`, `GEMINI`, `PERPLEXITY`, and `GROQ`, because `ModelRouter` already honors those values as Primary Mind boosts.
- Updated Plugins to show the real 116-connector backend catalog, installed connector instances, and per-connector skill/tool cards.
- Added an MCP Servers panel that separates:
  - live Daena MCP registry rows
  - MCPs detected from Claude/Codex/Gemini config files
  - installable MCP packages from Daena plugin definitions
  - Claude Desktop config rows
- MCP import now uses `POST /api/v1/mcp-sync/import`, not the fake runtime truth persist action.

## Security Findings

- Security frontend was capable of timing out because it waited on multiple `/security/*` calls.
- Backend `/security/status` still did filesystem scan-history reads and PATH-based tool detection inside an async request handler.
- FastAPI docs recommend normal `def` or external threadpool handling for blocking file/API/database operations; direct sync work inside `async def` can block the request worker.

## Security Fixes Applied

- Moved security tool stats, scan history reads, and self-improvement metric reads off the event loop with `asyncio.to_thread`.
- Added short TTL caches for security tool stats and tool lists.
- Limited scan-history JSON parsing to recent candidate files before applying the final response limit.
- Added frontend fallback status so partial `/security/*` failures do not crash the page.
- Changed elevated security wording away from offensive labels in the dashboard chrome.
- Reworked scan rows to show report-style context: target, type, authorization scope, status, time, tool/runtime, finding count, and severity summary.

## Validation

- Python syntax compile passed for:
  - `backend/app/api/v1/runtimes.py`
  - `backend/app/api/v1/security_dashboard.py`
- Frontend build could not be executed from this Codex shell. Both system Node and bundled Codex Node abort with `ncrypto::CSPRNG` initialization failure. WSL also failed with `Wsl/Service/0x8007072c`.
- Local HTTP validation could not be executed from this Codex shell. `curl` and Python asyncio fail with Windows socket/provider errors (`WinError 10106` / `requested service provider could not be loaded or initialized`).

## Remaining Truth

- The stale `backend/.daena-port` currently reads `8000` from this shell while local HTTP checks fail. Backend/frontend runtime validation must be run from the normal terminal/browser session, not this broken Codex shell.
- Plugin catalog count is 116 connectors, not 146, based on `backend/app/config/connector_catalog.json` in the active tree.
- Backend plugin definitions count is 23, based on `backend/app/services/plugin_catalog.py`.

## 2026-04-30 Addendum: Codex Continuation

### Connections

- Verified in the browser at `http://localhost:5173/connections`.
- Main Brain tab shows Codex as persisted primary runtime: `Saved as codex`.
- Plugins tab loads the real connector catalog: `116 apps · 15 installed · 1 connected · catalog v2026-04-29.1`.
- Plugin `Install` creates a backend connector instance. It does not ask for credentials. Credential/OAuth flow is now reserved for `Connect account`.
- MCP tab still needs deeper install/callability work, but it renders the detected set instead of hiding the fifth row.

### Security Dashboard Performance

- `/api/v1/security/status` no longer waits on full PATH-based installed-tool detection.
- First status response now returns cached/stale/pending tool inventory immediately and refreshes inventory in the background.
- `/api/v1/security/tools` now uses the cached installed-tool snapshot instead of probing every tool on every page load.
- Frontend shows `checking inventory` / `installed, refreshing` instead of falsely marking tools missing while the background scan is still running.
- Browser evidence after patch:
  - `/api/v1/security/status`: 200 in 397-569 ms.
  - `/api/v1/security/tools`: 200 in 10-25 ms.
  - `/api/v1/security/shields`: 200 in 9 ms.
  - `/api/v1/security/opsec/status`: 200 in 10-31 ms.
- Security page and Tools tab produced no browser console warnings/errors after reload.

### Security Tool Install Guard

- A preserved browser network log showed an unintended `POST /api/v1/security/tools/install-all`.
- The background job reached `prowler`, `scoutsuite`, and `trufflehog` before backend reload killed the job. Daena now detects those three as installed.
- This was not acceptable as a side effect. The endpoint is now hardened:
  - `POST /api/v1/security/tools/install/{name}` without `confirm=install-security-tool` returns 409.
  - `POST /api/v1/security/tools/install-all` without `confirm=install-security-tool` returns 409.
  - `dry_run=true` still returns the plan without spawning commands.
  - a cooperative `POST /api/v1/security/tools/install-all/cancel/{job_id}` endpoint now exists for future jobs.
- No uninstall was performed. Removing packages is local destructive cleanup and could break the Python environment; it needs explicit approval.
