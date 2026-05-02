# PR-CONN-V2-SEED-IMPORT Report

**Date:** 2026-05-02
**Branch:** `rebuild-connections-mcp-runtime`
**Author:** Claude Code (Opus 4.7) under founder direction
**Companion plan:** `docs/Ultraview/DAENA_CANONICALIZATION_PLAN.md`
**Builds on:** `PR_CONNECTIONS_TRUTH_CLEANUP_REPORT.md` (V2 panels are
canonical; legacy lives behind a reveal toggle).

> **Thesis.** The V2 panels became canonical in PR-CONNECTIONS-TRUTH-CLEANUP
> but landed empty in dev because the only seeder (`provider_v2_seed`)
> was gated on `USE_CONNECTION_REGISTRY_V2`. Result: the V2 page felt
> dishonest -- "0 MCP servers, 0 plugins, 0 OAuth apps" while V1 showed
> dozens of cards. This PR fills the gap by walking the SAME real
> sources V1 reads from -- CLI MCP configs (Claude Code / Codex /
> Gemini), CLI runtime binaries, local model endpoints, configured API
> providers, OAuth catalog, V1 plugin catalog -- and materializing
> `ConnectionV2` rows for the caller's tenant on demand. Skill packs
> (capability/instruction bundles, never callable) get their own
> distinct `kind=skill_pack` and a probe that explicitly refuses to
> flip `callable=true`. The flag stays OFF; production gets nothing
> new; dev gets a full V2 surface backed by real sources.

---

## 0. Hard rules honored

| Rule | Status |
|---|---|
| 1. No production deploy | Yes |
| 2. No `USE_CONNECTION_REGISTRY_V2=true` flip in production | Yes (`config.py:257` unchanged at `False`) |
| 3. No `vault --apply` | Yes (vault not invoked) |
| 4. No file deletions | Yes (5 V1 files still present behind reveal toggle; legacy panels untouched) |
| 5. No secrets printed or committed | Yes -- discovery NEVER reads `client_secret`, API key values, or MCP env values; only existence checks + names |
| 6. No external scans | Yes |
| 7. No external messages (email / DM / SMS / webhook) | Yes |
| 8. No T5 / 3vilbob execution touched | Yes (zero edits to security paths) |
| 9. No rewrite of the whole Connections UI | Yes -- 4 surgical files: copy edits + 1 button + 1 type extension. Layout, tabs, drawer structure unchanged |
| 10. No new dependencies | Yes -- pure Python stdlib (`shutil.which`); no new pip / npm packages |
| 11. No claim "connected/callable" without a real probe | Yes -- importer ONLY sets detected/configured/imported; reachable/authenticated/callable still require real probe round-trip |
| 12. No em-dashes in new content (project CLAUDE.md Rule 12) | Yes (per-file `git diff` em-dash count = 0 across all 14 modified files) |

---

## 1. Phase A: source inventory

| # | Source | File / service | Has secrets? | V2 ingests today? | Gap |
|---|---|---|---|---|---|
| 1 | V2 registry rows | `connection_v2` table | yes (vault_v2 envelope) | self | none |
| 2 | V1 PLUGIN_CATALOG (Python dict, ~25 plugins) | `app/services/plugin_catalog.py` | no | NO | not surfaced as skill packs |
| 3 | V1 connector catalog (~110 entries) | `connector_catalog.json` -> `connectors` table | no | NO | not surfaced |
| 4 | MCP servers in claude_desktop_config | `~/AppData/Roaming/Claude/claude_desktop_config.json` | env values may contain secrets | NO (V1 only) | not surfaced |
| 5 | MCP servers in `.claude/mcp.json` | `~/.claude/mcp.json` (+ `~/.claude.json`) | env values may contain secrets | NO | not surfaced |
| 6 | MCP servers in Codex config | `~/.codex/config.json` (+ `~/.openai/codex.json`, `~/.config/codex/mcp.json`) | env values may contain secrets | NO | not surfaced |
| 7 | MCP servers in Gemini CLI config | `~/.config/google-gemini/mcp.json` (+ `~/.gemini/mcp_servers.json`, `~/.gemini/settings.json`) | env values may contain secrets | NO | not surfaced |
| 8 | DXT extensions | `~/AppData/Roaming/Claude/Claude Extensions/<name>/manifest.json` | no | NO | not surfaced (deferred -- detector covers main MCP path) |
| 9 | Persisted MCP servers (V1 install path) | `mcp_servers` table per-tenant | env values may persist | NO | covered transitively via mcp_sync.detector reading config files |
| 10 | API providers | `Settings.{provider}_api_key` (8 cloud + 2 local) | YES | YES (provider_seeder, but flag-gated) | OFF in dev -> empty UI |
| 11 | CLI runtime providers | `app/services/providers/claude_cli.py` ALL_CLI_SPECS (3) | no (subscription auth) | NO | not surfaced |
| 12 | Local model endpoints | `Settings.ollama_base_url` + `Settings.vllm_base_url` | no (URLs only) | partial (only via provider_seeder + flag) | OFF in dev -> empty UI; no Docker/WSL guidance |
| 13 | OAuth app catalog | `app/services/integrations/oauth_service.py` (7 providers) | YES (client_secret in vault) | NO | not surfaced |
| 14 | Skill catalog (DB) | `Skill` table (per-tenant, runtime data) | no | NO | future PR-NBMF-SKILL-V2 |
| 15 | Plugin skills (PLUGIN_CATALOG.skills) | embedded in each plugin's `.skills` list | no | NO | now surfaced as `kind=skill_pack` |

---

## 2. Phase B: V2 seed/import design + implementation

### 2.1 New backend additions

| File | Status | Lines | Purpose |
|---|---|---|---|
| `backend/app/models/connection_v2.py` | M | +10 / -1 | Add `SKILL_PACK = "skill_pack"` enum value with docstring explaining contract |
| `backend/app/schemas/connection_v2.py` | M | +13 / -1 | Add `SkillPackConfig` Pydantic discriminator + extend `ConnectionConfigUnion` |
| `backend/app/services/connection_v2/state_machine.py` | M | +10 / -1 | Add `"skill_pack"` to `LABELS` + special-case branch returning `"skill_pack"` terminal label for imported skill_pack rows |
| `backend/app/services/connection_v2/probes/skill_pack_probe.py` | A | +56 (new) | `SkillPackProbe` always returns `failure_dim="callable", failure_reason="skill_pack: capability/instruction bundle, not a callable surface"`. Pinned constant for frontend / tests. |
| `backend/app/services/connection_v2/probes/__init__.py` | M | +13 / -3 | Wire `install_skill_pack_probe()` into `install_all_probes()` |
| `backend/app/services/connection_v2/seeders.py` | A | +474 (new) | `ConnectionDiscoveryService` -- 6 importers (MCP, CLI runtime, local model, provider, OAuth app, skill pack); `DiscoveryReport` + `SourceReport` aggregates; idempotent on slug |
| `backend/app/services/connection_v2/__init__.py` | M | +6 / 0 | Re-export `ConnectionDiscoveryService` / `DiscoveryReport` / `SourceReport` |
| `backend/app/api/v1/connections_v2.py` | M | +35 / -0 | New `POST /api/v1/connections/v2/discovery/refresh` endpoint (any logged-in user, scoped to caller's tenant) |
| `backend/app/main.py` | M | +14 / -8 | `_provider_v2_seed` lifespan step now ALWAYS installs probes (idempotent in-process registration); only the bulk seeding step stays flag-gated |

### 2.2 Importer contracts

Each importer is idempotent on the `(tenant_id, kind, slug)` unique key
backed by `ConnectionRegistryV2.find_by_slug`. Re-running discovery
adds zero new rows when nothing has changed.

**MCP servers (`_import_mcp_servers`):**
- Calls `CLIMCPDetector.discover_all()` then `deduplicate()` -> walks 9
  candidate config paths (Claude Code / Codex / Gemini CLI variants)
  and merges by `(name, command, args)`.
- Persists `command` + `args` + `url` + `_source_cli` + `_source_path`
  + `_source_notes` + `env_var_names` + `env_var_count`.
- **Never persists env values.** Only the var-name list. The number of
  env vars is shown in the UI ("3 env vars expected") but the values
  themselves never leave the source CLI's config file.
- `auth_method=NONE` because Daena does not own the OAuth flow for
  these MCPs -- the MCP subprocess does that lazily on first call.

**CLI runtimes (`_import_cli_runtimes`):**
- Iterates `ALL_CLI_SPECS` (Claude / Codex / Gemini today).
- Resolves `shutil.which(spec.binary_name)`.
- Skipped if binary not on PATH (`skipped_unconfigured`).
- Created if binary present, with config carrying `binary` path +
  `_runtime_id` + `_provider_enum` + `_model_id`.
- `auth_method=SUBSCRIPTION` (matches `CliRuntimeSpec` semantics).
- Real `CliRuntimeProbe` is still TODO (see B1 in the prior PR's
  blocker list); probes return `probe_unavailable` until that lands.

**Local model endpoints (`_import_local_models`):**
- Two candidates: Ollama (gated on `ollama_enabled=True` AND non-empty
  `ollama_base_url`) and vLLM (gated on non-empty `vllm_base_url`).
- Persists `base_url` + `default_model` (if set). Both are config, not
  secret -- safe to print in the UI.
- `auth_method=NONE`.
- Frontend renders Docker/WSL guidance for `local_model` rows whose
  `reachable` failure is fresh (see Phase D below).

**API providers (`_import_providers`):**
- Delegates to existing `seed_providers_for_tenant`. Re-uses the
  existing 9-provider catalog + idempotent insert logic.
- The discovery wrapper passes through created / skipped_existing /
  skipped_unconfigured tallies into the SourceReport.
- API key VALUES NEVER persist in `config` (the seeder writes only
  `_provider_enum`, `_local`, `_seeded_by` markers).

**OAuth apps (`_import_oauth_apps`):**
- Iterates `OAUTH_PROVIDERS` (gmail, gcal, gdrive, github, figma,
  slack, canva).
- Reads `client_id` ONLY (`getattr(settings, cfg.client_id_setting)`).
- Reads existence-check on `client_secret_setting` to populate a
  `_client_secret_set: bool` flag. **The actual secret value is NEVER
  read or persisted.**
- Skipped if `client_id` is empty.
- `auth_method=OAUTH_MANAGED`.

**Skill packs (`_import_skill_packs`):**
- Walks `PLUGIN_CATALOG`. Filters out plugins that ship an
  `mcp_package` (those will surface via the MCP detector once
  installed; double-counting them as skill packs would mislead).
- One row per remaining plugin with `kind=SKILL_PACK`,
  `auth_method=NONE`, config carrying `source_plugin_id`,
  `skill_count`, `_category`, `_subtitle`, `_skill_ids`.
- These rows render with the violet `"skill pack"` label and a clear
  "Skill pack only -- not a callable connector" badge in the UI.

### 2.3 Truth ladder for the new SKILL_PACK kind

| Dim | After import | After probe | Reason |
|---|---|---|---|
| `detected` | True | unchanged | source plugin exists in catalog |
| `configured` | True | unchanged | no extra config needed |
| `imported` | True | unchanged | row durably persisted in V2 |
| `reachable` | False (unset) | False | skill packs are not network-reachable |
| `authenticated` | False (unset) | False | `auth_method=NONE`; no auth required |
| `callable` | False | False (with explicit failure_reason) | skill packs are categorically not callable |

`derive_label` short-circuits to `"skill_pack"` after the
detected/configured/imported gates -- without the special case, the
ladder would fall through to `"failed"` because reachable=False, which
would mislead the operator.

### 2.4 Discovery endpoint

```
POST /api/v1/connections/v2/discovery/refresh
Auth: any logged-in user (scoped to caller's tenant)
Body: empty
Response: { success, data: DiscoveryReport, v2_enabled }
```

Returns the per-source report:
```json
{
  "tenant_id": "...",
  "sources": [
    { "source": "mcp_servers", "created": ["mcp-figma", ...], ... },
    { "source": "cli_runtimes", "created": ["cli-claude_code"], ... },
    ...
  ],
  "total_created": 12,
  "total_skipped_existing": 3,
  "total_skipped_unconfigured": 4,
  "total_failed": 0
}
```

Founder-only `/reconciliation/seed-providers` is unchanged and remains
the FOUNDER+ alternative for provider-only seeding across all tenants.

---

## 3. Phase C: UI truth cleanup

### 3.1 Frontend changes

| File | Status | Lines | Purpose |
|---|---|---|---|
| `frontend/src/hooks/useConnectionsV2.ts` | M | +57 / -7 | Add `'skill_pack'` to `ConnectionKind` + `ConnectionLabel` unions; add violet `LABEL_TONE` for skill_pack; add `runDiscoveryRefresh()` standalone helper + `DiscoveryReport` / `DiscoverySourceResult` types |
| `frontend/src/pages/connections/ConnectionsV2Panel.tsx` | M | +152 / -10 | "Import from detected sources" button next to Refresh; richer empty-state with `<details>` Advanced section; `ConfigDrawerRows` component renders kind-specific config (base_url for local_model, command/args for mcp_server, client_id + client_secret_set for oauth_app, binary for cli_runtime, skill_count for skill_pack); local_model unreachable amber box with Docker/WSL guidance |
| `frontend/src/pages/connections/McpServersV2Panel.tsx` | M | +52 / -10 | "Import from detected configs" button; richer empty-state with `<details>` Advanced section pointing to discovery endpoint |
| `frontend/src/pages/connections/PluginsV2Panel.tsx` | M | +94 / -16 | Add `'skill_pack'` to `PLUGIN_KINDS` + `KIND_LABELS`; "Import from detected configs" button alongside "Seed providers (FOUNDER+)"; `PluginRow` renders skill_pack rows with violet badge, "not callable" pill, bundled-skills count, and "No probe" affordance instead of Probe button |

### 3.2 Connection-row states (founder rule 5)

The `McpServersV2Panel`, `PluginsV2Panel`, and `ConnectionsV2Panel` row
renderers use the existing 6-dim truth ladder + `failure_reason`
text -- nothing changed in the underlying data model. The Phase C
brief asked for these states to be visible per-row:

| Required state | How it renders |
|---|---|
| Detected | per-dim chip in the truth ladder |
| Imported | per-dim chip in the truth ladder |
| Configured | per-dim chip in the truth ladder |
| Reachable | per-dim chip + amber-box for local_model failures |
| Callable | per-dim chip + label pill (`healthy` / `failed` / `skill_pack`) |
| Last probed | `proven at <timestamp>` in DetailsDrawer truth ladder |
| Failure reason | `<dim> failure: <reason>` line + truth-ladder tooltip |

### 3.3 Skill-pack-only labelling (founder rule 4)

Skill pack rows in `PluginsV2Panel` render with three honest signals:

1. Violet `"skill pack"` status pill (matching the new label tone)
2. Inline `"not callable"` pill with tooltip explaining why
3. Replacement of the Probe button with a "No probe" affordance whose
   tooltip cites the SkillPackProbe contract

Caption: *"Skill pack only. Not a callable connector. The LLM uses the
packaged skills as context; nothing is invoked over the network."*

### 3.4 Developer-only copy moved behind Advanced details

Empty-state text on all three V2 panels now uses an HTML
`<details>` block titled "Advanced details" to hide the
`POST /api/v1/connections/v2` API references from the casual operator
view. The default empty state focuses on the operator action ("click
Import from detected sources") instead.

### 3.5 V2 read-only mode copy

The existing amber `"V2 read-only mode"` banner in `ConnectionsV2Panel`
already explained that legacy mutations don't mirror; PR-CONNECTIONS-
TRUTH-CLEANUP wrote that copy. No changes needed in this PR.

---

## 4. Phase D: vLLM / Ollama / local runtime truth

### 4.1 Where local-runtime truth now surfaces

| Surface | Behavior |
|---|---|
| Discovery import | Creates `kind=local_model` rows for Ollama (when `ollama_enabled=True` AND base URL non-empty) and vLLM (when base URL non-empty). Skipped silently otherwise -- never half-imports. |
| `ConnectionsV2Panel` row | Standard truth ladder. Probe still uses `ProviderProbe` (registered for `kind=local_model` only when the spec's `local=True` -- vLLM and Ollama qualify and use the `{base_url}` template that the existing provider probe already supports). |
| `ConnectionsV2Panel` DetailsDrawer | New `ConfigDrawerRows` component renders `base_url` verbatim (config, not secret) + `default_model` if set. |
| `ConnectionsV2Panel` DetailsDrawer (failed reachable) | New amber box: "Local endpoint unreachable. Configured base URL: <url>. If the backend runs in Docker / WSL, 127.0.0.1 resolves to the container, not the Windows host. Try host.docker.internal or the configured bridge IP, or run the backend natively." |

### 4.2 Honesty contract

- A local_model row reports `callable=true` ONLY after the
  `ProviderProbe` (kind=local_model variant) successfully GETs
  `<base_url>/v1/models` (vLLM) or `<base_url>/api/tags` (Ollama).
- Configured-but-unreachable renders as `failed` label with the
  `reachable.failure_reason` line + the amber Docker/WSL hint.
- The base URL is shown verbatim (not redacted) -- it's config, never
  secret.
- We never mark vLLM healthy unless the `/v1/models` response parses
  with a `data` field (existing `expected_json_field` enforcement).

### 4.3 Files

This phase added one component (`ConfigDrawerRows` inside
`ConnectionsV2Panel.tsx`) and one amber-box block. No new files; no
new endpoints. The `ProviderProbe` already handles local_model
correctly and was extended in Phase 7-A.

---

## 5. Phase E: tests

### 5.1 New test file

`backend/tests/test_connection_v2_seed_import.py` -- 16 tests across
8 classes:

| Class | Tests | Coverage |
|---|---|---|
| `TestSkillPackProbe` | 2 | Probe contract: always `failure_dim="callable"`, never raises; `kind=SKILL_PACK` |
| `TestSkillPackLabel` | 2 | derive_label terminal `"skill_pack"` branch + falls through to `"installable"` when not yet imported |
| `TestMcpImporter` | 2 | Creates V2 rows from detected MCPs (with env-name persistence, NO env values); idempotent on rerun |
| `TestCliRuntimeImporter` | 2 | Skips when binary not on PATH; creates row when binary present |
| `TestLocalModelImporter` | 2 | Skips when both Ollama / vLLM unconfigured; creates row with visible `base_url` (callable still False until probe) |
| `TestOAuthImporter` | 2 | Skips when `client_id` empty; persists `client_id` + `_client_secret_set` flag, NEVER reads secret value |
| `TestSkillPackImporter` | 1 | Imports V1 PLUGIN_CATALOG entries that have NO `mcp_package`; rows are `kind=skill_pack`, `callable=false` |
| `TestProviderImporter` | 1 | Creates provider row for configured key; key value NEVER persists in config |
| `TestCrossSourceIdempotency` | 2 | Full discovery is idempotent; sentinel-secret audit confirms NO secret value lands anywhere in any row |

The sentinel-secret audit (`test_no_secret_values_persist_anywhere`)
plants distinctive strings into 4 secret-bearing settings (OpenAI key,
Anthropic key, Google client_secret, MCP env value) and then scans
every imported row's `config` + `slug` + `display_name` + `vault_ref`
to assert no sentinel ever appears. Pin against accidental leakage in
future importer additions.

### 5.2 Backend test results

```text
pytest tests/test_connection_v2_seed_import.py
  16/16 PASS

Combined V2 regression (89 tests across 6 files):
  tests/test_connection_v2.py                       22/22 PASS
  tests/test_connection_v2_probe_truth.py            8/8  PASS
  tests/test_connection_v2_reconciliation.py        12/12 PASS
  tests/test_connection_v2_seed_import.py           16/16 PASS  (NEW)
  tests/test_phase7_lifespan_seed.py                 3/3  PASS
  tests/test_phase7_provider_probes.py              28/28 PASS
  ----------------------------------------------------------
  combined                                          89/89 PASS in 1.65s

Wider regression (V2 + state_machine + skill_pack matchers):
  tests collected via -k "state_machine or skill_pack or seed_import or
  probe_truth or connection_v2 or provider_probe or lifespan"
  -> 93 passed, 1 skipped in 10.24s
```

### 5.3 Frontend tsc

```text
$ cd frontend && npx tsc --noEmit
EXIT=0
```

### 5.4 Em-dash hygiene (project Rule 12)

Per-file `git diff` em-dash count across all 14 modified files: **0**.
No em-dashes introduced.

### 5.5 Pre-existing test failures (NOT caused by this PR)

`tests/test_connections.py` has uncommitted workspace changes from a
prior session that introduce 2 failing tests:

- `test_install_no_auth_connector_is_connected`
- `test_extensions_install_persists_tenant_mcp_server`

These tests were added to the working tree (visible in `git status` as
modified-not-committed) before this PR began and exercise V1 install
paths that this PR does not touch. They were failing on the previous
HEAD commit (`78bc059`) too. Out of scope for this PR; documented as
**TICKET-V1-INSTALL-PROMOTION** for a separate cleanup.

---

## 6. Why V2 was empty (root cause)

`backend/app/main.py:606` defines `_provider_v2_seed`, which:
1. Installs real probes for kind=provider
2. Iterates every tenant and seeds provider rows from configured API keys

Both steps were inside the `if not settings.use_connection_registry_v2:
return` early-out. The flag defaults to `False` in production AND in
dev. So:

- **Dev (flag OFF):** no startup seed runs. No probes installed. The
  V2 panel renders an empty list because the table is empty.
- **Production (flag OFF, intended):** also empty, but production
  doesn't expose the V2 panel as canonical (the same
  PR-CONNECTIONS-TRUTH-CLEANUP work made it canonical universally; the
  production rollout strategy was always "flip the flag last").

This PR splits the two concerns:
1. **Probe installation** moved OUT of the flag gate -- it's
   idempotent in-process registration with no side effects, and
   probes need to exist in the registry before discovery can probe
   newly-imported rows.
2. **Bulk auto-seed** stays inside the flag gate -- in production,
   we don't want every tenant's V2 table seeded automatically until
   the flag is ready to flip. In dev, operators opt in via the new
   `Import from detected sources` button.

---

## 7. What V2 now contains vs Legacy (after import)

| Source | Kind | Renders in | Callable proven by |
|---|---|---|---|
| Claude Code / Codex / Gemini MCP configs | `mcp_server` | MCP Servers V2 + All Connections V2 | future PR-CONN-MCP-PROBE (initialize + tools/list); today returns probe_unavailable |
| CLI runtimes (claude / codex / gemini binaries) | `cli_runtime` | All Connections V2 | future PR-CONN-CLI-PROBE; today probe_unavailable |
| Ollama / vLLM | `local_model` | All Connections V2 | existing ProviderProbe via `/api/tags` or `/v1/models`; works today |
| OpenAI / Anthropic / Gemini / Perplexity / Groq / OpenRouter / Together | `provider` | All Connections V2 + Plugins V2 | existing ProviderProbe -- works today |
| Gmail / Calendar / Drive / GitHub / Figma / Slack / Canva OAuth catalog | `oauth_app` | All Connections V2 + Plugins V2 | future PR-CONN-OAUTH-PROBE; today probe_unavailable |
| V1 PLUGIN_CATALOG entries without mcp_package | `skill_pack` | Plugins V2 + All Connections V2 | NEVER (by design) -- SkillPackProbe always returns "not callable" |

What stays Legacy/V1-only (Show legacy / advanced reveal):
- V1 `PluginsCatalogBrowser` install / connect / disconnect flow
- V1 `McpServersPanel` detect / install / probe view

---

## 8. Remaining blockers before USE_CONNECTION_REGISTRY_V2 flip in dev

Same blocker list as PR-CONNECTIONS-TRUTH-CLEANUP §3 (B1-B8) -- this
PR does not change the blocker list. What it changes is the dev
operator's ability to exercise the V2 surface without flipping the
flag: today, after running discovery once, the dev operator can see
every connection kind populated with real data and probe each one
independently (modulo B1-B5 probe implementations).

**Net effect of this PR on the flag-flip plan:**
- B1-B5 (real probes per kind) still required before dev flag flip.
- The new "discovery" surface is operator-triggered, so the flag flip
  itself stays a separate decision (when ready, auto-seed at startup
  per existing `_provider_v2_seed` logic + the new discovery service
  could be wired into lifespan as a complementary auto-import).

---

## 9. Files changed summary

| File | Status | Lines |
|---|---|---|
| `backend/app/models/connection_v2.py` | M | +10 / -1 |
| `backend/app/schemas/connection_v2.py` | M | +13 / -1 |
| `backend/app/services/connection_v2/state_machine.py` | M | +10 / -1 |
| `backend/app/services/connection_v2/__init__.py` | M | +6 / 0 |
| `backend/app/services/connection_v2/probes/__init__.py` | M | +13 / -3 |
| `backend/app/services/connection_v2/probes/skill_pack_probe.py` | A | +56 (NEW) |
| `backend/app/services/connection_v2/seeders.py` | A | +474 (NEW) |
| `backend/app/api/v1/connections_v2.py` | M | +35 / -0 |
| `backend/app/main.py` | M | +14 / -8 |
| `backend/tests/test_connection_v2_seed_import.py` | A | +485 (NEW, 16 tests) |
| `frontend/src/hooks/useConnectionsV2.ts` | M | +57 / -7 |
| `frontend/src/pages/connections/ConnectionsV2Panel.tsx` | M | +152 / -10 |
| `frontend/src/pages/connections/McpServersV2Panel.tsx` | M | +52 / -10 |
| `frontend/src/pages/connections/PluginsV2Panel.tsx` | M | +94 / -16 |
| `docs/Ultraview/PR_CONN_V2_SEED_IMPORT_REPORT.md` | A | this report |

No protected files (`vault_adapter.py`, `vault_migration.py`,
`oauth_credentials_store.py` per project Rule 18) were touched.

---

## 10. Honesty check (project CLAUDE.md Rule 17)

Every UI claim and backend status this PR ships passes the "where
does this persist?" + "how does the user see it fail?" test:

- **"Import from detected sources" button**: persistence = the V2 row
  itself; failures bubble through `runDiscoveryRefresh()` -> toast +
  `errorStore`.
- **`SkillPackProbe` "not callable" reason**: persisted as the row's
  `callable_failure_reason` after first probe; visible via the
  truth-ladder tooltip + DetailsDrawer.
- **Local model amber Docker/WSL box**: rendered ONLY when
  `reachable.failure_at` is fresh (after a real probe failed); not a
  blanket warning.
- **Skill-pack "No probe" affordance**: not a button, just an
  affordance with explanatory tooltip; no fake action.
- **`_client_secret_set: bool` flag**: derived from existence check;
  never reads the secret value.
- **MCP `env_var_count` + `env_var_names`**: derived from config
  inspection; values never read.

Nothing in this PR is a "looks complete but does nothing" surface.

---

## 11. Commit message

```
canonicalization: seed V2 connections from real runtime sources
```

Single commit on branch `rebuild-connections-mcp-runtime`.

---

**Stopping here as requested. Awaiting next founder direction.**
