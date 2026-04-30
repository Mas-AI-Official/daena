# Frontend File Map

Scope: Connections / MCP / Plugins / Runtime / Brain UI inventory.
Generated: 2026-04-30. Branch: `D:\Ideas\Daena\frontend\src`.

## Pages (`src/pages/*.tsx`)

| Path | Purpose | In App.tsx? | Real backend? | Handlers wired? | Fake/demo? | Reco |
|---|---|---|---|---|---|---|
| `pages/ConnectionsPage.tsx` | Tab shell (Main Brain / Plugins / MCP) | Yes (`/connections`) | n/a (shell only) | Yes (tab switcher) | None | KEEP |
| `pages/SettingsPage.tsx` | 13 lazy settings tabs incl. Models & Runtimes | Yes (`/settings`, `/settings/:cat`) | Per-tab | Yes | None | KEEP |
| `pages/MindsPage.tsx` | 10-card gallery of department soul personas | Yes (`/minds`) | `/souls`, `/souls/proposals` | Yes (refine-all founder, navigate) | None | KEEP |
| `pages/MindDetailPage.tsx` | Single soul detail + refine + proposal review/diff | Yes (`/minds/:slug`) | `/souls/{slug}`, `/souls/{slug}/refine`, `/souls/proposals/{id}/{approve\|reject}` | Yes (founder-gated) | None | KEEP |

Note: `MindsPage` / `MindDetailPage` are about soul-personas, NOT runtime brain switcher. Naming is a known footgun (see "Surprises").

## Pages - Connections subdir (`src/pages/connections/`)

| Path | Purpose | In App.tsx? | Real backend? | Handlers wired? | Fake/demo? | Reco |
|---|---|---|---|---|---|---|
| `connections/MainBrainPanel.tsx` | New Main Brain tab - pick CLI runtime or API provider as primary | Indirect (mounted by ConnectionsPage) | `/runtimes`, `PUT /runtimes/primary`, `/runtimes/{id}/test` | All wired | None | KEEP |
| `connections/McpServersPanel.tsx` | MCP detected/registry/catalog/extensions panel | Indirect | `/mcp-sync/detected`, `/connections/mcp-registry`, `/connections/extensions`, `/connections/plugin-catalog`, `/mcp-sync/import`, `/connections/extensions/install`, `/connections/extensions/{key}/probe-auth` | All wired | None | KEEP |
| `connections/PluginsCatalogBrowser.tsx` | Codex-style connector catalog grid | Indirect | `/connections/instances`, `/connections/instances/install-defaults`, `/connections/instances/{id}/disconnect`, hook → `/connections/catalog` | All wired | None | KEEP |
| `connections/ConnectionsConnectors.tsx` | Legacy "plugins" tab w/ ConnectorRow + advanced per-tool perms (33 KB) | NOT mounted by current ConnectionsPage shell | `/connections/instances` (ConnectorRow direct POST) | Mostly wired; handler props expect parent | Imports hardcoded `CONNECTORS` from `catalog.ts` (~110 entries) | ARCHIVE |
| `connections/ConnectionsExtensions.tsx` | Legacy extensions tab w/ per-tool optimistic perms (26 KB) | NOT mounted (replaced by McpServersPanel) | `/connections/extensions/{id}/permissions`, `/connections/extensions/{id}` | Wired (parent-prop driven) | None (real persistence) | ARCHIVE |
| `connections/ConnectionsRuntimes.tsx` | Legacy "Mind Control" runtimes tab + CLIBridgeCard (31 KB) | NOT mounted (replaced by MainBrainPanel) | `/runtimes`, `/bridge/status`, `/bridge/token` | Wired | None | ARCHIVE (kept only if CLI Bridge moves to MainBrainPanel) |
| `connections/BrowseModal.tsx` | Legacy marketplace overlay for connectors+extensions | NOT mounted | `/connections/extensions/install`, OAuth helper | Wired | Reads `BROWSE_CONNECTORS_CATALOG`/`BROWSE_EXTENSIONS_CATALOG` hardcoded | ARCHIVE |
| `connections/catalog.ts` | 880 lines of hardcoded `CONNECTORS`, `BROWSE_*_CATALOG`, `CLOUD_PREINSTALLED_EXTENSIONS`, `SKILL_DESCRIPTIONS`, `CONNECTOR_MCP_EQUIVALENT` | Imported by archived components + `PluginsCatalogBrowser` (only `CONNECTOR_MCP_EQUIVALENT`) | None | n/a | Entire file is hardcoded data; backend `/connections/catalog` already supersedes most | ARCHIVE majority; KEEP only `CONNECTOR_MCP_EQUIVALENT` (move to small file) |
| `connections/installFlow.ts` | OAuth/api-token install state machine (208 LOC) | Imported by `ConnectorInstallDialog` | `/connectors/{slug}/install/start`, `/install/complete` | n/a | None | KEEP |
| `connections/oauth.ts` | `startOAuthConnect` helper (legacy) | Imported by archived components | OAuth popup flow | n/a | None | ARCHIVE w/ legacy components |
| `connections/shared.tsx` | `ConfigPanel`, `ContextMenu`, `PermissionSelect` (legacy) | Imported by archived components | n/a | n/a | None | ARCHIVE w/ legacy components |
| `connections/types.ts` | `ConnectorDef`, `Permission`, `ExtensionData`, `RuntimeData`, `TabKey` | Imported broadly | n/a | n/a | None | KEEP (split - RuntimeData/ExtensionData still live) |

## Pages - Settings subdir (`src/pages/settings/`)

| Path | Purpose | In App.tsx? | Real backend? | Handlers wired? | Fake/demo? | Reco |
|---|---|---|---|---|---|---|
| `settings/SettingsModelsRuntimes.tsx` | Local Ollama panel + API-key forms + read-only routing notice | Indirect (lazy via SettingsPage) | `/runtimes`, `/chat/model-registry`, `/dynamic-models/provision` | API-key save wired; Auto-Routing is read-only banner | "Auto Routing" section is intentional placeholder (banner says "frontend-only, removed") | REWRITE (or merge into MainBrainPanel) |

## Components (`src/components/`)

| Path | Purpose | In App.tsx? | Real backend? | Handlers wired? | Fake/demo? | Reco |
|---|---|---|---|---|---|---|
| `components/connections/ConnectorInstallDialog.tsx` | Codex-style install card; one dialog, 4 auth flows | Imported by `PluginsCatalogBrowser` & legacy `ConnectionsConnectors` | `/connectors/{slug}/install/info`, then `installFlow.ts` | Yes | None | KEEP |
| `components/chat/RuntimeSwapper.tsx` | Chat header dropdown to pick primary runtime | Mounted in chat header | Consumes `useRuntimeRegistry()` (no direct fetch) | Yes; rewrite 2026-04-29 deleted DEFAULT_RUNTIMES; shows "Detecting runtimes..." skeleton when empty | None (post-rewrite) | KEEP |

## Hooks (`src/hooks/`)

| Path | Purpose | Real backend? | Behaviour | Fake/demo? | Reco |
|---|---|---|---|---|---|
| `hooks/useConnectorCatalog.ts` | Fetches `/connections/catalog`; 5-min module cache; surfaces `error` | `GET /connections/catalog` | Honest; never falls back to hardcoded list | None | KEEP |
| `hooks/useRuntimeRegistry.ts` | Polls `/runtimes` every 30s; adapts to `RuntimeInfo`; listens for `daena:retry-pending` | `GET /runtimes` | Honest; `normalizeStatus` defaults unknown→offline | None | KEEP |

## API client (`src/lib/api.ts`, `src/lib/mutations.ts`) - relevant slices

| Path | Connection/MCP/runtime relevance | Reco |
|---|---|---|
| `lib/api.ts` | Axios instance; SILENT_PREFIXES list contains `/runtimes/`, `/connections/`, `/mcp/`, `/mcp-sync/`, `/dynamic-models/`. `silent` per-call override. ErrorStore/console.warn always run. | KEEP |
| `lib/mutations.ts` | Generic `deleteWithToast` / `batchDeleteWithToast`. No connection/MCP-specific paths. | KEEP |

## Routes registered in App.tsx (related)

| Route | Component | Status |
|---|---|---|
| `/connections` | `ConnectionsPage` (lazy) | Active |
| `/settings` + `/settings/:category` | `SettingsPage` (lazy) | Active |
| `/minds` | `MindsPage` (lazy) | Active |
| `/minds/:slug` | `MindDetailPage` (lazy) | Active |
| `/founder` → redirects to `/settings/governance` | n/a | Active legacy redirect |

No route exists for legacy `ConnectionsConnectors` / `ConnectionsExtensions` / `ConnectionsRuntimes` - the new `ConnectionsPage` shell only renders `MainBrainPanel`, `PluginsCatalogBrowser`, `McpServersPanel`.

## Buttons that exist but have no real handler

None found in the active path. All scanned files (current `ConnectionsPage` + 3 sub-panels + `ConnectorInstallDialog` + `RuntimeSwapper` + `MainBrainPanel` + Settings tabs + `MindsPage`/`MindDetailPage`) have functional `onClick` wiring backed by API calls.

Caveats:
- `ConnectionsConnectors.tsx` has `toast.info('Documentation for ${connector.name}')` for "View docs" - toast-only, no real link. (Archived candidate.)
- `ConnectionsConnectors.tsx` "Clear selection" → just clears local state + toast. (Archived candidate.)
- `SettingsModelsRuntimes` "Auto Routing" section is intentionally read-only banner (no buttons).

## Status badges based on mock/hardcoded data instead of backend

None found in the active path post-2026-04-29 honesty rewrite.

Historical only:
- `RuntimeSwapper.tsx` previously had `DEFAULT_RUNTIMES` const that hardcoded all runtimes as `status: 'online'` - DELETED 2026-04-29 per CLAUDE.md rule 17. Now shows "Detecting runtimes..." skeleton when prop is empty.
- `MainBrainPanel.tsx` `isRuntimeUsable()` uses real `installed && status === 'online' && is_authenticated` from backend payload. Honest.
- `McpServersPanel.tsx` "Callable" / "Not callable" badges only render after `probe[server_key]` is set by an actual `/probe-auth` POST.
- `PluginsCatalogBrowser.tsx` `StatusBadge` reads from real `instance.status` enum (`CONNECTED` / `INSTALLED` / `NEEDS_REAUTH` / `ERROR` / `DISCONNECTED`).

## Components that render data without ever calling an API

None on the active path. All renderers fetch from the backend or consume a hook that does.

## Stale/hardcoded enums

- `connections/catalog.ts` lines 1-880: hardcoded `CONNECTORS` (~110 entries), `BROWSE_CONNECTORS_CATALOG`, `BROWSE_EXTENSIONS_CATALOG`, `CLOUD_PREINSTALLED_EXTENSIONS`, `SKILL_DESCRIPTIONS`, `CONNECTOR_MCP_EQUIVALENT`. Backend `/connections/catalog` (consumed by `useConnectorCatalog`) is canonical now. Only `CONNECTOR_MCP_EQUIVALENT` is still imported by active path (`PluginsCatalogBrowser`).
- `SettingsModelsRuntimes.tsx` `PROVIDERS` const (lines 25-30) hardcodes 4 providers (anthropic / openai / google_gemini / perplexity). Backend has 9 providers (Ollama, Anthropic, OpenAI, Gemini, Groq, OpenRouter, Together, Perplexity, ...) - STALE.

## Recommendations summary by file

KEEP (active, honest, wired):
- `pages/ConnectionsPage.tsx`
- `pages/connections/MainBrainPanel.tsx`
- `pages/connections/McpServersPanel.tsx`
- `pages/connections/PluginsCatalogBrowser.tsx`
- `pages/connections/installFlow.ts`
- `pages/connections/types.ts`
- `pages/SettingsPage.tsx`, `pages/MindsPage.tsx`, `pages/MindDetailPage.tsx`
- `components/connections/ConnectorInstallDialog.tsx`
- `components/chat/RuntimeSwapper.tsx`
- `hooks/useConnectorCatalog.ts`, `hooks/useRuntimeRegistry.ts`
- `lib/api.ts`, `lib/mutations.ts`

ARCHIVE (replaced; not mounted anywhere):
- `pages/connections/ConnectionsConnectors.tsx`
- `pages/connections/ConnectionsExtensions.tsx`
- `pages/connections/ConnectionsRuntimes.tsx` (re-port CLIBridgeCard into MainBrainPanel first)
- `pages/connections/BrowseModal.tsx`
- `pages/connections/catalog.ts` (extract `CONNECTOR_MCP_EQUIVALENT` to a small dedicated file before archive)
- `pages/connections/oauth.ts`
- `pages/connections/shared.tsx`

REWRITE:
- `pages/settings/SettingsModelsRuntimes.tsx` - `PROVIDERS` enum is stale (4 vs backend's 9); "Auto Routing" section is a placeholder banner; consider folding live runtime UI into `MainBrainPanel` and keeping this tab to Local Ollama + API keys only.
