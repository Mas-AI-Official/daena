# PR-6: Connections / MCP / Runtime Readiness Closure — Report

**Date:** 2026-05-06
**Sprint:** DAENA-SPRINT-21-UI-BACKEND-WIRING-CLOSURE

## Verdict

**Honest already.** ADR-002 (connections rebuild, 2026-05-02) explicitly forbids the
"connected because keys exist" pattern. Every "Ready" / "Connected" pill in the
Connections UI is gated by a real probe.

## Verified surfaces

### MainBrainPanel.tsx (Connections → Brain tab)

- Indexes V2 truth by slug from `useConnectionsV2('cli_runtime')`.
- Comment in source (line 89-91): *"Phase 5 PR 2: V2 truth — only callable=true CLI runtimes can be pinned as Main Brain when USE_CONNECTION_REGISTRY_V2 is on (unless founder opts in to experimentalOverride)."*
- `isRuntimeUsable()` requires `installed && status==='online' && (subscription?.is_authenticated ?? true)`. Probes go through `GET /runtimes`.
- Provider error rendering shows `last_error_msg` + relative time (`{seconds}s ago`).

### McpServersPanel.tsx (Connections → Plugins tab)

- Probe failure helper `probeMessage(raw)` rewrites the MCP TaskGroup error into operator-actionable text: *"MCP process failed during startup. Check command, args, package, and required env vars."*
- Registry truth comes from `GET /api/v1/mcp/registry`.
- "Install" + "Probe/Test" + "Setup guide" actions are wired through the existing connector-install lifecycle.

### MarketplaceCard.tsx + PluginDetailDrawer.tsx

- Connector lifecycle states: `unconfigured / configured / connected / authenticated / failed / skill_pack`.
- "Coming soon" is reserved for the catalog metadata flag `install_method === 'coming-soon'` (connectors that aren't installable yet) — never used as a fake status pill.
- "Last checked" timestamp surfaces the most recent V2 probe time.
- Failure state renders the inline `v2_failure_reason` with a red border.

### BrainReadinessPanel.tsx

- 5-state truth ladder: `ready / configured_untested / not_configured / detected_offline / unknown`.
- Source comment: *"We never label a runtime 'connected' off key-presence alone."*
- Endpoints: `GET /api/v1/system/runtime-readiness` + `GET /api/v1/system/qe-readiness`.
- QE mode is rendered exactly as the backend emits it (`full / degraded / unavailable`); no rounding up.

### GoogleAccountSetupGuide.tsx + OpportunityInboxPage activation banner

- `GET /connections/google-activation-summary` is a pure DB read (no Google round-trip).
- Each blocker enumerates `{role, email|"OAuth client", missing[]}`. The activation banner deep-links to `/connections`.
- The Setup Guide page auto-probes on mount and shows `next_action` from the live readiness probe.

### ConnectorInstallDialog.tsx + OAuthConnectDrawer.tsx

- Install button gated by `GET /connectors/{slug}/install/info` probe.
- OAuth drawer gated by client-readiness check.
- Both surface backend refusal codes verbatim instead of generic "failed".

## What was NOT changed in this PR

The brief listed: replace dead Install with setup blockers, deep-link missing keys, etc.

Every one of those patterns is already shipped:
- Dead Install: `install_method='coming-soon'` renders as a metadata badge, not a button.
- Missing keys: `BrainReadinessPanel` shows `next_action` per runtime; chat composer suggests opening Provider Keys.
- Local runtime missing: `LocalModelsPanel` + `BrainReadinessPanel.safe_failure_reason` describe the install command.
- MCP not installed: `MCPInstallDrawer` + `McpServersPanel.shortCommand` show the install command.

## Hard rules respected

- [x] No fake "Connected" pills
- [x] No deploy
- [x] No code modified — UI was already correct
- [x] All wiring claims backed by direct grep + read of the listed files

## Next

PR-7: NUser browser crawl.
