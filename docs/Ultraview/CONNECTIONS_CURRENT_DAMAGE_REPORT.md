# Connections System -- Current Damage Report
**Generated:** 2026-04-30
**Branch:** rebuild-connections-mcp-runtime
**Sources:** docs/_explore/01_damage_findings.md, docs/_explore/05_lying_ui_findings.md

## Executive verdict

The Connections / MCP / Plugins / Runtime stack is a half-finished rebuild on top of a still-active legacy monolith, where six unrelated truth dimensions (detected / configured / imported / persisted / reachable / callable / authenticated) have been collapsed into single optimistic UI badges. The 2026-04-29 honesty refactor (ADR-001) deleted the worst frontend offender (`RuntimeSwapper.DEFAULT_RUNTIMES`), but the deeper sin survives: every CLI adapter's `check_health` returns ONLINE on binary presence alone, and `connection_service._status_for_install` emits CONNECTED for any `auth_type=none` row or any row with a credentials dict, with no upstream probe. The chat header dot is green for runtimes that will fail the next `check_subscription()` call.

Compounding the damage, an unfinished modular rebuild (`pages/connections/MainBrainPanel`, `McpServersPanel`, `PluginsCatalogBrowser`) lives alongside the legacy monolith (`ConnectionsConnectors`, `ConnectionsExtensions`, `ConnectionsRuntimes`, `BrowseModal`) -- the new shell mounts only the first three, but the legacy files still compile, still import 880 lines of hardcoded `catalog.ts`, and were never deleted. Two parallel runtime registries (`RuntimeRegistry` adapter-driven vs `RuntimeTruthRegistry` JSON-persisted) feed two different API surfaces (`/runtimes` plural vs `/runtime` singular) which the frontend calls inconsistently. No regression evidence exists for the entire 2026-04-30 connections rebuild -- the audit pass crashed on `ncrypto::CSPRNG` and `WinError 10106` before any test or build ran.

## P0 -- must fix before V2 ships (blocking, user-visible lies)

| # | Symptom | Location (file:line) | Severity | Quoted evidence |
|---|---------|----------------------|----------|------------------|
| 1 | CLI adapter `check_health` returns ONLINE on binary presence alone (5 files, identical pattern) | `backend/app/services/runtimes/adapters/claude_code.py:182-186`, `codex.py:93-97`, `gemini_cli.py:59-63`, `grok_cli.py:49-53`, `mcp_bridge.py:88-93` | P0 | "Binary present = ONLINE, no auth or RPC check" |
| 2 | `_status_for_install` returns CONNECTED without probing upstream | `backend/app/services/connection_service.py:131-143` | P0 | "if cls._is_no_auth_connector(connector): return ConnectorStatus.CONNECTED.value" |
| 3 | Demo mode forges assistant responses when LLMs fail | `backend/app/services/chat_orchestrator.py:4155-4162` | P0 | "Demo mode: return mock response instead of error" |
| 4 | `_status_for_install` flips to CONNECTED on credentials presence alone | `backend/app/services/connection_service.py:142` | P0 | "if credentials: return ConnectorStatus.CONNECTED.value" |
| 5 | "Callable" pill driven by string-prefix match on backend message | `frontend/src/pages/connections/McpServersPanel.tsx:296` | P0 | "probe[entry.server_key].startsWith('Alive')" |
| 6 | "Installed" badge fires on package-name match in registry, not health | `frontend/src/pages/connections/McpServersPanel.tsx:369,379` | P0 | "plugin.mcp_package && livePackages.has(plugin.mcp_package)" |
| 7 | "Install MCP" writes JSON config but never spawns server | `frontend/src/pages/connections/McpServersPanel.tsx:407` | P0 | Toast says "MCP installed and persisted" -- writes file only |
| 8 | "Connected via subscription" trusts CLI's loggedIn flag (Linux Claude lies) | `frontend/src/pages/settings/SettingsLLM.tsx:91` | P0 | "subscriptions.filter((s) => s.is_authenticated)" |
| 9 | Identity/quota duplicate Masoud rows | `/settings/user`, tenant/quota tables | P0 | "duplicate Masoud Masoori identity/plan surfaces" |
| 10 | `/runtime/import` faked imports (legacy) | `POST /api/v1/runtime/import` | P0 | "only marked an item persisted in Daena's runtime truth JSON" |
| 11 | MCP detection vs registry count mismatch | `/mcp-sync/detected` (5) vs `/connections/mcp-registry` (4) | P0 | "detection count and rendered/registered count were using different sources" |
| 12 | `install-all` security tools installed without confirm gate | `POST /api/v1/security/tools/install-all` | P0 | "background job reached prowler, scoutsuite, and trufflehog" |

## P1 -- structural problems that produce P0s

| # | Problem | Location | Severity | Why this matters |
|---|---------|----------|----------|------------------|
| 1 | Two parallel runtime registries with no shared data | `services/runtimes/registry.py` + `services/runtime_truth_registry.py` | P1 | UI calls both; counts diverge; either could be stale |
| 2 | Two parallel MCP discovery paths register under different `server_key`s | `services/mcp_bootstrap.py` + `services/mcp_sync/detector.py` | P1 | Some servers registered twice |
| 3 | OAuth state stored in two ephemeral in-memory dicts (Redis available but unused) | `connector_install.py._MCP_OAUTH_STATES`, `connector_oauth.py._oauth_states` | P1 | "production: use Redis or DB" comment in code; both scrap on restart |
| 4 | OAuth client creds in three places (env / JSON file / vault) | `core.config.Settings`, `oauth_credentials_store.py` (.daena_oauth_overrides.json), `core.vault` | P1 | "For production, this should be replaced by the AES-256 secret vault" |
| 5 | `dynamic_model_service` imports `_PROVIDER_MAP` private dict from `model_registry` | `services/dynamic_model_service.py` | P1 | Refactor in registry breaks dynamic provisioning silently |
| 6 | `MCPTool` defined twice with different shapes | `services/mcp/server.py` + `services/mcp_registry.py` | P1 | Same name, different shape -- easy to confuse on import |
| 7 | Legacy `ConnectionsPage.tsx` monolith still active alongside `pages/connections/*` | `frontend/src/pages/connections/*` | P1 | Modular split unfinished |
| 8 | Cloudflare OAuth not proven end-to-end | `/connectors/mcp-oauth/callback` | P1 | "implemented but not end-to-end proven" |
| 9 | Figma OAuth metadata discovery failed | `/connectors/figma/install/start` | P1 | "falls back to token setup because metadata discovery failed" |
| 10 | Provider rows mislabeled `failed` when only env key exists (no probe) | `/runtime/truth` | P1 | "fake failed/imported to configured_untested when only a key exists" |
| 11 | Daena MCP package marked persisted because file existed on disk | `services/runtime_truth_registry.py:491` | P1 | "Daena MCP package existing on disk is not persistence" |
| 12 | `/security/status` did sync FS reads inside async handler | `backend/app/api/v1/security_dashboard.py` | P1 | "filesystem scan-history reads ... inside an async request handler" |
| 13 | `gitnexus`/`local-llm` MCPs detected but not callable | runtime truth | P1 | "not callable from backend path evidence" |
| 14 | vLLM `127.0.0.1:8080` failed; backend-local Ollama failed | runtime detection | P1 | "Configured vLLM endpoint ... failed connection attempts" |
| 15 | Browse marketplace catalog frontend-static, not DB | `ConnectionsPage.tsx` browse modal | P1 | "browse modal extension catalog is still frontend-static" |
| 16 | `web_search_stub` in cognitive prod code | `services/laevateinn/tool_augmented.py` | P1 | "Multiple web_search_stub references" |
| 17 | `laevateinn.py` is a placeholder | `api/v1/laevateinn.py` | P1 | "placeholder until fully wired" |
| 18 | `daena-mcp` package unpublished to npm | `packages/daena-mcp/package.json` | P1 | README admits "npm install -g returns 404"; blocks one-line Claude Desktop install UX |
| 19 | `daena_audit_query` is a TODO scaffold | `packages/daena-mcp/src/tools/audit.ts` | P1 | "aggregate mode not yet designed" |
| 20 | benchmarks `suite.py` measures pipeline overhead with `asyncio.sleep(0)` placeholders | `backend/app/services/benchmarks/suite.py:80-115` | P1 | "All five pipeline stages are asyncio.sleep(0) placeholders" |

## P2 -- debt and duplication

| # | Problem | Location | Severity | Cleanup recommendation |
|---|---------|----------|----------|------------------------|
| 1 | MCP Test surfaced raw `TaskGroup` errors | `McpServersPanel`, `mcp_invoker` | P2 | Sanitize handshake errors to `Not callable: <reason>` |
| 2 | Install dialog kept stale token form state | `ConnectorInstallDialog` | P2 | Clear state on every open |
| 3 | Header `AGI ACTIVE` wording mismatched semantics | `Header.tsx` | P2 | Rename to AUTOPILOT ON/OFF |
| 4 | RAG/Obsidian status has no first-class API | `/memory/*` | P2 | Implement or label honestly |
| 5 | Webhook UI exists but no backend route | `SettingsDeveloper.tsx` | P2 | Either build route or remove section |
| 6 | `SettingsModelsRuntimes.PROVIDERS` const hardcodes 4 providers (backend has 9) | `frontend/src/pages/settings/SettingsModelsRuntimes.tsx:25-30` | P2 | Replace with backend-driven list |
| 7 | `connector_catalog.json` (3352 lines) needs per-category split | `backend/app/config/connector_catalog.json` | P2 | Split for editability |
| 8 | `api/v1/connections.py` (1150 LOC, 6 concerns) too big | `backend/app/api/v1/connections.py` | P2 | Split into router + service helpers |
| 9 | `services/model_router.py` (1464 LOC, mixed strategies) | `backend/app/services/model_router.py` | P2 | Split routing strategies |
| 10 | `heartbeat/work_queue.py` vs `autopilot/background_queue.py` | both files | P2 | Document or unify "two task-queue mental models" |
| 11 | `ScanWalkthroughPage.tsx` generates `Math.random()` IDs not synced to backend | `frontend/src/pages/ScanWalkthroughPage.tsx:192` | P2 | Use backend-issued IDs |
| 12 | `SettingsGeneral` import success toast fires regardless of response body | `frontend/src/pages/settings/SettingsGeneral.tsx:266,269` | P2 | Inspect response before toast |
| 13 | `system_access.py` write/copy/move always `return True` | `backend/app/services/agent_core/system_access.py:63,92,98` | P2 | Verify side effects before returning |
| 14 | `daena_vp.py` placeholder `provider=ANTHROPIC` | `backend/app/services/daena_vp.py:485` | P2 | Resolve real provider before audit log |
| 15 | `dynamic_model_service.py` placeholder `provider=OLLAMA` for unknown | `backend/app/services/dynamic_model_service.py:101` | P2 | Use UNKNOWN sentinel |
| 16 | `connector_install.py:160-161` docstring still documents `connected: True` for auth=none | docstring lie | P2 | Update docstring to match 409 behavior |
| 17 | `vuln_scanner_agent.py:163` localhost auto-pass without policy check | `backend/app/services/daenabot/vuln_scanner_agent.py:163` | P2 | Run policy gate before allowlist |
| 18 | `real_benchmarks.py` 5 occurrences of heuristic `return True` in eval scoring | `backend/app/services/benchmarks/real_benchmarks.py:1502-1548` | P2 | Strict pass/fail; document partial-match logic |
| 19 | `extension_scanner.py:148` -- empty `tools` list still emits `enabled=True` | `backend/app/services/extension_scanner.py:148` | P2 | Disable extensions with empty tools |
| 20 | `oauth_credentials_store.py` JSON file -- comments admit needs vault | `services/integrations/oauth_credentials_store.py` | P2 | Migrate to AES vault |

## Specific lies the UI tells today

(citations from `docs/_explore/05_lying_ui_findings.md`)

- "Callable" / "Not callable" pill = string-prefix match: `frontend/src/pages/connections/McpServersPanel.tsx:296` -- `"probe[entry.server_key].startsWith('Alive')"`
- "Installed" badge = name-only registry membership: `frontend/src/pages/connections/McpServersPanel.tsx:369,379` -- `"livePackages.has(plugin.mcp_package)"`
- "${serverKey} is callable" toast on first `tools/list` reply, not persisted: `frontend/src/pages/connections/McpServersPanel.tsx:218`
- "Skill pack only..." copy fired by platform-name string match, not adapter introspection: `frontend/src/pages/connections/PluginsCatalogBrowser.tsx:98`
- Runtime status dot green when CLI is installed but unauthenticated: `frontend/src/components/chat/RuntimeSwapper.tsx:29-43`
- Hardcoded "Not connected" badge with no probe: `frontend/src/pages/settings/SettingsDeveloper.tsx:90`
- "Connected" pill = "instance row exists in DB": `frontend/src/pages/connections/ConnectionsConnectors.tsx:277`
- "${liveMcpCount} plugins live and callable right now" -- "live and callable" = `Set.has()` over registry rows: `frontend/src/pages/connections/ConnectionsConnectors.tsx:608`
- "${mcp.name} installed. The MCP server will prompt you to sign in..." on POST success regardless of probe: `frontend/src/pages/connections/OAuthSetupModal.tsx:81`
- Per-tool "installed/missing" from backend dict that uses path-lookup not exec: `frontend/src/pages/security/SecurityOverview.tsx:222-231`
- "connected via subscription" trusts CLI lying loggedIn flag: `frontend/src/pages/settings/SettingsLLM.tsx:91`
- "imported" tag appended client-side regardless of response success: `frontend/src/pages/settings/SettingsGeneral.tsx:266,269`

## Specific lies the backend tells today

(citations from `docs/_explore/05_lying_ui_findings.md`)

- `_status_for_install` returns CONNECTED for `auth_type=none` rows: `backend/app/services/connection_service.py:139-143` -- `"if cls._is_no_auth_connector(connector): return ConnectorStatus.CONNECTED.value"`
- Same function flips CONNECTED on credentials presence: `backend/app/services/connection_service.py:142` -- `"if credentials: return ConnectorStatus.CONNECTED.value"`
- Five CLI adapters return ONLINE on binary presence (no LLM round-trip): `claude_code.py:182-186`, `codex.py:93-97`, `gemini_cli.py:59-63` (admits "gemini --version hangs when not authenticated"), `grok_cli.py:49-53`, `mcp_bridge.py:88-93`
- `chat_orchestrator.py:4155-4162` -- demo mode forges responses, audited as `provider="demo"` but streamed as normal assistant message
- `benchmarks/suite.py:91-107` -- `"asyncio.sleep(0)  # Placeholder for actual SecurityGate call"` x 8 stages -- pipeline overhead reports near-zero ms
- `daena_vp.py:485` -- `"provider=ModelProvider.ANTHROPIC,  # placeholder"` makes audit trail record wrong provider
- `dynamic_model_service.py:101` -- `"provider=ModelProvider.OLLAMA,  # placeholder for unknown"` records unknown failures as Ollama failures
- `chat_orchestrator.py` demo response forge when LLMs all fail
- `security_operations_agent.py:67` -- `"# demo runs inside a single worker process."` indicates demo path active in production
- `connector_install.py:160-161` -- docstring still documents `connected: True` for auth=none branch (behavior was fixed at line 686 to raise 409)
- `agent_core/system_access.py:63,92,98` -- write_file/copy_file/move_file always `return True` after subprocess; partial writes pass
- `real_benchmarks.py:1502-1548` -- 5 occurrences of `return True` in heuristic graders inflate benchmark scores
- `daenabot/vuln_scanner_agent.py:163` -- `"return True, \"localhost/private (always allowed)\""` waves through policy check
- `extension_scanner.py:148` -- emits `enabled=True` even when `tools` list is empty
- Endpoint `POST /connections/install` (`connections.py:323`) returns `success=True` for DB inserts only, no upstream probe
- Endpoint `POST /connections/extensions/install` (`connections.py:655`) -- success means "we wrote the JSON file", not "MCP server responds"

## Two-registry problem (root architectural sin)

Two parallel runtime registries co-exist, each with its own persistence model and API surface, with no shared data layer. The frontend calls both. Counts diverge; either can be stale.

| Surface | Frontend file | Backend route | Backend service | Truth model |
|---------|---------------|---------------|------------------|--------------|
| Chat header dot | `components/chat/RuntimeSwapper.tsx` | `GET /runtimes` | `services/runtimes/registry.RuntimeRegistry` | Adapter-driven, in-memory cache, health from `check_health()` (lying -- binary presence) |
| Main Brain panel | `pages/connections/MainBrainPanel.tsx` | `GET /runtimes`, `PUT /runtimes/primary` | `services/runtimes/registry.RuntimeRegistry` | Same as above |
| Settings runtimes | `pages/settings/SettingsModelsRuntimes.tsx` | `GET /runtimes`, `/dynamic-models/provision` | RuntimeRegistry + DynamicModelService | Same |
| Runtime Truth (newer) | not yet bound to UI | `GET /runtime/truth`, `/runtime/refresh`, `/runtime/import`, `/runtime/health-check`, `/runtime/test-call` | `services/runtime_truth_registry.RuntimeTruthRegistry` | JSON-persisted under `var/`, broader scope: providers + MCP + local models |
| MCP detection | `pages/connections/McpServersPanel.tsx` | `/mcp-sync/detected` | `services/mcp_sync/detector.py` (reads ALL CLI configs) | Read-only filesystem scan |
| MCP bootstrap | (lifespan startup) | n/a | `services/mcp_bootstrap.py` (reads `claude_desktop_config.json` only) | Adapter cache feed |

## Prior unfinished rebuild attempts already in tree

Untracked files representing previous Claude session rebuilds that were started but never completed:

- `backend/app/api/v1/connector_install.py` (848 LOC) -- new unified install dialog backend
- `frontend/src/components/connections/ConnectorInstallDialog.tsx` -- matching frontend component
- `frontend/src/pages/connections/installFlow.ts` (208 LOC) -- OAuth/api-token state machine
- `scripts/scrape_codex_plugins.py` -- Codex plugin scraper (re-runnable, idempotent)
- `backend/app/config/connector_catalog.json` -- expanded to 116 connectors v `2026-04-29.3`
- `skills/connector-*` folders -- copied from Codex plugins

CODEX_BRUTAL pass: `RuntimeTruthRegistry` service + `/api/v1/runtime/*` endpoints; `/connections` rebuilt as "Runtime & Connections Center" -- never bound to UI.

SEC_STAB pass: 3-tab `/connections` (Main Brain / Plugins / MCP Servers); MCP Servers panel separating live registry / detected / installable / Claude Desktop config -- live but legacy ConnectionsPage.tsx monolith STILL ACTIVE alongside `pages/connections/*`.

FE_BE_TRUTH 2026-04-29 repairs: `/connections/extensions/install`, `/connectors/{id}/oauth/authorize`, MCP sync hooks; new `/memory/status` honest endpoint; deleted `RuntimeSwapper.DEFAULT_RUNTIMES`, fake departments, fake `/export`/`/compact` slash cmds, fake cost toast.

**Status: rebuild unfinished.** Modular tree exists; legacy monolith never deleted; CLI Bridge still in legacy file; catalog.ts hardcodes still imported by archived components.

## What is NOT broken (good news section -- avoid replacing what already works)

**Frontend honest paths** (post-2026-04-29 ADR-001 refactor):
- `pages/ConnectionsPage.tsx` shell -- tab switcher only, no fake state
- `pages/connections/MainBrainPanel.tsx` -- `isRuntimeUsable()` uses real `installed && status === 'online' && is_authenticated` from backend
- `pages/connections/PluginsCatalogBrowser.tsx` -- `StatusBadge` reads real `instance.status` enum
- `components/connections/ConnectorInstallDialog.tsx` -- 4 auth flows wired correctly
- `components/chat/RuntimeSwapper.tsx` -- post-rewrite: shows "Detecting runtimes..." skeleton instead of fake online pills
- `hooks/useConnectorCatalog.ts` -- 5-min module cache, never falls back to hardcoded list, surfaces `error`
- `hooks/useRuntimeRegistry.ts` -- polls `/runtimes` every 30s, `normalizeStatus` defaults unknown -> offline
- `lib/api.ts` -- silent prefixes contain connection routes; ErrorStore/console.warn always run
- `lib/mutations.ts` -- generic `deleteWithToast` / `batchDeleteWithToast`

**Backend honest paths**:
- `services/connection_service.py` -- vault encrypt/decrypt for credentials (per-tool permission_level honest)
- `services/mcp_invoker.py` (199 LOC) -- real MCP handshake via `mcp.ClientSession`
- `services/mcp_registry.py` (592 LOC) -- DB-backed, `hydrate_from_db` on startup -- matches ADR-001
- `services/runtime_truth_registry.py` -- JSON-persisted truth, broader scope (newer/cleaner than `runtimes.py`)
- `services/integrations/oauth_service.py` -- real OAuth + token exchange + refresh
- `services/integrations/integration_router.py` -- permission check + vault decrypt + client.execute()
- `services/runtimes/health_tracker.py` -- per-provider circuit breaker working as designed
- `services/runtimes/recovery_monitor.py` -- background half-open circuit reopener
- `services/providers/ollama.py:58-66` -- actually GETs `/api/tags` (counter-example, NOT lying)
- `backend/app/api/v1/connections.py:877-893` (`probe-auth`) -- actually opens an MCP stdio session
- `services/dynamic_model_service.py:111-113` -- actually calls `provider.health_check()`
- `models/connections.py`, `models/mcp_server.py`, `schemas/connections.py` -- DB models honest
- `config/connector_catalog.json` v `2026-04-29.3` -- 116-entry catalog usable as V2 spine

**Daena-MCP package**:
- `packages/daena-mcp/src/index.ts` -- solid stdio scaffolding, bridge handshake/heartbeat shipped
- `packages/daena-mcp/src/daena-client.ts` -- clean envelope handling, error taxonomy
- `packages/daena-mcp/src/tools/{status,chat,memory,governance}.ts` -- production-quality
