# Connections Rebuild — Archive Log

**Branch:** `rebuild-connections-mcp-runtime`
**Archive root:** `archive/connections_rebuild_20260430_171410/`
**Started:** 2026-04-30 17:14 UTC (Phase 0)
**Phase 3 archive batch:** 2026-04-30 (this commit)

---

## Working principle

> **Archive first. Never delete first.** Every file replaced gets moved to `archive/connections_rebuild_20260430_171410/<original_path>` with a row below.
>
> Hard deletion is post-V2 only, founder-gated, with 14-day grace minimum.

## Phase 3 batch (2026-04-30) — frontend pages/connections/* legacy components

All 7 moves verified:
- Branch confirmed: `rebuild-connections-mcp-runtime`.
- gitnexus impact analysis run per file: all `risk: LOW`, `impactedCount: 0`.
- Cross-tree grep verified: only consumers of each archived file were other archived files in the same batch.
- Live V2 surface (`MainBrainPanel`, `McpServersPanel`, `PluginsCatalogBrowser`, `OAuthSetupModal`, `installFlow.ts`, `types.ts`, `catalog.ts`, `components/connections/ConnectorInstallDialog.tsx`) untouched.
- All backend, chat, dashboard, departments, tasks, files modules untouched.

| # | Original path | Archive path | Why archived | Replacement file | Risk |
|---|---|---|---|---|---|
| 1 | `frontend/src/pages/connections/ConnectionsConnectors.tsx` (33 KB) | `archive/connections_rebuild_20260430_171410/frontend/src/pages/connections/ConnectionsConnectors.tsx` | Legacy "plugins" tab. Not mounted by current `pages/ConnectionsPage.tsx` shell. Imports hardcoded `CONNECTORS` from `catalog.ts`. Per `CONNECTIONS_FILE_MAP.md` ARCHIVE row + per gitnexus `impactedCount=0`. | `pages/connections/PluginsCatalogBrowser.tsx` (V2; already live) | LOW (no live consumers; was untracked in git) |
| 2 | `frontend/src/pages/connections/ConnectionsExtensions.tsx` (27 KB) | `archive/connections_rebuild_20260430_171410/frontend/src/pages/connections/ConnectionsExtensions.tsx` | Legacy extensions tab w/ per-tool optimistic perms. Not mounted (replaced by `McpServersPanel`). | `pages/connections/McpServersPanel.tsx` (V2; already live) | LOW (no live consumers) |
| 3 | `frontend/src/pages/connections/ConnectionsRuntimes.tsx` (31 KB) | `archive/connections_rebuild_20260430_171410/frontend/src/pages/connections/ConnectionsRuntimes.tsx` | Legacy "Mind Control" runtimes tab + CLIBridgeCard. Not mounted (replaced by `MainBrainPanel`). NOTE: any unique CLIBridgeCard logic must be reviewed for port to `MainBrainPanel.tsx` before this archive is hard-deleted (file map note). | `pages/connections/MainBrainPanel.tsx` (V2; already live) | LOW (no live consumers); follow-up: review CLIBridgeCard logic before hard-delete |
| 4 | `frontend/src/pages/connections/ConnectionsMcpServers.tsx` (54 KB) | `archive/connections_rebuild_20260430_171410/frontend/src/pages/connections/ConnectionsMcpServers.tsx` | Legacy Codex-parity MCP CRUD tab. Untracked in git, zero external imports. Per ADR-002 D-009. CRUD UX patterns (toggle / settings / add / delete) must be reviewed for port into V2 `McpServersPanel.tsx` Tools sub-tab BEFORE hard-delete. | `pages/connections/McpServersPanel.tsx` (V2; live) — Tools sub-tab will absorb the CRUD pattern in Phase 7 | LOW (no live consumers); follow-up: port CRUD pattern in Phase 7 frontend rebuild |
| 5 | `frontend/src/pages/connections/BrowseModal.tsx` (10 KB) | `archive/connections_rebuild_20260430_171410/frontend/src/pages/connections/BrowseModal.tsx` | Legacy marketplace overlay for connectors+extensions. Reads hardcoded `BROWSE_CONNECTORS_CATALOG`. Not mounted. Only consumers were `ConnectionsConnectors` + `ConnectionsExtensions` (both archived in this batch). | `pages/connections/PluginsCatalogBrowser.tsx` (catalog browse is now in-tab, not modal) | LOW |
| 6 | `frontend/src/pages/connections/oauth.ts` (5.5 KB) | `archive/connections_rebuild_20260430_171410/frontend/src/pages/connections/oauth.ts` | Helper `startOAuthConnect` used only by archived `BrowseModal` + `ConnectionsConnectors`. The V2 OAuth flow lives in `installFlow.ts` + `components/connections/ConnectorInstallDialog.tsx` (both KEEP). | `pages/connections/installFlow.ts` (V2 OAuth state machine; already live) | LOW |
| 7 | `frontend/src/pages/connections/shared.tsx` (5.2 KB) | `archive/connections_rebuild_20260430_171410/frontend/src/pages/connections/shared.tsx` | Helper components `ConfigPanel`, `ContextMenu`, `PermissionSelect` used only by archived `ConnectionsConnectors` + `ConnectionsExtensions` + `ConnectionsRuntimes`. | None needed; V2 panels do not use these helpers. New equivalents (if needed) will be added per V2 §9 Plugin Detail Drawer in Phase 7. | LOW |

### Files NOT moved this batch (intentional deferrals)

| Path | Status | Why deferred |
|---|---|---|
| `frontend/src/pages/connections/catalog.ts` (880 LOC) | DEFER → Phase 7 | Live consumer: `PluginsCatalogBrowser.tsx` imports `CONNECTOR_MCP_EQUIVALENT`. Extraction of this single constant into `connectorMcpMap.ts` is a frontend code change; founder constraint for Phase 3 is "no rebuild frontend yet." Per file map: "ARCHIVE (mostly); KEEP only `CONNECTOR_MCP_EQUIVALENT` (move to small file)." Move scheduled for Phase 7 frontend rebuild. |
| `frontend/src/pages/connections/OAuthSetupModal.tsx` (13 KB) | DEFER → ADR supplement / Phase 7 | Independent finding: zero external consumers (cross-tree grep + gitnexus). Same orphan pattern as `ConnectionsMcpServers.tsx`. NOT in the file map's ARCHIVE list, so not moved in this batch. Suggest founder add to next ADR supplement or roll into Phase 7 sweep. |

### Files NOT in scope for any phase of this rebuild

Founder explicit list (untouched):
- All Chat / Dashboard / Departments / Tasks / Files frontend pages.
- All backend modules outside `connections / mcp / runtime / connector / brain / model_registry` scope.
- `core/vault.py` (Phase 4a only).
- Security scanning workflows (HANDS OFF list per CLAUDE.md / SESSION-LOG 2026-04-19).

---

## Recovery procedure (if archive needs reversal)

1. `git log archive/connections_rebuild_20260430_171410/` to find this commit's SHA.
2. `cd D:\Ideas\Daena`.
3. For each file row above: `mv archive/connections_rebuild_20260430_171410/<orig_path> <orig_path>`.
4. The archived files were untracked in git at the time of move — so reversal restores them as untracked. Original behavior identical.

---

## Hard-delete schedule

These files MAY be hard-deleted from `archive/...` no earlier than:
- 14 days after V2 ships to production AND
- Founder explicit approval AND
- Verification that none of the deferred review items (CLIBridgeCard logic for ConnectionsRuntimes; CRUD patterns for ConnectionsMcpServers) need re-import.

Until then: archived files remain searchable and IDE-collapsable under `archive/connections_rebuild_20260430_171410/`.
