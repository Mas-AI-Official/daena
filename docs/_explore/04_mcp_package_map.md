# MCP Package + Discovery Map

Inventory of `@mas-ai/daena-mcp` (the npm-published MCP server bridging external MCP hosts into a running Daena backend) and every MCP discovery / scrape / sync surface in the Daena repo.

Scope dates: 2026-04-30. Source files inspected: `D:\Ideas\Daena\packages\daena-mcp\` (full tree minus `node_modules/`), `backend/app/api/v1/{mcp_server,mcp_sync,connections}.py`, `backend/app/services/{mcp_invoker,mcp_registry,mcp_bootstrap,mcp_sync/detector,runtime_truth_registry}.py`, `scripts/scrape_codex_plugins.py`, `backend/scripts/{verify_primary_mind_picker,council_perplexity}.py`, `backend/app/config/connector_catalog.json`.

---

## daena-mcp package

| Field | Value |
|---|---|
| Path | `D:\Ideas\Daena\packages\daena-mcp\` |
| Package name | `@mas-ai/daena-mcp` |
| Version | `0.1.0` |
| License | MIT (note: commercial Daena is not OSS - this bridge is intentionally MIT) |
| Repo URL declared | `https://github.com/mas-ai/daena-mcp` |
| Bin | `daena-mcp` -> `./dist/index.js` |
| Build | `tsc` (no compiled `dist/` checked in - must `npm run build` first) |
| Node deps | `@modelcontextprotocol/sdk ^1`, `ws ^8.18`, `commander ^12`, `undici ^6.21` |
| **Published to npmjs.org?** | **No.** README explicitly says `npm install -g @mas-ai/daena-mcp` returns 404. Local install is `npm link` from package dir. |

### Tools exposed (`src/tools/index.ts` registry)

| Tool | File | Status | Daena endpoint hit |
|---|---|---|---|
| `daena_status` | `tools/status.ts` | Complete | `GET /health/detailed` |
| `daena_chat` | `tools/chat.ts` | Complete (non-streaming only - MCP `tools/call` is request/response) | `POST /api/v1/chat/messages` |
| `daena_recall_memory` | `tools/memory.ts` | Complete (T0-T4 tier filter) | `GET /api/v1/memory?q=…&tiers=…` |
| `daena_governance_check` | `tools/governance.ts` | Complete | `POST /api/v1/governance/evaluate` |
| `daena_audit_query` | `tools/audit.ts` | **Scaffold w/ TODO** - list mode returns raw entries verbatim, aggregate mode is stubbed (`notice: 'aggregate mode not yet designed'`) | `GET /api/v1/governance/audit` |

### Two operating modes (`src/index.ts`)

1. **STDIO (default)** - standard MCP server invoked by Claude Desktop / Cursor / Codex CLI as a subprocess; tool calls become HTTP requests against `DAENA_URL` (default `http://localhost:8000`). Uses `DAENA_TOKEN` JWT bearer auth.
2. **Bridge (`--bridge`)** - outbound WebSocket relay to `wss://daena.mas-ai.co/api/v1/ws/bridge`. Daena dispatches work *to* the local machine. **Phase 2 stub** - `tool_call dispatch: future Phase 2.` Handshake + reconnect logic shipped, dispatch not.

### `DaenaClient` (`src/daena-client.ts`)
Thin undici HTTP wrapper. Handles `{success,data,error}` envelope unwrap, 401/timeout/network errors → `DaenaError` with codes (`HTTP_*`, `TIMEOUT`, `NETWORK_ERROR`, `INVALID_JSON`). 30 s default timeout. Stateless - no caching, no pooling.

---

## Backend MCP routes (mounted in `backend/app/api/v1/__init__.py`)

| Route | Method | File | Purpose |
|---|---|---|---|
| `/mcp/tools` | GET | `mcp_server.py` | List tools Daena-as-MCP-server exposes (delegates to `DaenaMCPServer.get_tool_definitions`) |
| `/mcp/call` | POST | `mcp_server.py` | Tool invocation (auto-wraps non-JSON-RPC body into `tools/call`) |
| `/mcp/jsonrpc` | POST | `mcp_server.py` | Raw JSON-RPC endpoint for `tools/list` + `tools/call` |
| `/mcp-sync/detected` | GET | `mcp_sync.py` | Returns deduplicated list of MCPs found in installed CLI configs (Claude Code / Codex / Gemini) |
| `/mcp-sync/import` | POST | `mcp_sync.py` | Runs `InstallScanner.scan_mcp_server` then `MCPRegistry.register_tools` + `persist_addition`. Tier 2 (NOTIFIED) by default. |
| `/connections/extensions/{id}/install` | POST | `connections.py` (line ~678) | Mutates `~/AppData/Roaming/Claude/claude_desktop_config.json` `mcpServers` block (the in-app installer; not exposed by `daena-mcp`) |
| `/connections/extensions/{id}/uninstall` | DELETE | `connections.py` (line ~1111) | Removes from `claude_desktop_config.json` |

`mcp_invoker.py` is *not* a route - it's the runtime that opens stdio sessions to installed MCPs (via `mcp.ClientSession` + `stdio_client`). Used by chat orchestrator + plugin-admin agent. ~100-400 ms per call (spawn-handshake-call-close).

---

## Discovery sources

| Source | File on disk | Where parsed | Status |
|---|---|---|---|
| **Claude Desktop** | `~\AppData\Roaming\Claude\claude_desktop_config.json` | `mcp_bootstrap.py:42` (primary; bootstraps system-tenant adapters at startup) and `mcp_sync/detector.py:80` (one of the Claude Code candidates) | Parsed; mutates back via `connections.py` extension install |
| **Claude Code CLI** | `~\.claude\mcp.json`, `~\.claude.json` (legacy embedded), `~\AppData\Roaming\Claude\claude_desktop_config.json` | `mcp_sync/detector.py:_CANDIDATES["claude_code"]` | Read-only |
| **Codex CLI** | `~\.codex\config.json`, `~\.openai\codex.json`, `~\.config\codex\mcp.json` | `mcp_sync/detector.py:_CANDIDATES["codex"]` | Read-only - picks first candidate that parses |
| **Codex plugin cache (richer)** | `C:\Users\masou\.codex\plugins\cache\<marketplace>\<plugin>\<version>\` | `scripts/scrape_codex_plugins.py` | Standalone re-runnable script - enriches `connector_catalog.json` + mirrors SKILL.md trees |
| **Gemini CLI** | `~\.config\google-gemini\mcp.json`, `~\.gemini\mcp_servers.json`, `~\.gemini\settings.json` | `mcp_sync/detector.py:_CANDIDATES["gemini_cli"]` | Read-only |
| **Daena DB (`mcp_servers` table)** | SQLite/Postgres | `mcp_registry.py:hydrate_from_db` at app startup via `init_mcp_registry` (lifespan, `app/main.py:500`) | Tenant-scoped, soft-delete aware |
| **`daena-mcp` package itself** | `D:\Ideas\Daena\packages\daena-mcp` | `runtime_truth_registry.py:491` only - probes filesystem existence; **never invokes the package** | Probe-only |
| **npm registry** | npmjs.org | NOT parsed anywhere | **Gap** - no remote search/discovery |
| **MCP Registry (anthropic-skills `mcp-registry` MCP)** | Remote | NOT parsed anywhere | **Gap** |
| **Env vars (DAENA_URL/TOKEN)** | `process.env` | `packages/daena-mcp/src/index.ts:47` for the bridge; backend reads via `app.core.config.get_settings` | OK |

The detector handles both `mcpServers` (Claude/Codex modern) and `mcp_servers` (Gemini older) keys, and both `{command,args}` and `{url}` shapes (`detector.py:142`). Dedup key: `(name, command, tuple(args))`. Cross-CLI dupes are collapsed and tagged `detected_in=claude_code,codex,gemini_cli`.

---

## connector_catalog.json schema

Path: `backend/app/config/connector_catalog.json` (version `2026-04-29.3`). Top level: `{ "version": str, "connectors": [...] }`. Sample (Hugging Face - first entry, abridged):

```json
{
  "name": "Hugging Face", "slug": "hugging-face",
  "description": "Inspect models, datasets, Spaces, and research",
  "category": "Coding", "auth_type": "api_key", "icon_url": null,
  "tools": [{"name": "search_models", "description": "..."}, ...],
  "config_schema": {},
  "interface": {
    "displayName": "...", "shortDescription": "...", "longDescription": "...",
    "developerName": "...", "websiteURL": "...",
    "privacyPolicyURL": "...", "termsOfServiceURL": "...",
    "brandColor": "#FFD21E", "defaultPrompts": [...], "capabilities": [...]
  },
  "auth": { "method": "api_token", "token_settings_url": "...",
            "token_help": "...", "validate_endpoint": "..." }
}
```

| Field | Type | Notes |
|---|---|---|
| `name` / `slug` | str | Identity. Slug is stable, not changed on enrichment. |
| `category` | str | "Coding" / "Productivity" / "Sales" / "Design" |
| `auth_type` | str | Legacy: `api_key` / `token` / `oauth` (kept for back-compat, derived from `auth.method`) |
| `tools` | list | Stub catalog of operations - these are NOT live MCP tool definitions, they are display copy |
| `config_schema` | dict | Currently always `{}` - placeholder |
| `interface.*` | dict | Display metadata: copy, brand color, capabilities |
| `auth.method` | str | `api_token` \| `oauth_managed` \| `mcp_remote_oauth` \| `none` |
| `auth.mcp_url` | str | When `mcp_remote_oauth`: SSE URL (e.g. `https://mcp.linear.app/sse`) |
| `mcp_servers` | dict | Optional - Codex's `.mcp.json` block for the connector (only when scraped) |
| `skills` | list | Optional - `[{id, name, description, source}]` pulled from Codex plugin SKILL.md frontmatter |
| `codex_app` | dict | Optional - Codex-proprietary app ID, recorded only |
| `skill_count` | int | Optional |

**V2 catalog viability:** Yes, usable as the spine. The `interface` block is rich enough to render the Connections UI without a separate copy table. Gaps for V2: (a) per-tool MCP wiring (`mcp_servers` is sparse - only present where Codex shipped a `.mcp.json`), (b) `tools` field is human-curated copy, not auto-discovered tool schemas, (c) no field for "is the underlying npm package published" or "where does the auth flow run" - both implicit today.

---

## scripts/

| Script | Path | Purpose | Status |
|---|---|---|---|
| `scrape_codex_plugins.py` | `D:\Ideas\Daena\scripts\` | Scrape `~\.codex\plugins\cache` -> enrich `connector_catalog.json` + mirror SKILL.md into `D:\Ideas\Daena\skills\connector-<slug>\`. Also pre-populates 17 KNOWN_CONNECTORS (Hugging Face, Vercel, Netlify, GitHub, CircleCI, Sentry, Expo, CodeRabbit, Neon, Cloudinary, Render, Linear, Atlassian Rovo, Google Calendar, Gmail, HubSpot, Canva). | Re-runnable; idempotent merge. **Catalog hand-off works.** |
| `verify_primary_mind_picker.py` | `D:\Ideas\Daena\backend\scripts\` | Runtime test: for each Primary Mind value (`None`, `claude_code`, `codex`, `gemini_cli`, `ollama`, `grok_cli`, `perplexity`), call `ModelRouter.route()` in STANDARD + COUNCIL@medium + COUNCIL@high effort modes; verify priority-tagged flagships win and Council judge/debater asymmetry holds. Sanity check: no flagship slot contains `flash`/`mini`/`haiku`/`instant`/`nano`. | Working; not part of test suite, run manually. |
| `council_perplexity.py` | `D:\Ideas\Daena\backend\scripts\` | One-shot: stdin/file -> `PerplexityProvider.generate(model="sonar-pro")` -> stdout. Used as the "third opinion" in 3-way council pattern (Claude / Perplexity / GPT-5.5). | Working. UTF-8 forced on Windows stdout. |

---

## Wire-up status

| Component | Wired? | Where |
|---|---|---|
| `daena-mcp` package npm-published | **No** | README line 147 admits 404 |
| `daena-mcp` package invoked from backend | **No** | Only filesystem-existence probed in `runtime_truth_registry.py:491` |
| `daena-mcp` package documented in Claude Desktop config | Manually (README copy-paste) | `claude_desktop_config.json` example in README |
| `mcp_server.py` routes mounted | Yes | `api/v1/__init__.py:99` `prefix=/mcp` |
| `mcp_sync.py` routes mounted | Yes | `api/v1/__init__.py:100` `prefix=/mcp-sync` |
| `mcp_bootstrap.bootstrap_installed_mcps()` runs at startup | Yes | Called from `init_mcp_registry` (lifespan), see `app/main.py:500` |
| `mcp_registry.hydrate_from_db` runs at startup | Yes | Same lifespan step |
| `mcp_invoker` used in chat | Yes | Imported by orchestrator + plugin-admin |
| `scrape_codex_plugins.py` integrated into pipeline | **No** | Manual `python scripts/scrape_codex_plugins.py` |

---

## Gaps

1. **Not on npm.** `daena-mcp` is `0.1.0` and unpublished. Until published, every install is `npm link` or absolute-path. This blocks the "drop one block in `claude_desktop_config.json`" UX the README sells.
2. **`daena_audit_query` is a TODO.** Aggregate mode returns a sample + notice; list mode returns raw entries (blows MCP tool-result size with `limit=200`).
3. **No streaming chat.** `daena_chat` calls non-streaming endpoint; the README acknowledges progress-token streaming as future.
4. **No bridge dispatch.** `--bridge` mode connects + handshakes + heartbeats but tool dispatch is `future Phase 2`.
5. **No npm-registry / mcp-registry remote search.** Detector only reads local CLI configs. Cannot "browse all available MCPs and click install" - only sync what user already installed elsewhere. Anthropic now ships an `mcp-registry` MCP (`mcp__mcp-registry__list_connectors`) that is not consumed.
6. **No per-tenant detector.** `mcp_sync/detector.py` reads `Path.home()` - a multi-tenant deploy on Cloud Run cannot run discovery for individual users; it sees the container's home dir.
7. **No write-back to CLI configs.** Sync is one-way (CLI -> Daena). If operator installs via Daena, that doesn't propagate to Claude Code or Codex.
8. **No credential sync.** By design - README and detector docstring both call this out - but it means each install must be re-authorized inside Daena.
9. **VSCode / Cursor / Continue / Cline / Zed** - not in `_CANDIDATES`. All host MCPs.
10. **Anthropic's `~/.config/claude/claude.json`** (Claude Code's newer location on Linux/macOS) - not in candidate list; only Windows AppData path is.
11. **`packages/daena-mcp/dist/`** is gitignored (no compiled artifact in tree). Consumers must build before `npm link`.
12. **No tests.** Package has no test runner / fixtures / vitest config.
13. **`tools` field in `connector_catalog.json` is hand-curated copy**, not auto-discovered. Drift risk vs. live MCP tool list.

---

## Recommendations

| File | Verdict | Reason |
|---|---|---|
| `packages/daena-mcp/src/index.ts` | **KEEP** | Solid stdio scaffolding; extend bridge dispatch in Phase 2 |
| `packages/daena-mcp/src/daena-client.ts` | **KEEP** | Clean envelope handling, error taxonomy |
| `packages/daena-mcp/src/tools/{status,chat,memory,governance}.ts` | **KEEP** | Production-quality |
| `packages/daena-mcp/src/tools/audit.ts` | **REWRITE** | Finish list trimming + aggregate; add anomaly surfacing |
| `packages/daena-mcp/package.json` | **REWRITE** | Bump to 0.2.0, publish to npmjs.org, add `vitest`, add `prepublishOnly: tsc` |
| `packages/daena-mcp/README.md` | **KEEP** (update post-publish) | Clear for the README it ships |
| `backend/app/api/v1/mcp_sync.py` | **KEEP** | Clean route layer; no dependencies on dead code |
| `backend/app/api/v1/mcp_server.py` | **KEEP** | Thin and correct |
| `backend/app/services/mcp_invoker.py` | **KEEP** | Fail-safe stdio session manager |
| `backend/app/services/mcp_registry.py` | **KEEP** | Tenant-scoped, DB-backed, hydrate-on-startup - matches CLAUDE.md ADR-001 |
| `backend/app/services/mcp_bootstrap.py` | **KEEP** | Read-only `claude_desktop_config.json` -> adapter cache; idempotent |
| `backend/app/services/mcp_sync/detector.py` | **EXTEND** (don't rewrite) | Add VSCode / Cursor / Cline / Continue / Zed candidate paths; add macOS/Linux Claude Code paths; add `mcp-registry` remote source as a separate `discover_remote()` method |
| `scripts/scrape_codex_plugins.py` | **KEEP** | Re-runnable bootstrap of the V2 catalog. Run it as part of release pipeline. |
| `backend/scripts/verify_primary_mind_picker.py` | **KEEP** | Promote to test; fold into pytest as a smoke test of `ModelRouter` |
| `backend/scripts/council_perplexity.py` | **KEEP** (single-file utility) | Useful, isolated, no rewrite needed |
| `backend/app/config/connector_catalog.json` | **KEEP as V2 source** | Add: per-tool MCP wiring, `npm_package`, `auto_install_command` fields |
| `backend/app/services/runtime_truth_registry.py` (line 491 daena-mcp probe) | **KEEP, EXTEND** | Once `daena-mcp` is on npm, switch from filesystem probe to `npm view` probe + version freshness check |
