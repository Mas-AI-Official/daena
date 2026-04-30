# Backend File Map

Scope: connections / MCP / runtime / model registry / brain switching.
Inspected against `D:\Ideas\Daena\backend\app\main.py` (lifespan + create_app)
and `D:\Ideas\Daena\backend\app\api\v1\__init__.py` (router aggregator).
Lines counts via `wc -l`. "Wired" = listed in `__init__.py` v1 router.

## API Layer (api/v1/*.py)

| Path | Purpose | Used? | Wired? | Stub patterns | Imports of note | Recommendation |
|---|---|---|---|---|---|---|
| `api/v1/connections.py` (1150 LOC) | CMP catalog + per-tool permissions, plugin catalog overlay, install/connect/disconnect | Yes | Yes (`/connections`) | 2 hits ("hardcoded" comments referencing legacy CONNECTORS array; no live stubs) | `ConnectionService`, `plugin_catalog`, `Connector` model | KEEP - split into router + service helpers (file is too big) |
| `api/v1/connector_install.py` (848 LOC) | Unified install dialog: oauth_managed / mcp_remote_oauth / api_token; PKCE; HTML callback | Yes | Yes (mounted root) | 1 ("fake installs" guard comment); large in-memory `_MCP_OAUTH_STATES` dict (not Redis) | `httpx`, `vault.encrypt_dict`, `Connector*` models | KEEP - refactor MCP-OAuth state into Redis/DB (ADR-001 honesty rule) |
| `api/v1/connector_oauth.py` (313 LOC) | Multi-provider OAuth (Google/GitHub/Figma/Slack/Canva) authorize → callback → refresh | Yes | Yes (mounted root) | In-memory `_oauth_states` dict ("production: use Redis or DB") | `ConnectorOAuthService`, `OAuthConfigError` | KEEP - replace `_oauth_states` with Redis (sibling of connector_install) |
| `api/v1/mcp_server.py` (71 LOC) | Daena-as-MCP-server JSON-RPC: list_tools / call / jsonrpc | Yes | Yes (`/mcp`) | None | `DaenaMCPServer` | KEEP - thin pass-through, fine as-is |
| `api/v1/mcp_sync.py` (235 LOC) | Detect MCPs in Claude/Codex/Gemini CLI configs + one-click import via install_scanner | Yes | Yes (`/mcp-sync`) | 2 (config-shape edge cases) | `CLIMCPDetector`, `InstallScanner`, `MCPRegistry` | KEEP |
| `api/v1/runtime.py` (116 LOC) | NEW singular `/runtime` API → `RuntimeTruthRegistry` (truth/refresh/import/health-check/test-call/patch) | Yes | Yes (`/runtime`) | None | `runtime_truth_registry` singleton | KEEP - newer/cleaner than `runtimes.py` |
| `api/v1/runtimes.py` (620 LOC) | LEGACY plural `/runtimes` for ConnectionsPage; provider list_models with parallel gather, 30s tenant cache, primary-mind selection, test endpoint | Yes | Yes (`/runtimes`) | 3 `return []` (legitimate: failure path returns empty list) | `model_registry`, `runtime_registry`, `subscription_auth` | WRAP - keep API for UI compat, route internals to `runtime_truth_registry` |
| `api/v1/settings.py` (459 LOC) | Developer-mode toggle, OAuth credentials override store, public settings overview | Yes | Yes (`/settings`) | 1 (TODO marker) | `oauth_credentials_store`, `Settings` config | KEEP |
| `api/v1/founder.py` (358 LOC) | Founder-only: routing diagnostics, RoutingPolicy CRUD, telemetry preview, model_registry deps | Yes | Yes (`/founder`) | None | `ModelRouter`, `RoutingPolicy`, `AuditService` | KEEP |
| `api/v1/dynamic_models.py` (117 LOC) | Hot-add/remove provider with API key at runtime: provision/remove/refresh/list_provisionable | Yes | Yes (`/dynamic-models`) | None | `DynamicModelService` | KEEP |
| `api/v1/security_authorized_scope.py` (240 LOC) | Founder-gated scope CRUD for YELLOW-tier hacking tools (auth scope JSON) | Yes | Yes (mounted root, paths self-prefixed) | 4 (defaults: empty lists in pydantic body) | `yellow_runtime_gate`, internal `_SCOPES_JSON_PATH` | KEEP - out of scope for connections rebuild |
| `api/v1/integrations.py` (191 LOC) | Provider tool execution dispatcher: `provider.tool_name` → `IntegrationRouter` | Yes | Yes (`/integrations`) | None | `IntegrationRouter`, `gmail/calendar/notion` clients | KEEP |

## Service Layer (services/*.py)

| Path | Purpose | Used? | Wired? | Stub patterns | Imports of note | Recommendation |
|---|---|---|---|---|---|---|
| `services/connection_service.py` (622 LOC) | CMP service - connector catalog, instances, per-tool permissions; vault encrypt/decrypt creds | Yes | Yes (via `connections.py` API + `IntegrationRouter`) | None | `vault.encrypt_dict/decrypt_dict`, `Connector*` models | KEEP |
| `services/mcp_invoker.py` (199 LOC) | Spawns stdio MCP server, MCP handshake via `mcp.ClientSession`, list_server_tools/call_server_tool | Yes | Indirect (through `mcp_bootstrap` registry) | None | `mcp.ClientSession`, `mcp.client.stdio.StdioServerParameters` | KEEP |
| `services/mcp_registry.py` (592 LOC) | Tenant-scoped MCP tool runtime cache backed by `McpServer` model; hydrate_from_db on startup | Yes | Yes (via `init_mcp_registry` in lifespan) | None | `McpServer` model, `httpx` for HTTP MCPs | KEEP |
| `services/model_registry.py` (561 LOC) | Singleton catalog of all 9 LLM providers; lazy provider init via `_PROVIDER_MAP` | Yes | Yes (`app.state.model_registry` set in lifespan) | None | All 9 provider modules, `ModelInfo` | KEEP |
| `services/model_router.py` (1464 LOC) | Picks best model+fallback chain: scoring, healthy filter, runtime-vs-LLM split for EXE | Yes | Yes (consumed by `chat_orchestrator`, `founder` API) | 3 (TODO/FIXME) | `query_understanding`, `health_tracker`, runtime registry | KEEP - too big; needs split into routing strategies |
| `services/runtime_truth_registry.py` (565 LOC) | NEW persistent JSON-backed registry under `var/`; probes runtimes/providers/MCP/local-models; import/health/test events | Yes | Yes (via `/runtime` API) | None | `httpx`, `mcp_sync.detector.CLIMCPDetector` | KEEP - newer source-of-truth |
| `services/mcp/server.py` (443 LOC) | Daena-as-MCP-server (JSON-RPC handler exposing governance/memory/skills/audit) | Yes | Yes (via `mcp_server.py` API) | None | dataclasses for tool defs | KEEP |
| `services/mcp_sync/detector.py` (191 LOC) | Reads `~/.claude/mcp.json`, `~/.codex/...`, `~/.gemini/...` and merges → DetectedMCP rows | Yes | Yes (via `mcp_sync.py` API + `runtime_truth_registry`) | None | json, pathlib | KEEP |
| `services/mcp_bootstrap.py` (208 LOC) | Reads `claude_desktop_config.json` + instantiates `MCPBridgeAdapter` per stdio entry | Yes | Yes (called by `mcp_registry.init`) | None | `MCPBridgeAdapter` | KEEP - but overlaps `mcp_sync/detector.py` (different scope: bootstrap vs UI surface) |
| `services/dynamic_model_service.py` (325 LOC) | Provision/remove/refresh providers at runtime; CONNECTOR_PROVIDER_MAP | Yes | Yes (via `dynamic_models.py` API) | 1 (1 generic TODO) | `ModelRegistry` internals (`_PROVIDER_MAP`, `_PROVIDER_DISPLAY_NAMES`) | KEEP |
| `services/integrations/oauth_service.py` (495 LOC) | `ConnectorOAuthService` - provider configs + auth_url + token exchange + refresh; uses `oauth_credentials_store` | Yes | Yes (via `connector_oauth.py`) | None | httpx, `oauth_credentials_store` | KEEP |
| `services/integrations/integration_router.py` (319 LOC) | `provider.tool` → permission check → vault decrypt → client.execute() | Yes | Yes (via `integrations.py` API) | None | `gmail/calendar/notion` clients, `vault.decrypt_dict`, `Connector*` | KEEP |
| `services/integrations/oauth_credentials_store.py` (145 LOC) | JSON store for runtime OAuth client_id/secret overrides at `backend/.daena_oauth_overrides.json` | Yes | Yes (via `oauth_service`, `settings` API) | None | json, asyncio.Lock | WRAP - must migrate to AES vault for prod (per CLAUDE.md note in file) |
| `services/integrations/gmail_client.py` (293 LOC) | Gmail API client | Yes | Yes (via integration_router) | - | google-api | KEEP |
| `services/integrations/calendar_client.py` (250 LOC) | Google Calendar client | Yes | Yes | - | google-api | KEEP |
| `services/integrations/notion_client.py` (319 LOC) | Notion API client | Yes | Yes | - | httpx | KEEP |
| `services/runtimes/registry.py` (508 LOC) | `RuntimeRegistry` singleton - register/discover/health/select; concurrent health | Yes | Yes (`get_runtime_registry()`) | 7 defensive `return []` | base_adapter | KEEP |
| `services/runtimes/base_adapter.py` (185 LOC) | Abstract base - install/health/capability/execute/cancel/subscription | Yes | Yes (parent of all) | None | abc, dataclasses | KEEP |
| `services/runtimes/health_tracker.py` (286 LOC) | Per-provider circuit breaker (HEALTHY→DEGRADED→OPEN→HALF→...) | Yes | Yes (via model_router) | None | in-memory only | KEEP |
| `services/runtimes/recovery_monitor.py` (172 LOC) | Background half-open circuit reopener | Yes | Yes (via model_router) | None | asyncio | KEEP |
| `services/runtimes/capability_matrix.py` (101 LOC) | Static capability scoring per task type | Yes | Yes | None | dataclasses | KEEP |
| `services/runtimes/cost_estimator.py` (150 LOC) | Pre-execution cost per runtime | Yes | Yes | None | - | KEEP |
| `services/runtimes/session_manager.py` (169 LOC) | Persistent session map for stateful CLIs | Yes | Yes (claude_session) | None | dataclasses | KEEP |
| `services/runtimes/subscription_auth.py` (91 LOC) | AuthMethod/SubscriptionStatus enums + SubscriptionAuth dataclass | Yes | Yes | None | enum | KEEP |
| `services/runtimes/adapters/claude_code.py` (358 LOC) | claude CLI (`-p` json) adapter | Yes | Yes | None | subprocess | KEEP |
| `services/runtimes/adapters/claude_session.py` (574 LOC) | Persistent --resume Claude sessions + per-tenant MCP allowlist | Yes | Yes | 3 TODOs | subprocess | KEEP |
| `services/runtimes/adapters/codex.py` (253 LOC) | `codex exec` adapter | Yes | Yes | None | subprocess | KEEP |
| `services/runtimes/adapters/gemini_cli.py` (306 LOC) | Gemini CLI adapter | Yes | Yes | None | subprocess | KEEP |
| `services/runtimes/adapters/grok_cli.py` (167 LOC) | Grok CLI adapter | Yes | Yes | None | subprocess | KEEP |
| `services/runtimes/adapters/ollama_adapter.py` (157 LOC) | Ollama via HTTP API (no CLI) | Yes | Yes | None | httpx | KEEP |
| `services/runtimes/adapters/vllm_adapter.py` (183 LOC) | vLLM runtime (OpenAI-compat HTTP) | Yes | Yes | None | httpx | KEEP |
| `services/runtimes/adapters/mcp_bridge.py` (214 LOC) | Generic MCP server adapter (stdio or HTTP) | Yes | Yes | None | mcp.ClientSession | KEEP |
| `services/providers/base.py` (190 LOC) | `BaseProvider` abstract - generate/stream/health/list_models | Yes | Yes (parent) | 1 default | abc | KEEP |
| `services/providers/anthropic.py` (252 LOC) | Anthropic Messages API; primary = Sonnet 4.7 Max | Yes | Yes | 1 default | httpx, orjson | KEEP |
| `services/providers/claude_cli.py` (513 LOC) | claude/codex/gemini CLI as subscription provider | Yes | Yes (when no API key) | None | subprocess | KEEP |
| `services/providers/openai.py` (202 LOC) | OpenAI | Yes | Yes | None | httpx | KEEP |
| `services/providers/gemini.py` (214 LOC) | Google Gemini | Yes | Yes | None | httpx | KEEP |
| `services/providers/groq.py` (239 LOC) | Groq | Yes | Yes | None | httpx | KEEP |
| `services/providers/ollama.py` (618 LOC) | Ollama with WSL-aware base URL resolution | Yes | Yes | None | httpx | KEEP |
| `services/providers/openrouter.py` (166 LOC) | OpenRouter aggregator | Yes | Yes | None | httpx | KEEP |
| `services/providers/perplexity.py` (210 LOC) | Perplexity | Yes | Yes | None | httpx | KEEP |
| `services/providers/together.py` (194 LOC) | Together.ai | Yes | Yes | None | httpx | KEEP |
| `services/providers/vllm.py` (369 LOC) | vLLM (OpenAI-compat) - also services llama-server | Yes | Yes | None | httpx | KEEP |
| `services/providers/llama_server_manager.py` (460 LOC) | llama-server lifecycle: PID, mutex, cooldown, GGUF swap, respect_external | Yes | Yes | 1 defensive | subprocess | KEEP |
| `services/providers/gguf_catalog.py` (149 LOC) | Static GGUF catalog under `MODELS_ROOT\gguf\`; BACKGROUND PATH ONLY | Yes | Yes | 1 marker | dataclasses | KEEP |

## Data Layer (models/*.py, schemas/*.py)

| Path | Purpose | Used? | Wired? | Stub patterns | Imports of note | Recommendation |
|---|---|---|---|---|---|---|
| `models/connections.py` (101 LOC) | `Connector`, `ConnectorInstance`, `ConnectorPermission` (CMP) - vault-encrypted creds, per-tool permission_level | Yes | Yes | None | `TenantMixin`, `JSONBCompat` | KEEP |
| `models/mcp_server.py` (180 LOC) | `McpServer` - tenant-scoped MCP persistence; STATUS_DISCOVERED/ACTIVE/FAILED/DISABLED | Yes | Yes (`hydrate_from_db`) | None | `TenantMixin`, `JSONBCompat`, `extra_metadata` | KEEP |
| `models/organization.py` (180 LOC) | `Department`, `Agent`, `SubCapability` (10×6 sunflower-honeycomb) | Yes | Yes | None | `TenantMixin` | KEEP - out of scope but referenced |
| `models/skill.py` (135 LOC) | `RefinedSkill` - Skill Refinery store with maturity tiers T0-T4 | Yes | Yes (Skill Refinery) | None | `TenantMixin`, `SmallInteger` for tier | KEEP - out of scope |
| `schemas/connections.py` (118 LOC) | Pydantic schemas: CreateConnector / Connect / InstallConnector / SetPermission / responses | Yes | Yes | None | pydantic, `DaenaSchema` | KEEP |

## Config Layer

| Path | Purpose | Used? | Wired? | Stub patterns | Imports of note | Recommendation |
|---|---|---|---|---|---|---|
| `config/connector_catalog.json` (3352 LOC) | Master connector catalog - version `2026-04-29.3`; seeded by `_seed_connector_catalog` on startup | Yes | Yes (lifespan deferred step #3) | None (data file) | n/a | KEEP - split per-category for editability |
| `config/dcps.json` (630 LOC) | 55 Domain Context Packs for Quintessence | Yes | Yes (loaded via `dcp_loader.py`) | None | n/a | KEEP - out of scope |
| `config/founder_accounts.py` (95 LOC) | Founder seed defaults | Yes | Yes (lifespan) | None | - | KEEP - out of scope |
| `config/pii_blocklist.yaml` (95 LOC) | PII guard regex list | Yes | Yes | None | - | KEEP - out of scope |

## Wire-up Status

All routers in scope are mounted in `app/api/v1/__init__.py`:

| Router | Prefix | Notes |
|---|---|---|
| `connections.router` | `/connections` | OK |
| `connector_oauth.router` | (root, paths self-prefixed `/connectors/...`) | OK |
| `connector_install.router` | (root, prefixed in module `/connectors`) | OK |
| `mcp_server.router` | `/mcp` | OK |
| `mcp_sync.router` | `/mcp-sync` | OK |
| `runtime.router` | `/runtime` | NEW singular |
| `runtimes.router` | `/runtimes` | LEGACY plural |
| `settings.router` | `/settings` | OK |
| `founder.router` | `/founder` | OK |
| `dynamic_models.router` | `/dynamic-models` | OK |
| `security_authorized_scope.router` | (root, self-prefixed `/security/authorized-scope`) | OK |
| `integrations.router` | `/integrations` | OK |

Lifespan hydration chain (deferred step order):
1. `_seed_founder_accounts` 2. `_seed_departments_for_all_tenants`
3. `_seed_connector_catalog` 4. `_demo_seed`
5. `_company_context` 6. `_warmup_ollama` (fire-and-forget)
7. `runtime_registry_init` 8. `init_mcp_registry`
9. `init_background_queue` 10. `start_cron_scheduler`
11. `dream_engine` 12. `tlm_init` 13. `evilbob_init`

Periodic loop: `_periodic_runtime_rescan` every 60s.
Singleton accessors: `get_runtime_registry()` in `core.events`,
`runtime_truth_registry` module-level, `app.state.model_registry`.

## Cross-File Duplication

Two-source problem on RUNTIMES:
- `services/runtimes/registry.py` (RuntimeRegistry - adapter-driven, in-memory, health cache)
- `services/runtime_truth_registry.py` (RuntimeTruthRegistry - JSON-persisted truth, broader scope: providers + MCP + local models)
Result: API surfaces `runtime.py` (truth) AND `runtimes.py` (registry+models combined).
The two registries don't share data; UI calls both.

Two-source problem on MCP DETECTION:
- `services/mcp_bootstrap.py` reads `claude_desktop_config.json` only.
- `services/mcp_sync/detector.py` reads ALL CLI configs (Claude Code / Codex / Gemini).
Both feed `MCPRegistry` indirectly through different paths; bootstrap fires on lifespan,
detector is on-demand from `/mcp-sync/detected`. Some servers may end up registered twice
under different `server_key`s.

Two-source problem on PROVIDER LISTING:
- `services/model_registry.py` (`_PROVIDER_MAP`)
- `services/dynamic_model_service.py` (`CONNECTOR_PROVIDER_MAP`, `PROVIDER_CONFIG_KEYS`)
Both keep mappings of provider-name to config-key. dynamic_model_service imports the
registry's private dict - a refactor in registry breaks dynamic provisioning silently.

OAuth STATE STORAGE:
- `connector_install.py._MCP_OAUTH_STATES` (in-memory dict)
- `connector_oauth.py._oauth_states` (in-memory dict, comment: "production: use Redis or DB")
Two parallel ephemeral state dicts; both scrap on restart, neither uses Redis though
Redis client is imported in lifespan.

OAUTH CREDENTIALS:
- `services/integrations/oauth_credentials_store.py` (JSON file `.daena_oauth_overrides.json`)
- `core.config.Settings` (env-based)
- `core.vault` (AES-256, exists, used for ConnectorInstance creds but NOT for client_id/secret)
Three places where OAuth client creds live. The store comments
"For production, this should be replaced by the AES-256 secret vault" → debt logged.

MCP TOOL DEFINITION:
- `services/mcp/server.py.MCPTool` (dataclass, for Daena-as-server)
- `services/mcp_registry.MCPTool` (frozen-slots dataclass, for tools we INVOKE)
Same name, different shape. Easy to confuse on import.

Tests missing for: `runtimes.py`, `connector_install.py`, `connector_oauth.py`,
`runtime.py`, `runtime_truth_registry.py`, `dynamic_models.py`, `mcp_invoker.py`,
`mcp_bootstrap.py`, `connection_service.py`, `oauth_service.py`,
`integration_router.py`, `oauth_credentials_store.py`, `security_authorized_scope.py`.
Existing: `test_connections.py`, `test_connector_catalog_api.py`,
`test_connector_catalog_seed.py`, `test_mcp_registry.py`, `test_mcp_server.py`,
`test_mcp_sync_api.py`, `test_mcp_sync_detector.py`, `test_model_registry.py`,
`test_oauth_credentials_store.py`, `test_runtime_adapters.py`, `test_integrations.py`,
`test_dynamic_model_service.py`, `test_founder_*` (3).

## Recommendations Summary

REWRITE (1):
- `services/integrations/oauth_credentials_store.py` → AES vault. Self-documented debt; multi-tenant unsafe.

WRAP (3):
- `api/v1/runtimes.py` → UI shim that delegates to `runtime_truth_registry`. Eliminates two-source drift.
- `services/mcp_bootstrap.py` → fold into `services/mcp_sync/`. Overlap with `detector.py`.
- `services/dynamic_model_service.py` → stop importing private `_PROVIDER_MAP`. Expose public API on `ModelRegistry`.

SPLIT (4 - KEEP but break apart):
- `api/v1/connections.py` (1150 LOC, 6 concerns)
- `services/model_router.py` (1464 LOC, scoring + runtime + fallback strategies mixed)
- `config/connector_catalog.json` (3352 lines per-category)
- `connector_install.py` + `connector_oauth.py` - extract `_MCP_OAUTH_STATES` and `_oauth_states` dicts to Redis.

PROMOTE (1):
- `services/runtime_truth_registry.py` + `api/v1/runtime.py` → canonical source-of-truth.

KEEP as-is (everything else): all providers (13), all adapters (8), models, schemas, services not listed above.

ARCHIVE: none outright. All duplicates are WRAP candidates, not delete candidates.

Add tests for: `runtimes.py`, `runtime.py`, `connector_install.py`, `connector_oauth.py`,
`dynamic_models.py`, `runtime_truth_registry.py`, `mcp_invoker.py`, `mcp_bootstrap.py`,
`connection_service.py`, `oauth_service.py`, `integration_router.py`,
`security_authorized_scope.py`.
