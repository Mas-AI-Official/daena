# PR-CONNECTIONS-SIMPLE-PLUGIN-UX Report

**Date:** 2026-05-02
**Branch:** `rebuild-connections-mcp-runtime`
**Author:** Claude Code (Opus 4.7) under founder direction
**Builds on:**
* `PR_CONN_V2_SEED_IMPORT_REPORT.md` -- discovery + V2 row materialization
* `PR_CONN_UX_RESCUE_REPORT.md` -- prior 7-tab UX cleanup
* `CONNECTIONS_MARKETPLACE_RESEARCH.md` -- catalog sourcing notes
* (Mid-PR pivot) -- the 9-tab marketplace direction was reverted to a
  Codex-style 3-tab "Brain / Plugins / Advanced" surface.

> **Thesis.** The Connections page should look like a real plugin
> marketplace, not a registry-internals dashboard. Hide V1/V2/MCP/OAuth/
> skill-pack plumbing behind ONE concept: "Plugins." Keep an Advanced
> tab for operators who need the registry view. Brain remains its own
> tab because picking the primary runtime is a distinct decision the
> operator makes once. Everything else collapses into a Codex-style
> grid where each card carries an honest lifecycle pill driven by the
> V2 truth ladder underneath.

---

## 0. Hard rules honored

| Rule | Status |
|---|---|
| 1. No production deploy | Yes |
| 2. No `USE_CONNECTION_REGISTRY_V2=true` flip | Yes (`config.py:257` unchanged at `False`) |
| 3. No `vault --apply` | Yes |
| 4. No file deletions | Yes -- legacy V1 panels remain in `connections/` and surface in Advanced -> Legacy V1 panels |
| 5. No secrets printed or committed | Yes -- catalog ships only env var NAMES; sentinel-secret unit test pins the contract |
| 6. No external scans | Yes |
| 7. No external messages | Yes |
| 8. No automatic install of random packages | Yes -- every install path surfaces as "Setup guide" because the backend has no safe install endpoint yet (founder rule explicitly permits `Install` only when backend can safely write config) |
| 9. No callable claim without probe | Yes -- "Connected" status comes from the V2 truth ladder via `pluginCard.deriveStatus` |
| 10. No V1/V2 terminology in normal UI | Yes -- Brain / Plugins / Advanced tab labels are kind-agnostic; per-kind language only appears in Advanced |
| 12. No em-dashes (project Rule 12) | Yes -- per-file `git diff` em-dash count = 0 across all 14 modified/new files |

---

## 1. What changed in the user-facing UX

### 1.1 Tabs collapsed (9 -> 3)

| Old tab | New home |
|---|---|
| Overview | Removed from primary; lives in Advanced -> Registry overview |
| Main Brain | -> Brain (renamed) |
| Runtimes | -> Plugins (filter: CLI runtimes / AI providers) + Advanced -> Runtimes (V2) |
| MCP Store | -> Plugins (filter: MCP categories) + Advanced -> MCP servers (V2) |
| Apps | -> Plugins (filter: OAuth-backed apps) + Advanced -> OAuth apps (V2) |
| Browser / Computer Use | -> Plugins (filter: Browser / Computer Use) + Advanced -> Browser tools (V2) |
| Skill Packs | -> Plugins (with "Skill pack. Needs a runtime/tool to execute." caption) + Advanced -> Skill packs (V2) |
| Local Models | -> Plugins (filter: Local LLM) + Advanced -> Local models (V2) |
| Advanced | -> Advanced (kept; expanded with sectioned sidebar) |

### 1.2 New 3-tab layout

| Tab | Content | Audience |
|---|---|---|
| **Brain** | `MainBrainPanel` -- choose primary runtime / provider; non-callable rows disabled with reason; Experimental Override audit-logged | Founder + operators picking the primary mind |
| **Plugins** | `PluginsPanel` -- one Codex-style marketplace grid combining MCP / OAuth / browser / computer-use / CLI / API / local-model / skill-pack into one PluginCard view-model. Status filter chips + category sidebar + search | Default for everyone |
| **Advanced** | Sectioned sidebar (Registry overview / Runtimes (V2) / MCP servers (V2) / OAuth apps (V2) / Browser tools (V2) / Local models (V2) / Skill packs (V2) / Legacy V1 panels / Discovery + endpoints) | Operators + devs only |

### 1.3 Top-level toolbar

* **Discover installed tools** -- POST `/api/v1/connections/v2/discovery/refresh`. Toast carries per-source created counts (`mcp_servers: +12 · cli_runtimes: +1`) plus the "No installed MCP configs found (searched 9 paths)" hint when MCP discovery returned 0 with `>0` paths searched.
* **Show advanced** checkbox -- gates the Advanced tab visibility. Persists to `localStorage`. Auto-flips ON if the operator deep-links into the Advanced tab so they're never trapped.
* **Last discovery: <timestamp>** -- shown next to the tab row when a discovery has run this session (or persisted `localStorage`).

---

## 2. The PluginCard view-model

`frontend/src/pages/connections/pluginCard.ts` (NEW, 333 lines).

Pure adapter that normalizes one `MarketplaceCard` (catalog entry +
V2 truth overlay) into a single `PluginCard` shape with founder-spec
status + action vocabulary:

```typescript
interface PluginCard {
  id: string
  name: string
  vendor: string
  icon: string                 // single-letter glyph
  category: CatalogCategory
  category_label: string
  description: string
  included_skills: string[]    // capabilities exposed by this plugin
  backing_types: BackingType[] // mcp | oauth | api | local_model | skill_pack | cli | browser | computer_use
  status: PluginStatus         // available | installed | needs_auth | connected | failed | not_supported_on_os
  status_label: string
  primary_action: PluginAction // install | configure | connect | test | open | setup_guide
  primary_action_label: string
  action_enabled: boolean
  failure_reason: string | null
  last_checked: string | null
  is_skill_pack: boolean
  is_skill_pack_caption: string | null
  required_env_vars: string[]
  setup_notes: string
  // Pass-through metadata
  install_method: ...
  auth_type: ...
  risk_level: ...
  official_url: string
  compatible_os: string[]
  v2_row_id: string | null
  source: MarketplaceCard
}
```

### 2.1 Status derivation -- internal kinds collapsed to 6 user-visible states

| Internal state (V2 truth + catalog) | User-facing status |
|---|---|
| `compatible_os` excludes current OS | `not_supported_on_os` |
| Skill pack (catalog kind OR V2 lifecycle) | `connected` (with caption) |
| V2 row exists, recent failure | `failed` |
| V2 row exists, callable=True | `connected` |
| V2 row exists, reachable=True | `needs_auth` |
| V2 row exists, configured=True (auth=none) | `installed` |
| V2 row exists, configured=True (auth required) | `needs_auth` |
| V2 row exists, imported=True | `installed` |
| V2 row exists, disabled / archived | `installed` (re-enable available) |
| No V2 row | `available` |

### 2.2 Action derivation -- founder safety rules

```
not_supported_on_os         -> Setup guide
skill_pack                  -> Open
connected                   -> Test
failed                      -> Test (or Setup guide if no V2 row)
needs_auth (oauth)          -> Connect
needs_auth (api_key/token)  -> Configure
needs_auth (none)           -> Test
installed (oauth)           -> Connect
installed (api_key/token)   -> Configure
installed (none)            -> Test
available + coming-soon     -> Setup guide
available + oauth           -> Setup guide (operator pastes OAuth client creds first)
available (any other)       -> Setup guide  [today the backend has NO safe install path]
```

The `Install` verb is reserved for a future PR that adds a safe
backend install endpoint. Per founder rule 8: "If backend cannot
install yet, button must say 'Setup guide,' not fake Install."

### 2.3 Backing type tags (for the Advanced view + PluginCard tooltip)

`mcp | oauth | api | local_model | skill_pack | cli | browser | computer_use`

Each PluginCard surfaces its backing type as a tooltip on the icon.
The user never sees these in normal mode unless they hover.

---

## 3. Backend support (Phase I)

### 3.1 Curated catalog (51 entries, 14 categories)

`backend/app/services/connection_v2/marketplace_catalog.py` (NEW, ~750 lines).

Hand-curated, source-tree-versioned. Every entry carries:
* `id`, `display_name`, `vendor`, `category`, `kind`
* `short_description`, `capabilities` (tuple)
* `install_method` (`npm` / `docker` / `local` / `manual` / `subscription` / `built-in` / `coming-soon`)
* `command_template` (e.g. `npx -y @modelcontextprotocol/server-github`)
* `required_env_vars` (NAMES ONLY, never values)
* `auth_type` (`none` / `oauth` / `api_key` / `token` / `subscription`)
* `official_url` (vendor docs link)
* `risk_level` (`low` / `medium` / `high`)
* `probe_type` (`mcp_initialize` / `oauth_token` / `http_get` / `binary_check` / `skill_pack_only` / `none`)
* `compatible_os` (tuple of `windows` / `wsl` / `mac` / `linux` / `docker`)
* `matches_v2_slug` (slug pattern that maps to a V2 row)
* `setup_notes` (short Setup-Guide blurb)

Catalog distribution by category:
* CLI runtimes: 3 (Claude Code, Codex, Gemini CLI)
* AI providers: 7 (Anthropic, OpenAI, Gemini, Perplexity, Groq, OpenRouter, Together)
* Local LLM: 2 (Ollama, vLLM/llama-server)
* Browser tools: 3 (Playwright, Chrome DevTools, Browserbase coming-soon)
* Computer Use: 2 (Desktop Commander, Windows MCP)
* Filesystem: 1 (filesystem MCP)
* Code platforms: 5 (GitHub, Cloudflare, Sentry, Vercel, Netlify)
* Communication: 1 (Slack MCP)
* Productivity: 3 (Notion, Linear, Google Drive)
* Design: 1 (Figma)
* Data + Storage: 4 (Postgres, SQLite, MongoDB coming-soon, Redis coming-soon)
* Payment: 2 (Stripe, Shopify coming-soon)
* Research: 1 (Perplexity Search coming-soon)
* Dev tools: 5 (Fetch, Brave Search, Time, Git, Memory)
* OAuth Apps: 11 (Gmail, GCal, GDrive, GitHub, Figma, Slack, Canva, Notion coming-soon, Stripe Connect coming-soon, Cloudflare coming-soon, Sentry coming-soon)

### 3.2 Marketplace overlay service

`backend/app/services/connection_v2/marketplace_service.py` (NEW, ~280 lines).

`MarketplaceService.list_cards(tenant_id)` walks every catalog entry,
finds the matching V2 row by slug (when present), and emits a
`MarketplaceCard` with derived `lifecycle` + `primary_action`.

Honesty contract:
* If `entry.matches_v2_slug` is empty OR no row matches, `lifecycle` is
  `available` (`needs_setup` for `coming-soon` entries). Card has
  `v2_row_id=None` and surfaces `Setup guide`.
* When a row matches, `lifecycle` reflects the truth ladder. Recent
  failures (any dim with `failure_at >= at`) collapse to `failed`.
* Skill pack rows always collapse to `lifecycle="skill_pack"`.
* `v2_truth` is the full 6-dim snapshot (rendered as ISO timestamps).
* `v2_failure_reason` picks the most-actionable reason across the
  ladder (callable -> authenticated -> reachable -> configured).

### 3.3 New API endpoints (Phase I)

Mounted under `/api/v1/connections/v2/`:

| Method | Path | Purpose |
|---|---|---|
| GET | `/catalog` | Static catalog: entries + category metadata |
| GET | `/marketplace/cards` | Per-tenant overlay: catalog + V2 truth |
| GET | `/marketplace/install-plan/{entry_id}` | Setup-Guide steps for one entry (NEVER auto-executed) |

Auth: any logged-in user (the catalog is identical for every tenant;
overlays are tenant-scoped).

Endpoints `/test`, `/enable`, and `/install` are deliberately NOT
added. Probe / enable / disable already exist on the V2 router and
Daena does NOT yet have a safe automatic install endpoint -- the
front end always falls back to `Setup guide` for any "Available"
plugin.

---

## 4. Files changed summary

### Backend (new, 3 files)

| File | Status | Lines |
|---|---|---|
| `backend/app/services/connection_v2/marketplace_catalog.py` | A | +745 (NEW) |
| `backend/app/services/connection_v2/marketplace_service.py` | A | +290 (NEW) |
| `backend/tests/test_connection_v2_marketplace.py` | A | +445 (NEW, 39 tests) |

### Backend (modified, 1 file)

| File | Status | Lines |
|---|---|---|
| `backend/app/api/v1/connections_v2.py` | M | +85 / -4 (3 new GET endpoints + imports) |

### Frontend (new, 8 files)

| File | Status | Lines |
|---|---|---|
| `frontend/src/hooks/useMarketplace.ts` | A | +320 (NEW) |
| `frontend/src/pages/connections/pluginCard.ts` | A | +335 (NEW) |
| `frontend/src/pages/connections/PluginCardView.tsx` | A | +395 (NEW) |
| `frontend/src/pages/connections/PluginsPanel.tsx` | A | +290 (NEW) |
| `frontend/src/pages/connections/MarketplaceCard.tsx` | A | +330 (NEW; used by per-kind Advanced panels) |
| `frontend/src/pages/connections/OverviewPanel.tsx` | A | +320 (NEW; rendered in Advanced -> Registry overview) |
| `frontend/src/pages/connections/McpStorePanel.tsx` | A | +205 (NEW; rendered in Advanced -> MCP servers) |
| `frontend/src/pages/connections/AppsStorePanel.tsx` | A | +160 (NEW; rendered in Advanced -> OAuth apps) |
| `frontend/src/pages/connections/BrowserComputerUsePanel.tsx` | A | +210 (NEW; rendered in Advanced -> Browser tools) |

### Frontend (modified, 3 files)

| File | Status | Lines |
|---|---|---|
| `frontend/src/pages/ConnectionsPage.tsx` | M | rewrite -- 3 tabs (Brain / Plugins / Advanced) |
| `frontend/src/pages/connections/RuntimesPanel.tsx` | M | rewrite -- now PluginCard-based; rendered in Advanced |
| `frontend/src/pages/connections/LocalModelsPanel.tsx` | M | rewrite -- now PluginCard-based; rendered in Advanced |

### Docs (new, 2 files)

| File | Status | Lines |
|---|---|---|
| `docs/Ultraview/CONNECTIONS_MARKETPLACE_RESEARCH.md` | A | +210 (NEW) |
| `docs/Ultraview/PR_CONNECTIONS_SIMPLE_PLUGIN_UX_REPORT.md` | A | this report |

No protected files (`vault_adapter.py`, `vault_migration.py`,
`oauth_credentials_store.py` per project Rule 18) were touched. No V1
files deleted (per founder rule 4).

---

## 5. Tests

### 5.1 Backend (39 new + 142 V2 regression)

`tests/test_connection_v2_marketplace.py` -- 39 tests across 6 classes:

| Class | Tests | Coverage |
|---|---|---|
| `TestCatalogShape` | 6 | Catalog non-empty, every entry has required fields, ids unique, lookup works, JSON serializable, categories complete |
| `TestCatalogCoverage` | 5 + 14 parametrized | Every founder-listed category present; CLI + API + browser kinds first-class; computer_use risk=high; OAuth catalog mirrors `oauth_service.OAUTH_PROVIDERS` |
| `TestNoSecretLeak` | 2 | Sentinel-secret audit (`sk-`, `sk-ant-`, `pplx-`, `gsk_`, `AIza`, `ghp_`, `ya29.`, AWS keys, Daena sentinels); `required_env_vars` are NAMES not values (no `=`, no spaces) |
| `TestInstallPlans` | 5 | Every entry has a plan; coming-soon plans link out; npm plans include command; OAuth plans include auth step; lookup returns None for unknown id |
| `TestMarketplaceServiceOverlay` | 5 | No V2 row -> available; callable=True -> lifecycle=callable; recent failure -> lifecycle=failed; disabled -> lifecycle=disabled; skill_pack always lifecycle=skill_pack |
| `TestListHelpers` | 2 | `list_catalog()` + `list_categories()` return JSON-friendly dicts |

```text
$ pytest tests/test_connection_v2_marketplace.py
  39/39 PASS in 0.40s

Combined V2 regression (8 files, 142 tests):
  tests/test_connection_v2.py                       22/22 PASS
  tests/test_connection_v2_probe_truth.py            8/8  PASS
  tests/test_connection_v2_reconciliation.py        12/12 PASS
  tests/test_connection_v2_seed_import.py           16/16 PASS
  tests/test_connection_v2_ux_rescue.py             14/14 PASS
  tests/test_connection_v2_marketplace.py           39/39 PASS  (NEW)
  tests/test_phase7_lifespan_seed.py                 3/3  PASS
  tests/test_phase7_provider_probes.py              28/28 PASS
  ----------------------------------------------------------
  combined                                         142/142 PASS in 2.00s
```

### 5.2 Frontend (tsc clean)

```text
$ cd frontend && npx tsc --noEmit
EXIT=0
```

The PluginCard view-model adapter (`pluginCard.ts`) is intentionally
test-friendly (pure functions over plain inputs); a future PR can add
Vitest coverage. Today the adapter is exercised end-to-end through
`PluginsPanel` rendering against the `useMarketplaceCards` hook, which
hits the live `/marketplace/cards` endpoint.

### 5.3 Em-dash hygiene (project Rule 12)

Per-file `git diff` em-dash count across all 14 modified/new files: **0**.

### 5.4 No-secret-leak guarantees

Three layers of protection:
1. **Catalog source code:** the catalog dataclass `to_dict()` walks
   only `id`, `display_name`, `vendor`, `category`, `kind`,
   `short_description`, `capabilities`, `install_method`,
   `command_template`, `required_env_vars` (NAMES), `auth_type`,
   `official_url`, `risk_level`, `probe_type`, `compatible_os`,
   `matches_v2_slug`, `setup_notes`. There is NO field where a value
   could land.
2. **Sentinel-secret unit test:** `TestNoSecretLeak.test_no_obvious_secret_in_catalog`
   scans every catalog entry text-content for known secret prefixes.
3. **Required env names test:** `test_required_env_vars_are_names_not_values`
   asserts each entry's env vars are uppercase identifiers (no `=`,
   no spaces), so a future contributor cannot paste an assignment.

The same protection extends through the marketplace service (no
secret-bearing fields in `MarketplaceCard`), the API responses (the
`/catalog`, `/marketplace/cards`, and `/install-plan/{id}` endpoints
emit only the catalog dict + truth snapshots), and the frontend
adapter (`pluginCard.ts` only reads catalog metadata + V2 truth).

---

## 6. What actions actually work today vs Setup-guide-only

### 6.1 Working actions

| Action | Backend support | Notes |
|---|---|---|
| **Discover installed tools** | `POST /v2/discovery/refresh` | Walks CLI MCP configs + binaries + local models + providers + OAuth catalog + V1 plugins; idempotent on slug |
| **Test (probe)** | `POST /v2/{id}/probe` | For local_model + provider kinds the existing `ProviderProbe` runs `/v1/models` or `/api/tags`. For other kinds the probe returns `probe_unavailable` until the per-kind probe lands |
| **Enable** | `POST /v2/{id}/enable` | Toggles `disabled=false` |
| **Open (skill pack)** | -- | Frontend opens the Setup-guide drawer with the included skills + caption |
| **Setup guide** | `GET /v2/marketplace/install-plan/{id}` | Returns the metadata-only plan (steps with `kind=command|env|auth|link|info|note`); operator copy-pastes |
| **Set Main Brain** | `PUT /runtimes/primary` | Persists to `User.settings.primary_runtime`; gated on V2 callable=True (with Experimental Override) |

### 6.2 Setup-guide-only actions (today)

| Action | Why deferred | Future PR |
|---|---|---|
| Install MCP server | No safe install endpoint -- backend cannot write to a CLI's `mcpServers` config without race / clobber risk | PR-CONN-MCP-INSTALL |
| Connect OAuth | OAuth flow surface lives in `oauth_service.py` but not yet wired through V2 -- operator still needs to paste client_id + client_secret in Settings | PR-CONN-OAUTH-INSTALL |
| Configure API key | Same reason as OAuth -- key paste UX still lives in Settings -> API Keys | (low priority -- Settings flow works today) |

For all three, today the button says **Setup guide** and opens a
drawer with the steps the operator runs themselves.

---

## 7. How internal V2 kinds map to the Plugin card

The backing types are visible in the PluginCard tooltip, the search
("search by 'oauth' to find OAuth plugins"), and the Advanced view
sidebar. The user never sees them in the default Plugins grid except
as the kind icon letter (M / O / B / C / R / A / L / S).

| V2 kind | Backing type tag | Catalog-side examples |
|---|---|---|
| `mcp_server` | `mcp` | GitHub MCP, Stripe MCP, Filesystem, Notion, ... |
| `oauth_app` | `oauth` | Gmail, GCal, GDrive, GitHub OAuth, Figma OAuth, ... |
| `cli_runtime` | `cli` | Claude Code, Codex CLI, Gemini CLI |
| `provider` (-> `api_provider`) | `api` | OpenAI, Anthropic, Perplexity, Groq, ... |
| `local_model` | `local_model` | Ollama, vLLM/llama-server |
| `browser_tool` (catalog-only) | `browser` | Playwright, Chrome DevTools, Browserbase |
| `computer_use` (catalog-only) | `computer_use` | Desktop Commander, Windows MCP |
| `skill_pack` | `skill_pack` | V1 PLUGIN_CATALOG entries without `mcp_package` |

The catalog kind `browser_tool` and `computer_use` are catalog-only
labels -- when they get installed, the V2 row is `kind=mcp_server`
because they ship as MCP packages. The catalog distinguishes them so
the Plugins grid can render them with the right risk badge + caption.

---

## 8. Discovery experience -- before vs after

### Before this PR

* Empty MCP tab: "0 servers found." (No explanation.)
* Empty Apps tab: "0 apps imported." (No path forward.)
* No catalog visible until Discover ran.

### After this PR

* Empty Plugins grid (no catalog match): "No plugins match the active
  filters. Click Discover installed tools to import what Daena finds
  on disk, or open a card and follow its Setup guide."
* Empty MCP discovery: toast carries "No installed MCP configs found
  (searched 9 paths). Open Advanced for details." Advanced -> Discovery
  + endpoints surfaces the per-path probe payload.
* Catalog ALWAYS visible -- 51 plugin cards rendered immediately on
  Plugins tab even before discovery, with status pills like Available
  / Setup guide so the user can browse what Daena supports without
  configuring anything first.

---

## 9. Remaining blockers before true one-click install

Same backbone blockers as PR-CONN-V2-SEED-IMPORT plus the
install-flow gap:

| # | Blocker | Owner |
|---|---|---|
| B1 | `McpServerProbe` (initialize + tools/list) | PR-CONN-MCP-PROBE |
| B2 | `CliRuntimeProbe` (which + version) | PR-CONN-CLI-PROBE |
| B3 | `OAuthAppProbe` (refresh + userinfo) | PR-CONN-OAUTH-PROBE |
| B4 | OAuth flow wired through V2 (paste client_id + connect) | PR-CONN-OAUTH-INSTALL |
| B5 | Safe MCP install endpoint -- atomic write to a CLI's mcpServers config | PR-CONN-MCP-INSTALL |
| B6 | `BrowserToolProbe` -- spawn the browser MCP, capture exit code, kill | PR-CONN-BROWSER-PROBE |
| B7 | DXT extension catalog import -- read `Claude Extensions/<name>/manifest.json` | PR-CONN-DXT-IMPORT |
| B8 | External catalog mirror (mcpservers.org / smithery.ai) | PR-CONN-CATALOG-EXTERNAL |
| B9 | Per-tenant OS detection (today the OS gate runs in the browser; a future PR can move detection server-side) | PR-CONN-OS-DETECT-SERVER |

None of these block the new UX from being usable. The Plugins page
ships catalog discovery + status overlay TODAY; one-click install lands
in a future PR.

---

## 10. Honesty audit (project Rule 17)

Every UI claim and backend status this PR ships passes the "where
does this persist?" + "how does the user see it fail?" test:

| Surface | Persistence | Failure visibility |
|---|---|---|
| Plugins grid status pill | V2 truth ladder (database) + catalog (source-tree) | Failed pill + inline `failure_reason` row |
| Setup guide drawer | Catalog `setup_notes` + `command_template` + `required_env_vars` (source-tree) | Modal carries an explicit "Daena does not execute install commands automatically" disclaimer |
| Skill pack caption | V2 row `kind=skill_pack` (database) | Caption shown on every skill_pack card; modal also surfaces it |
| Last checked timestamp | `ConnectionV2.callable_at / reachable_at / ...` | Hidden when no probe has ever run |
| Discovery toast summary | `DiscoveryReport.sources` + `mcp_paths_searched` (in-memory after request) | "No installed MCP configs found" hint when MCP source returned 0 with paths searched |
| Brain / Set Main Brain | `User.settings.primary_runtime` (database JSONB) | Toast on rejection (`runtime_not_callable`) + Experimental Override audit log |

Nothing in this PR is a "looks complete but does nothing" surface.

---

## 11. Commit message

```
canonicalization: simplify connections into plugin marketplace
```

Single commit on branch `rebuild-connections-mcp-runtime`.

---

**Stopping here as requested. Awaiting next founder direction.**
