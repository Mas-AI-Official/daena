# Connections System -- File Map
**Generated:** 2026-04-30
**Sources:** docs/_explore/02_backend_file_map.md, docs/_explore/03_frontend_file_map.md, docs/_explore/04_mcp_package_map.md

## Backend files (by directory)

### api/v1/

| path | purpose | KEEP/ARCHIVE/REWRITE/WRAP | reason |
|------|---------|---------------------------|--------|
| `backend/app/api/v1/connections.py` (1150 LOC) | CMP catalog + per-tool permissions, plugin catalog overlay, install/connect/disconnect | KEEP (split) | "Split into router + service helpers (file is too big)" |
| `backend/app/api/v1/connector_install.py` (848 LOC) | Unified install dialog: oauth_managed / mcp_remote_oauth / api_token; PKCE; HTML callback | KEEP | "Refactor MCP-OAuth state into Redis/DB (ADR-001 honesty rule)" |
| `backend/app/api/v1/connector_oauth.py` (313 LOC) | Multi-provider OAuth (Google/GitHub/Figma/Slack/Canva) authorize -> callback -> refresh | KEEP | "Replace `_oauth_states` with Redis (sibling of connector_install)" |
| `backend/app/api/v1/mcp_server.py` (71 LOC) | Daena-as-MCP-server JSON-RPC: list_tools / call / jsonrpc | KEEP | "Thin pass-through, fine as-is" |
| `backend/app/api/v1/mcp_sync.py` (235 LOC) | Detect MCPs in Claude/Codex/Gemini CLI configs + one-click import via install_scanner | KEEP | "Clean route layer; no dependencies on dead code" |
| `backend/app/api/v1/runtime.py` (116 LOC) | NEW singular `/runtime` API -> `RuntimeTruthRegistry` (truth/refresh/import/health-check/test-call/patch) | KEEP | "Newer/cleaner than `runtimes.py`" |
| `backend/app/api/v1/runtimes.py` (620 LOC) | LEGACY plural `/runtimes` for ConnectionsPage; provider list_models, primary-mind selection, test endpoint | WRAP | "Keep API for UI compat, route internals to `runtime_truth_registry`" |
| `backend/app/api/v1/settings.py` (459 LOC) | Developer-mode toggle, OAuth credentials override store, public settings overview | KEEP | normal |
| `backend/app/api/v1/founder.py` (358 LOC) | Founder-only: routing diagnostics, RoutingPolicy CRUD, telemetry preview | KEEP | normal |
| `backend/app/api/v1/dynamic_models.py` (117 LOC) | Hot-add/remove provider with API key at runtime: provision/remove/refresh/list_provisionable | KEEP | normal |
| `backend/app/api/v1/security_authorized_scope.py` (240 LOC) | Founder-gated scope CRUD for YELLOW-tier hacking tools | KEEP | "Out of scope for connections rebuild" |
| `backend/app/api/v1/integrations.py` (191 LOC) | Provider tool execution dispatcher: `provider.tool_name` -> `IntegrationRouter` | KEEP | normal |

### services/

| path | purpose | KEEP/ARCHIVE/REWRITE/WRAP | reason |
|------|---------|---------------------------|--------|
| `backend/app/services/connection_service.py` (622 LOC) | CMP service -- connector catalog, instances, per-tool permissions; vault encrypt/decrypt | KEEP | normal |
| `backend/app/services/mcp_invoker.py` (199 LOC) | Spawns stdio MCP server, MCP handshake | KEEP | "Fail-safe stdio session manager" |
| `backend/app/services/mcp_registry.py` (592 LOC) | Tenant-scoped MCP tool runtime cache; hydrate_from_db on startup | KEEP | "Tenant-scoped, DB-backed, hydrate-on-startup -- matches CLAUDE.md ADR-001" |
| `backend/app/services/model_registry.py` (561 LOC) | Singleton catalog of all 9 LLM providers; lazy provider init via `_PROVIDER_MAP` | KEEP | normal |
| `backend/app/services/model_router.py` (1464 LOC) | Picks best model+fallback chain | KEEP (split) | "Too big; needs split into routing strategies" |
| `backend/app/services/runtime_truth_registry.py` (565 LOC) | NEW persistent JSON-backed registry under `var/`; probes runtimes/providers/MCP/local-models | KEEP (PROMOTE) | "Newer source-of-truth"; "canonical source-of-truth" |
| `backend/app/services/mcp_bootstrap.py` (208 LOC) | Reads `claude_desktop_config.json` + instantiates `MCPBridgeAdapter` per stdio entry | WRAP | "Fold into `services/mcp_sync/`. Overlap with `detector.py`" |
| `backend/app/services/dynamic_model_service.py` (325 LOC) | Provision/remove/refresh providers at runtime; CONNECTOR_PROVIDER_MAP | WRAP | "Stop importing private `_PROVIDER_MAP`. Expose public API on `ModelRegistry`" |

### services/runtimes/, services/providers/, services/integrations/

| path | purpose | KEEP/ARCHIVE/REWRITE/WRAP | reason |
|------|---------|---------------------------|--------|
| `backend/app/services/mcp/server.py` (443 LOC) | Daena-as-MCP-server (JSON-RPC handler exposing governance/memory/skills/audit) | KEEP | normal |
| `backend/app/services/mcp_sync/detector.py` (191 LOC) | Reads `~/.claude/mcp.json`, `~/.codex/...`, `~/.gemini/...` -> DetectedMCP rows | KEEP (EXTEND) | "Add VSCode / Cursor / Cline / Continue / Zed candidate paths; add macOS/Linux Claude Code paths; add `mcp-registry` remote source" |
| `backend/app/services/integrations/oauth_service.py` (495 LOC) | `ConnectorOAuthService` -- provider configs + auth_url + token exchange + refresh | KEEP | normal |
| `backend/app/services/integrations/integration_router.py` (319 LOC) | `provider.tool` -> permission check -> vault decrypt -> client.execute() | KEEP | normal |
| `backend/app/services/integrations/oauth_credentials_store.py` (145 LOC) | JSON store at `backend/.daena_oauth_overrides.json` | REWRITE | "Self-documented debt; multi-tenant unsafe" -- migrate to AES vault |
| `backend/app/services/integrations/gmail_client.py` (293 LOC) | Gmail API client | KEEP | normal |
| `backend/app/services/integrations/calendar_client.py` (250 LOC) | Google Calendar client | KEEP | normal |
| `backend/app/services/integrations/notion_client.py` (319 LOC) | Notion API client | KEEP | normal |
| `backend/app/services/runtimes/registry.py` (508 LOC) | `RuntimeRegistry` singleton -- register/discover/health/select | KEEP | normal |
| `backend/app/services/runtimes/base_adapter.py` (185 LOC) | Abstract base -- install/health/capability/execute/cancel/subscription | KEEP | normal |
| `backend/app/services/runtimes/health_tracker.py` (286 LOC) | Per-provider circuit breaker | KEEP | normal |
| `backend/app/services/runtimes/recovery_monitor.py` (172 LOC) | Background half-open circuit reopener | KEEP | normal |
| `backend/app/services/runtimes/capability_matrix.py` (101 LOC) | Static capability scoring per task type | KEEP | normal |
| `backend/app/services/runtimes/cost_estimator.py` (150 LOC) | Pre-execution cost per runtime | KEEP | normal |
| `backend/app/services/runtimes/session_manager.py` (169 LOC) | Persistent session map for stateful CLIs | KEEP | normal |
| `backend/app/services/runtimes/subscription_auth.py` (91 LOC) | AuthMethod/SubscriptionStatus enums + dataclass | KEEP | normal |
| `backend/app/services/runtimes/adapters/claude_code.py` (358 LOC) | claude CLI adapter | KEEP | normal |
| `backend/app/services/runtimes/adapters/claude_session.py` (574 LOC) | Persistent --resume Claude sessions + per-tenant MCP allowlist | KEEP | normal |
| `backend/app/services/runtimes/adapters/codex.py` (253 LOC) | `codex exec` adapter | KEEP | normal |
| `backend/app/services/runtimes/adapters/gemini_cli.py` (306 LOC) | Gemini CLI adapter | KEEP | normal |
| `backend/app/services/runtimes/adapters/grok_cli.py` (167 LOC) | Grok CLI adapter | KEEP | normal |
| `backend/app/services/runtimes/adapters/ollama_adapter.py` (157 LOC) | Ollama via HTTP API (no CLI) | KEEP | normal |
| `backend/app/services/runtimes/adapters/vllm_adapter.py` (183 LOC) | vLLM runtime (OpenAI-compat HTTP) | KEEP | normal |
| `backend/app/services/runtimes/adapters/mcp_bridge.py` (214 LOC) | Generic MCP server adapter (stdio or HTTP) | KEEP | normal |
| `backend/app/services/providers/base.py` (190 LOC) | `BaseProvider` abstract | KEEP | normal |
| `backend/app/services/providers/anthropic.py` (252 LOC) | Anthropic Messages API; primary = Sonnet 4.7 Max | KEEP | normal |
| `backend/app/services/providers/claude_cli.py` (513 LOC) | claude/codex/gemini CLI as subscription provider | KEEP | normal |
| `backend/app/services/providers/openai.py` (202 LOC) | OpenAI | KEEP | normal |
| `backend/app/services/providers/gemini.py` (214 LOC) | Google Gemini | KEEP | normal |
| `backend/app/services/providers/groq.py` (239 LOC) | Groq | KEEP | normal |
| `backend/app/services/providers/ollama.py` (618 LOC) | Ollama with WSL-aware base URL resolution | KEEP | normal |
| `backend/app/services/providers/openrouter.py` (166 LOC) | OpenRouter aggregator | KEEP | normal |
| `backend/app/services/providers/perplexity.py` (210 LOC) | Perplexity | KEEP | normal |
| `backend/app/services/providers/together.py` (194 LOC) | Together.ai | KEEP | normal |
| `backend/app/services/providers/vllm.py` (369 LOC) | vLLM (OpenAI-compat) -- also services llama-server | KEEP | normal |
| `backend/app/services/providers/llama_server_manager.py` (460 LOC) | llama-server lifecycle: PID, mutex, cooldown, GGUF swap | KEEP | normal |
| `backend/app/services/providers/gguf_catalog.py` (149 LOC) | Static GGUF catalog under `MODELS_ROOT\gguf\` | KEEP | normal |

### models/, schemas/

| path | purpose | KEEP/ARCHIVE/REWRITE/WRAP | reason |
|------|---------|---------------------------|--------|
| `backend/app/models/connections.py` (101 LOC) | `Connector`, `ConnectorInstance`, `ConnectorPermission` -- vault-encrypted creds | KEEP | normal |
| `backend/app/models/mcp_server.py` (180 LOC) | `McpServer` -- tenant-scoped MCP persistence; STATUS_DISCOVERED/ACTIVE/FAILED/DISABLED | KEEP | normal |
| `backend/app/models/organization.py` (180 LOC) | `Department`, `Agent`, `SubCapability` (10x6 sunflower-honeycomb) | KEEP | "Out of scope but referenced" |
| `backend/app/models/skill.py` (135 LOC) | `RefinedSkill` -- Skill Refinery store | KEEP | "Out of scope" |
| `backend/app/schemas/connections.py` (118 LOC) | Pydantic schemas: CreateConnector / Connect / InstallConnector / SetPermission | KEEP | normal |

### config/

| path | purpose | KEEP/ARCHIVE/REWRITE/WRAP | reason |
|------|---------|---------------------------|--------|
| `backend/app/config/connector_catalog.json` (3352 LOC) | Master connector catalog -- version `2026-04-29.3`; seeded by `_seed_connector_catalog` on startup | KEEP (split) | "Split per-category for editability"; "V2 source -- add per-tool MCP wiring, `npm_package`, `auto_install_command` fields" |
| `backend/app/config/dcps.json` (630 LOC) | 55 Domain Context Packs for Quintessence | KEEP | "Out of scope" |
| `backend/app/config/founder_accounts.py` (95 LOC) | Founder seed defaults | KEEP | "Out of scope" |
| `backend/app/config/pii_blocklist.yaml` (95 LOC) | PII guard regex list | KEEP | "Out of scope" |

## Frontend files (by directory)

### pages/

| path | purpose | KEEP/ARCHIVE/REWRITE/WRAP | reason |
|------|---------|---------------------------|--------|
| `frontend/src/pages/ConnectionsPage.tsx` | Tab shell (Main Brain / Plugins / MCP) | KEEP | "Active, honest, wired" |
| `frontend/src/pages/SettingsPage.tsx` | 13 lazy settings tabs incl. Models & Runtimes | KEEP | "Active" |
| `frontend/src/pages/MindsPage.tsx` | 10-card gallery of department soul personas | KEEP | "Active" -- naming footgun (souls != runtimes) |
| `frontend/src/pages/MindDetailPage.tsx` | Single soul detail + refine + proposal review/diff | KEEP | "Active" |

### pages/connections/ (the unfinished rebuild subdir)

| path | purpose | KEEP/ARCHIVE/REWRITE/WRAP | reason |
|------|---------|---------------------------|--------|
| `frontend/src/pages/connections/MainBrainPanel.tsx` | New Main Brain tab -- pick CLI runtime or API provider as primary | KEEP | "All wired; honest" |
| `frontend/src/pages/connections/McpServersPanel.tsx` | MCP detected/registry/catalog/extensions panel | KEEP | "All wired" -- but P0 lying badges (string-prefix Callable, name-only Installed) need fixing |
| `frontend/src/pages/connections/PluginsCatalogBrowser.tsx` | Codex-style connector catalog grid | KEEP | "All wired"; reads from `useConnectorCatalog` |
| `frontend/src/pages/connections/ConnectionsConnectors.tsx` (33 KB) | Legacy "plugins" tab w/ ConnectorRow + advanced per-tool perms | ARCHIVE | "NOT mounted by current ConnectionsPage shell"; imports hardcoded `CONNECTORS` from `catalog.ts` (~110 entries) |
| `frontend/src/pages/connections/ConnectionsExtensions.tsx` (26 KB) | Legacy extensions tab w/ per-tool optimistic perms | ARCHIVE | "NOT mounted (replaced by McpServersPanel)" |
| `frontend/src/pages/connections/ConnectionsRuntimes.tsx` (31 KB) | Legacy "Mind Control" runtimes tab + CLIBridgeCard | ARCHIVE | "NOT mounted (replaced by MainBrainPanel)" -- "kept only if CLI Bridge moves to MainBrainPanel" |
| `frontend/src/pages/connections/BrowseModal.tsx` | Legacy marketplace overlay for connectors+extensions | ARCHIVE | "NOT mounted"; reads `BROWSE_CONNECTORS_CATALOG` hardcoded |
| `frontend/src/pages/connections/catalog.ts` (880 LOC) | Hardcoded `CONNECTORS`, `BROWSE_*_CATALOG`, `CLOUD_PREINSTALLED_EXTENSIONS`, `SKILL_DESCRIPTIONS`, `CONNECTOR_MCP_EQUIVALENT` | ARCHIVE (mostly) | "Entire file is hardcoded data; backend `/connections/catalog` already supersedes most"; KEEP only `CONNECTOR_MCP_EQUIVALENT` (move to small file) |
| `frontend/src/pages/connections/installFlow.ts` (208 LOC) | OAuth/api-token install state machine | KEEP | "Imported by `ConnectorInstallDialog`" |
| `frontend/src/pages/connections/oauth.ts` | `startOAuthConnect` helper (legacy) | ARCHIVE | "Imported by archived components" |
| `frontend/src/pages/connections/shared.tsx` | `ConfigPanel`, `ContextMenu`, `PermissionSelect` (legacy) | ARCHIVE | "Imported by archived components" |
| `frontend/src/pages/connections/types.ts` | `ConnectorDef`, `Permission`, `ExtensionData`, `RuntimeData`, `TabKey` | KEEP (split) | "Imported broadly"; "split -- RuntimeData/ExtensionData still live" |

### pages/settings/

| path | purpose | KEEP/ARCHIVE/REWRITE/WRAP | reason |
|------|---------|---------------------------|--------|
| `frontend/src/pages/settings/SettingsModelsRuntimes.tsx` | Local Ollama panel + API-key forms + read-only routing notice | REWRITE | "PROVIDERS enum is stale (4 vs backend's 9); 'Auto Routing' section is a placeholder banner; consider folding live runtime UI into MainBrainPanel" |

### components/connections/

| path | purpose | KEEP/ARCHIVE/REWRITE/WRAP | reason |
|------|---------|---------------------------|--------|
| `frontend/src/components/connections/ConnectorInstallDialog.tsx` | Codex-style install card; one dialog, 4 auth flows | KEEP | "Imported by `PluginsCatalogBrowser` & legacy `ConnectionsConnectors`" |

### components/chat/ (RuntimeSwapper)

| path | purpose | KEEP/ARCHIVE/REWRITE/WRAP | reason |
|------|---------|---------------------------|--------|
| `frontend/src/components/chat/RuntimeSwapper.tsx` | Chat header dropdown to pick primary runtime | KEEP | "Mounted in chat header"; "rewrite 2026-04-29 deleted DEFAULT_RUNTIMES; shows 'Detecting runtimes...' skeleton when empty" |

### hooks/

| path | purpose | KEEP/ARCHIVE/REWRITE/WRAP | reason |
|------|---------|---------------------------|--------|
| `frontend/src/hooks/useConnectorCatalog.ts` | Fetches `/connections/catalog`; 5-min module cache; surfaces `error` | KEEP | "Honest; never falls back to hardcoded list" |
| `frontend/src/hooks/useRuntimeRegistry.ts` | Polls `/runtimes` every 30s; adapts to `RuntimeInfo` | KEEP | "Honest; `normalizeStatus` defaults unknown -> offline" |

### lib/api.ts + mutations.ts (connection sections only)

| path | purpose | KEEP/ARCHIVE/REWRITE/WRAP | reason |
|------|---------|---------------------------|--------|
| `frontend/src/lib/api.ts` | Axios instance; SILENT_PREFIXES contains `/runtimes/`, `/connections/`, `/mcp/`, `/mcp-sync/`, `/dynamic-models/` | KEEP | "ErrorStore/console.warn always run" |
| `frontend/src/lib/mutations.ts` | Generic `deleteWithToast` / `batchDeleteWithToast` | KEEP | "No connection/MCP-specific paths" |

## daena-mcp package (D:\Ideas\Daena\packages\daena-mcp\)

| path | purpose | KEEP/ARCHIVE/REWRITE/WRAP | reason |
|------|---------|---------------------------|--------|
| `packages/daena-mcp/src/index.ts` | STDIO + Bridge mode entrypoint | KEEP | "Solid stdio scaffolding; extend bridge dispatch in Phase 2" |
| `packages/daena-mcp/src/daena-client.ts` | Thin undici HTTP wrapper for Daena envelope | KEEP | "Clean envelope handling, error taxonomy" |
| `packages/daena-mcp/src/tools/status.ts` | `daena_status` -> `GET /health/detailed` | KEEP | "Production-quality" |
| `packages/daena-mcp/src/tools/chat.ts` | `daena_chat` -> `POST /api/v1/chat/messages` (non-streaming) | KEEP | "Production-quality"; streaming is future work |
| `packages/daena-mcp/src/tools/memory.ts` | `daena_recall_memory` -> `GET /api/v1/memory?q=...&tiers=...` | KEEP | "Production-quality" |
| `packages/daena-mcp/src/tools/governance.ts` | `daena_governance_check` -> `POST /api/v1/governance/evaluate` | KEEP | "Production-quality" |
| `packages/daena-mcp/src/tools/audit.ts` | `daena_audit_query` (TODO scaffold) | REWRITE | "Finish list trimming + aggregate; add anomaly surfacing" |
| `packages/daena-mcp/src/tools/index.ts` | Tool registry | KEEP | normal |
| `packages/daena-mcp/package.json` | npm package descriptor (v0.1.0) | REWRITE | "Bump to 0.2.0, publish to npmjs.org, add `vitest`, add `prepublishOnly: tsc`" |
| `packages/daena-mcp/README.md` | User-facing docs | KEEP | "Update post-publish; clear for the README it ships" |

## Discovery scripts (D:\Ideas\Daena\backend\scripts\, D:\Ideas\Daena\scripts\)

| path | purpose | KEEP/ARCHIVE/REWRITE/WRAP | reason |
|------|---------|---------------------------|--------|
| `D:/Ideas/Daena/scripts/scrape_codex_plugins.py` | Scrape `~/.codex/plugins/cache` -> enrich `connector_catalog.json` + mirror SKILL.md | KEEP | "Re-runnable bootstrap of the V2 catalog. Run it as part of release pipeline" |
| `D:/Ideas/Daena/backend/scripts/verify_primary_mind_picker.py` | Runtime test: ModelRouter route() across Primary Mind values + Council modes | KEEP | "Promote to test; fold into pytest as a smoke test of `ModelRouter`" |
| `D:/Ideas/Daena/backend/scripts/council_perplexity.py` | One-shot stdin -> Perplexity (3-way council third opinion) | KEEP | "Single-file utility; useful, isolated, no rewrite needed" |

## API router wire-up status

All routers in scope ARE mounted in `backend/app/api/v1/__init__.py`:

| Router | Prefix | Status |
|--------|--------|--------|
| `connections.router` | `/connections` | OK |
| `connector_oauth.router` | (root, paths self-prefixed `/connectors/...`) | OK |
| `connector_install.router` | (root, prefixed in module `/connectors`) | OK |
| `mcp_server.router` | `/mcp` | OK |
| `mcp_sync.router` | `/mcp-sync` | OK |
| `runtime.router` | `/runtime` | OK -- NEW singular |
| `runtimes.router` | `/runtimes` | OK -- LEGACY plural (WRAP candidate) |
| `settings.router` | `/settings` | OK |
| `founder.router` | `/founder` | OK |
| `dynamic_models.router` | `/dynamic-models` | OK |
| `security_authorized_scope.router` | (root, self-prefixed `/security/authorized-scope`) | OK |
| `integrations.router` | `/integrations` | OK |

**Lifespan hydration chain:** `_seed_founder_accounts` -> `_seed_departments_for_all_tenants` -> `_seed_connector_catalog` -> `_demo_seed` -> `_company_context` -> `_warmup_ollama` (fire-and-forget) -> `runtime_registry_init` -> `init_mcp_registry` -> `init_background_queue` -> `start_cron_scheduler` -> `dream_engine` -> `tlm_init` -> `evilbob_init`

**Periodic loop:** `_periodic_runtime_rescan` every 60s.
**Singleton accessors:** `get_runtime_registry()` in `core.events`, `runtime_truth_registry` module-level, `app.state.model_registry`.

## Recommendations summary

| Action | Count | Files (top 5 examples) |
|--------|-------|------------------------|
| KEEP | 70+ | All providers (13), all adapters (8), models, schemas, hooks, services not flagged |
| ARCHIVE | 7 | `pages/connections/ConnectionsConnectors.tsx`, `ConnectionsExtensions.tsx`, `ConnectionsRuntimes.tsx`, `BrowseModal.tsx`, `catalog.ts` (mostly), `oauth.ts`, `shared.tsx` |
| REWRITE | 3 | `services/integrations/oauth_credentials_store.py` (-> AES vault), `pages/settings/SettingsModelsRuntimes.tsx` (stale providers; merge w/ MainBrainPanel), `packages/daena-mcp/src/tools/audit.ts` + `package.json` (publish to npm) |
| WRAP | 3 | `api/v1/runtimes.py` (UI shim -> `runtime_truth_registry`), `services/mcp_bootstrap.py` (fold into `mcp_sync/`), `services/dynamic_model_service.py` (stop importing private `_PROVIDER_MAP`) |
| SPLIT (KEEP but break apart) | 4 | `api/v1/connections.py` (1150 LOC), `services/model_router.py` (1464 LOC), `config/connector_catalog.json` (3352 lines), `connector_install.py` + `connector_oauth.py` (extract OAuth state to Redis) |
| PROMOTE | 1 | `services/runtime_truth_registry.py` + `api/v1/runtime.py` -> canonical source-of-truth |
| EXTEND | 1 | `services/mcp_sync/detector.py` -- add VSCode/Cursor/Cline/Continue/Zed/macOS/Linux paths + remote `mcp-registry` source |

## Critical findings carried forward from explore reports

V2 architecture must address these architectural issues:

- **Single source of truth per row** -- one backend-owned materialized view; no "JSON says X, DB says Y, FE cache says Z." Two parallel registries (`RuntimeRegistry` + `RuntimeTruthRegistry`) and two MCP discovery paths (`mcp_bootstrap` + `mcp_sync/detector`) must be unified.
- **Six truth dimensions are explicit fields, not one badge** -- detected / configured / imported / persisted / reachable / callable / authenticated. Each a boolean with `last_checked_at` + `last_failure_reason`. UI badges must map to one specific dimension.
- **`auth_type=none` NEVER defaults to `api_token`** -- skill packs render as `Skill pack` / `Not installable` (catalog has `auth.method=none` rows that are skill-only).
- **No `check_health` returning ONLINE on binary presence** -- five CLI adapters (claude_code / codex / gemini_cli / grok_cli / mcp_bridge) need real round-trip health checks.
- **No "ran but did nothing" jobs** -- cron + import endpoints must persist a run record with side-effect evidence (CLAUDE.md Rule 17 / ADR-001).
- **No hardcoded fallback lists posing as live state** -- `DEFAULT_RUNTIMES` pattern banned. Show "Detecting..." / "Empty" only.
- **No async handlers doing sync FS/network probes** -- use `asyncio.to_thread` + TTL caches + stale-while-refresh.
- **No destructive endpoints without `confirm=` gate** -- `install-all` requires explicit confirm; dry-run default.
- **No two parallel UI surfaces for the same concern** -- legacy `ConnectionsPage.tsx` monolith must be removed; only `pages/connections/*` modular tree survives.
- **No raw exceptions in UI** -- TaskGroup/handshake errors sanitized to `Not callable: <reason>`.
- **No "Imported"/"Persisted" UI without callable proof** -- persistence = authenticated round-trip recorded in DB.
- **No backend-local assumptions** -- `localhost:11434` != Windows host (auto-detect WSL bridge).
- **Install dialog state clears on every open**.
- **`configured_untested` not `failed`** when only env key exists.
- **Header chips match semantics** (no `AGI ACTIVE` for `AUTOPILOT ON`).
- **OAuth state in Redis, not in-memory dicts** -- `_MCP_OAUTH_STATES` and `_oauth_states` both ephemeral.
- **OAuth client creds in AES vault, not JSON file** -- consolidate from three storage locations to one.
- **`MCPTool` deduplication** -- two definitions with different shapes need a single source.
- **`daena-mcp` package published to npmjs.org** -- unblocks one-line Claude Desktop install UX.
- **Discovery extends to VSCode/Cursor/Cline/Continue/Zed and macOS/Linux paths** -- current detector is Windows-only.
- **Per-tenant detector** -- `Path.home()` breaks multi-tenant Cloud Run discovery.
