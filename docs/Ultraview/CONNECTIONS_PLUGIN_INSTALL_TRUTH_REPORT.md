# Connections Plugin Install Truth Report

Date: 2026-04-30

## What Codex Changed Before This Pass

- Added `backend/app/api/v1/connector_install.py`.
- Added `frontend/src/components/connections/ConnectorInstallDialog.tsx`.
- Added `frontend/src/pages/connections/installFlow.ts`.
- Added `scripts/scrape_codex_plugins.py`.
- Expanded `backend/app/config/connector_catalog.json` to 116 connectors and copied Codex plugin skills into `D:\Ideas\Daena\skills\connector-*`.

## Problem Found

The Codex install dialog was real code, but it was wired into `frontend/src/pages/connections/ConnectionsConnectors.tsx`, which is not the active `/connections` route.

The active route is `frontend/src/pages/ConnectionsPage.tsx`, and its Plugins tab renders `frontend/src/pages/connections/PluginsCatalogBrowser.tsx`.

Result: the user still saw the old install/connect behavior even though the new dialog existed in the tree.

## Fixes Applied

- `frontend/src/pages/connections/PluginsCatalogBrowser.tsx`
  - Wires the active Plugins tab to `ConnectorInstallDialog`.
  - `Install` and `Connect account` now open the same rich install flow.
  - Renders connector skills from backend catalog metadata instead of only old tool stubs.
  - Shows MCP availability from backend catalog metadata.

- `frontend/src/hooks/useConnectorCatalog.ts`
  - Added rich connector fields: `slug`, `interface`, `auth`, `skills`, `skill_count`, `mcp_servers`, and `catalog_seeded`.

- `backend/app/api/v1/connections.py`
  - Merges database connector rows with `backend/app/config/connector_catalog.json`.
  - Keeps database state authoritative for installed/connected state.
  - Returns JSON-catalog-only connectors even if the DB seeder has not inserted them yet.

- `backend/app/api/v1/connector_install.py`
  - Creates missing DB connector rows from the JSON catalog on first install.
  - Keeps managed OAuth if provider env is configured.
  - Falls back to token setup when managed OAuth env is missing.
  - Implements MCP remote OAuth start/callback/token-exchange code for providers that expose OAuth metadata and dynamic client registration.
  - Falls back to token setup when a remote MCP provider does not expose usable OAuth metadata or registration.

- `frontend/src/components/icons/BrandIcons.tsx`
  - Added local Neon and Quicknode icon fallbacks to remove broken Simple Icons CDN requests.

## Verified Browser Evidence

Browser URL: `http://localhost:5173/connections`

- `/connections` loads Main Brain, Plugins, and MCP Servers tabs.
- Main Brain page contains the persisted Codex primary runtime.
- Plugins tab shows `116 apps`, `15 installed`, `1 connected`.
- Searching Cloudflare shows:
  - Cloudflare card.
  - `9 skills`.
  - MCP server available.
  - Skill names copied from Codex, including `agents-sdk`, `wrangler`, `workers-best-practices`, and related Cloudflare skills.
- Clicking Cloudflare `Connect account` opens the rich `Install Cloudflare` dialog.
- Dialog shows About, skills, MCP server URL, Try saying, privacy/terms, and install action.
- `POST /api/v1/connectors/cloudflare/install/start` now returns `method=mcp_remote_oauth`, `popup=true`, and a real Cloudflare authorization URL.
- `GET /api/v1/connectors/mcp-oauth/callback?state=bad&code=x` returns 400 with `Invalid or expired OAuth state`, proving the callback route is mounted and not shadowed.
- Browser console after this flow: 0 errors, 0 warnings.

## Verified API Evidence

Authenticated browser fetches through the Vite proxy:

| Endpoint | Result |
|---|---|
| `POST /api/v1/connectors/github/install/start` | 200, `method=api_token`, no popup, bearer token field, GitHub token settings URL |
| `POST /api/v1/connectors/cloudflare/install/start` | 200, `method=mcp_remote_oauth`, popup true, Cloudflare authorization URL returned |
| `GET /api/v1/connectors/mcp-oauth/callback?state=bad&code=x` | 400, invalid-state HTML returned |
| `POST /api/v1/connectors/figma/install/start` | 200, `method=api_token`, no popup, bearer token field, explicit OAuth metadata-not-discovered fallback reason |
| `POST /api/v1/connectors/hugging-face/install/start` | 200, `method=api_token`, no popup, bearer token field, Hugging Face token settings URL |

## What Is Real Now

- The active `/connections` Plugins tab uses the new rich install dialog.
- The 116-connector catalog is visible through the active backend endpoint.
- Codex plugin skills copied into Daena are rendered in the live UI.
- First install can seed a missing `Connector` DB row from the JSON catalog.
- GitHub no longer hard-fails with a missing OAuth client ID when token fallback is possible.
- Cloudflare now starts real MCP Remote OAuth through discovery, dynamic client registration, PKCE, and backend callback state.
- Cloudflare token exchange/persistence code is implemented behind `/api/v1/connectors/mcp-oauth/callback`.
- Figma does not fake OAuth; it falls back because Daena did not discover usable Figma MCP OAuth metadata.

## What Is Still Not Real

- Cloudflare was not completed through the provider consent screen in this pass, so token persistence after a real Cloudflare authorization code is implemented but not end-to-end proven.
- Figma is not one-click OAuth-connected; it still falls back to token setup because metadata discovery failed.
- Mirroring into global `~/.claude/skills` was not performed in this pass.
- Imported Codex skill files were not independently injection-scanned in this pass.
- No full frontend build/typecheck was possible in this Codex shell because Node still aborts at `ncrypto::CSPRNG(nullptr, 0)`.
- No full backend pytest was possible in this Codex shell because Python `asyncio` still fails importing `_overlapped` with `WinError 10106`.

## Next Correct Step

Manually complete the Cloudflare consent screen once in the browser, then verify Daena stores encrypted MCP OAuth tokens and can make an authenticated MCP health call. After that, investigate Figma's actual remote MCP OAuth endpoint or leave it honestly as token setup.

## 2026-04-30 Addendum: Fake Installed States Removed

### Problem Found

- Skill-only connector rows such as `Build macOS Apps` had `auth_type=none`, no `auth.method`, no MCP server, and no backend adapter. Backend defaulted missing `auth.method` to `api_token`, so `/connectors/build-macos/install/start` returned a bearer-token form. That was fake.
- Legacy `ConnectionService.install()` treated every no-auth connector as connected immediately. That made skill packs look installed or connected even when Daena could not call anything.
- The install dialog kept stale token form state, so Cloudflare could still show the previous bearer-token form even after backend returned `mcp_remote_oauth`.
- MCP Test could show raw `unhandled errors in a TaskGroup` or stale `not in bootstrap registry`.

### Fixes Applied

- `connector_install.py` resolves missing rich `auth.method` from `auth_type`.
- `auth_type=none` now routes to `_start_none`, which returns HTTP 409 for skill-pack-only rows.
- `ConnectionService` only treats no-auth rows as connected when `config_schema.callable_without_auth` is explicitly true.
- `PluginsCatalogBrowser` labels skill-only rows as `Skill pack` and shows `Not installable`.
- `ConnectorInstallDialog` clears stale token forms before a new install attempt.
- `McpServersPanel` and `mcp_invoker` sanitize TaskGroup and connection-closed errors and show `Not callable` with a reason.
- `probe_extension_auth` re-bootstraps MCP registry once when the in-memory bootstrap registry is stale.
- Removed broken SimpleIcons aliases for SendGrid and Statsig.

### Verified Evidence

- Browser `/connections` Plugins: Build iOS, Build macOS, and Build Web show `Skill pack` and `Not installable`.
- API `POST /api/v1/connectors/build-macos/install/start`: 409 with skill-pack-only detail.
- API `POST /api/v1/connectors/cloudflare/install/start`: 200, `method=mcp_remote_oauth`, `popup=true`, Cloudflare authorize URL, no token form.
- Browser Cloudflare dialog opens without bearer-token form.
- API `POST /api/v1/connections/extensions/filesystem/probe-auth`: 200, `alive=false`, useful MCP handshake failure reason.
- UI Filesystem Test shows `Not callable` plus row detail.
- Fresh browser `/connections` console: 0 errors, 0 warnings.

### Still Not Proven

- Cloudflare OAuth consent was not completed, so encrypted token persistence and authenticated MCP callability are still not proven.
- The MCP rows are present but several are not callable because their npm package, command, or env config fails during handshake.
- Full typecheck, build, and pytest remain blocked by local Node/Python host failures.
