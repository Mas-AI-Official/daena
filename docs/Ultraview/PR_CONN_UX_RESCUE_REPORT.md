# PR-CONN-UX-RESCUE Report

**Date:** 2026-05-02
**Branch:** `rebuild-connections-mcp-runtime`
**Author:** Claude Code (Opus 4.7) under founder direction
**Builds on:** PR-CONN-V2-SEED-IMPORT (`4b52d3f`) and
PR-CONNECTIONS-TRUTH-CLEANUP.

> **Thesis.** PR-CONN-V2-SEED-IMPORT shipped real backend discovery
> but the page still felt like migration / debug internals: tabs were
> labelled "All Connections (V2)", legacy plugin cards visually
> dominated under the "Show legacy / advanced" reveal, the "Discover"
> button lived inside two child panels, and "0 MCP servers" gave no
> diagnostic context. This PR rescues the UX by treating Connections
> as a real product surface: 7 product-named tabs (no V1 / V2 in any
> default label), one canonical Discover button at the page header,
> per-source summary card after each run, and an honest empty state
> for MCP that lists every searched path so "0 found" reads as
> "checked 9 paths, 3 existed, 0 had a mcpServers block." Skill packs
> get their own tab so capability bundles never compete visually with
> callable connectors. Local models get their own tab with explicit
> Docker / WSL guidance for the most common reachability failure.
> Detector adds WSL bridge paths so a Linux-side backend can find
> configs the operator wrote on the Windows side.

---

## 0. Hard rules honored

| Rule | Status |
|---|---|
| 1. No production deploy | Yes |
| 2. No `USE_CONNECTION_REGISTRY_V2=true` flip | Yes (`config.py:257` unchanged) |
| 3. No `vault --apply` | Yes |
| 4. No file deletions | Yes (`PluginsV2Panel.tsx` is now orphan but kept; legacy panels still mounted under Advanced) |
| 5. No secrets printed or committed | Yes -- detector debug payload is path metadata only; sentinel-secret audit pinned by tests |
| 6. No external scans | Yes |
| 7. No external messages | Yes |
| 8. No T5 / 3vilbob execution touched | Yes |
| 9. No backend rewrite | Yes -- detector + seeders extended in place; no service replaced |
| 10. No new dependencies | Yes -- pure stdlib (`os`, `platform`); no new pip / npm packages |
| 11. No "callable" claim without a real probe | Yes -- importer still only sets detected/configured/imported; truth ladder unchanged |
| 12. No em-dashes in new content (project Rule 12) | Yes (per-file `git diff` em-dash count = 0 across all 12 files; report itself = 0) |

---

## 1. Default user-facing UI changes (Part A)

### 1.1 Tab renames (no V1 / V2 terminology in default labels)

| Before | After |
|---|---|
| `All Connections (V2)` | `All Connections` |
| `Main Brain` | `Main Brain` (unchanged) |
| (collapsed under Plugins) | `Runtimes` (NEW tab) |
| `MCP Servers` | `MCP Servers` (unchanged) |
| `Plugins` (mixed kinds) | `Apps` (OAuth + plugin kinds only) |
| (mixed under Plugins) | `Skill Packs` (NEW tab, dedicated) |
| (collapsed under Connections) | `Local Models` (NEW tab) |
| `Legacy / Advanced` | `Advanced` |

7 primary tabs + 1 Advanced reveal toggle. Default view = `All
Connections`.

### 1.2 Legacy / V1 placement

All V1 surfaces live exclusively in the `Advanced` tab, hidden behind
the `Show advanced` toggle (default OFF, persisted to
`localStorage["daena.connections.show_advanced"]`). The Advanced panel
is preceded by a clear amber banner:

> **Advanced migration / debug view.** Not the live connection truth.
> The panels below are the legacy plugin browser and MCP detect /
> install flow. They use the older "credentials present == connected"
> heuristic and do NOT reflect real probe truth.

### 1.3 Developer copy moved out of default panels

| Surface | Before | After |
|---|---|---|
| `ConnectionsV2Panel` empty state | mentioned `POST /api/v1/connections/v2/discovery/refresh` + `kind=...` | empty state describes the operator action; API references moved to Advanced > "Internal endpoints + flags" `<details>` block |
| `McpServersV2Panel` empty state | mentioned `USE_CONNECTION_REGISTRY_V2` + flag-flip caveat | reads "No MCP servers found in detected config paths. Checked N paths..." with collapsible Searched paths list |
| V2 read-only mode banner | rendered on every visit when flag was OFF | removed from default panel; the flag conversation lives in Advanced > Internal endpoints |

### 1.4 V2-flag banner removal

The `useV2Flag` hook + emerald/amber V2 banner that PR-CONNECTIONS-
TRUTH-CLEANUP added to `ConnectionsV2Panel` is gone from the default
view. Operator-facing copy no longer says "V2 read-only mode" --
that's developer noise. The flag is documented under Advanced for the
operator who needs it.

---

## 2. Discovery button behavior (Part B)

### 2.1 One canonical action

The page header now has one CTA: **"Discover installed tools"**. It
calls `POST /api/v1/connections/v2/discovery/refresh` (the existing
endpoint -- no new endpoint needed) and dispatches a
`daena:retry-pending` window event so every open `useConnectionsV2`
poll-hook refetches immediately.

The button + per-source summary state are owned by `ConnectionsPage`
and passed down to child panels as props
(`discoveryReport` / `onDiscover` / `discovering`). Internal Discover
buttons in `ConnectionsV2Panel` and `McpServersV2Panel` are removed.

### 2.2 Per-source summary

After a successful discovery, the `All Connections` tab renders a
`DiscoverySummary` card listing every source:

```
Last discovery -- 12 new, 4 existed, 5 unconfigured, 0 failed
[MCP Servers: +3] [CLI Runtimes: +1] [Local Models: +1] ...
```

The badge color encodes source health: emerald when `total_created > 0`,
rose when `total_failed > 0`, slate when no changes.

The discovery report is also persisted to
`localStorage["daena.connections.last_discovery"]` so the summary
survives page reloads (helpful for diagnosing a stale state in dev).

### 2.3 Empty MCP state explained

When the MCP servers tab is empty AFTER discovery has run, the empty
state reads:

> **No MCP servers found in detected config paths.** Daena checked
> **N** paths across Claude Code, Codex, and Gemini CLI. **M** existed,
> **K** contained a `mcpServers` block.

Followed by a `Show searched paths (N)` `<details>` block listing
each candidate with `[cli] /path/to/file.json -- exists / parse_ok /
mcp_count` and a colored dot. Operator can immediately see whether
the issue is:

- File doesn't exist (slate dot, "not found")
- File exists but isn't valid JSON (amber dot, "parse_error:...")
- File parses but no `mcpServers` block (amber dot, "no_mcp_block")
- File has the block (emerald dot, "N mcpServer entries")

---

## 3. MCP config path coverage + debug payload (Part C)

### 3.1 New paths covered

| Path | Status before | Status after |
|---|---|---|
| `~/.claude/mcp.json` | covered | covered |
| `~/.claude.json` | covered | covered |
| `~/AppData/Roaming/Claude/claude_desktop_config.json` (Windows) | covered | covered |
| `~/.codex/config.json` | covered | covered |
| `~/.openai/codex.json` | covered | covered |
| `~/.config/codex/mcp.json` | covered | covered |
| `~/.config/google-gemini/mcp.json` | covered | covered |
| `~/.gemini/mcp_servers.json` | covered | covered |
| `~/.gemini/settings.json` | covered | covered |
| `/mnt/c/Users/<win-user>/AppData/Roaming/Claude/claude_desktop_config.json` | NOT covered (WSL hole) | covered when running in WSL |
| `/mnt/c/Users/<win-user>/.claude/mcp.json` | NOT covered | covered (WSL) |
| `/mnt/c/Users/<win-user>/.claude.json` | NOT covered | covered (WSL) |
| `/mnt/c/Users/<win-user>/.codex/config.json` | NOT covered | covered (WSL) |
| `/mnt/c/Users/<win-user>/.openai/codex.json` | NOT covered | covered (WSL) |
| `/mnt/c/Users/<win-user>/.gemini/mcp_servers.json` | NOT covered | covered (WSL) |
| `/mnt/c/Users/<win-user>/.gemini/settings.json` | NOT covered | covered (WSL) |
| `/mnt/c/Users/<win-user>/.config/google-gemini/mcp.json` | NOT covered | covered (WSL) |
| `$DAENA_CLAUDE_CONFIG` (env override) | NOT covered | covered (highest priority) |
| `$DAENA_CODEX_CONFIG` (env override) | NOT covered | covered (highest priority) |
| `$DAENA_GEMINI_CONFIG` (env override) | NOT covered | covered (highest priority) |

### 3.2 WSL detection

`_is_wsl()` reads `/proc/version` once; returns False on macOS / native
Windows / errors. `_wsl_windows_user_home()` enumerates
`/mnt/c/Users/<entry>` skipping system folders, returns the first
entry whose `AppData/Roaming` exists. Both helpers are safe to call
on any host -- they catch `OSError` and return None / False.

The candidate list is built lazily via `_candidates()` and cached at
the module level (`_CANDIDATES_CACHE`); `reset_candidates_cache()`
exists as a test hook.

### 3.3 Debug payload contract

`CLIMCPDetector.discover_with_debug()` returns
`tuple[list[DetectedMCP], list[CandidatePathProbe]]`. Each
`CandidatePathProbe` carries:

```python
@dataclass(slots=True)
class CandidatePathProbe:
    cli: str            # "claude_code" / "codex" / "gemini_cli"
    path: str           # absolute path Daena tried
    exists: bool
    parse_ok: bool
    has_mcp_block: bool
    mcp_count: int
    server_names: list[str]
    skip_reason: str    # "not_found" / "parse_error:..." / "no_mcp_block"
```

**NEVER carries env values, secret material, or full server config.**
Pinned by `test_debug_payload_never_contains_env_values` and
`test_report_debug_payload_never_leaks_env_values` (sentinel-secret
audits). The `DiscoveryReport.mcp_paths_searched` field surfaces the
same metadata via the API.

---

## 4. Skill pack truth (Part D)

### 4.1 Dedicated tab

`Skill Packs` becomes its own primary tab via
`SkillPacksPanel.tsx` (NEW). Filters `useConnectionsV2` to
`kind=skill_pack`. Header copy:

> Skill packs are reusable instructions / capabilities. They are not
> callable tools until connected to a runtime, MCP server, or app.
> Daena uses them as context so the LLM knows how to do specific tasks.

### 4.2 Row treatment

Each row renders with:
- Violet badge `skill pack`
- Inline `not callable` pill with tooltip
- Skill count + (truncated) skill IDs
- Source plugin id + category from V1 catalog
- **No Probe button** -- replaced by a `No probe` affordance whose
  tooltip cites the `SkillPackProbe` contract

This satisfies the brief's "Do not show Probe button for skill packs"
and "Do not make skill packs look like installed apps."

### 4.3 Apps tab no longer mixes skill packs

`AppsPanel.tsx` (NEW) takes over the OAuth + plugin kinds. Skill
packs are explicitly excluded so the Apps tab reads as "callable
third-party services."

---

## 5. Local model / vLLM / Ollama truth (Part E)

### 5.1 Dedicated tab

`Local Models` becomes its own primary tab via
`LocalModelsPanel.tsx` (NEW). Filters `useConnectionsV2` to
`kind=local_model`. Header copy:

> Local LLM endpoints (Ollama, vLLM, llama-server). Daena calls them
> via OpenAI-compatible APIs. A row is "healthy" only after a
> successful model-list probe -- configured but unreachable rows
> surface the URL plus Docker / WSL guidance.

### 5.2 Row treatment

Each row shows:
- Configured `base_url` verbatim (config; safe to print)
- `default_model` if set
- 6-dim truth ladder
- Probe button

When `truth.configured.value && !truth.reachable.value &&
truth.reachable.failure_at` is fresh, the row appends an inline amber
box:

> **Configured but unreachable.** Daena could not reach `<base_url>`.
> Last error: `<failure_reason>`.
>
> **Docker / WSL guidance:** if the backend runs in WSL or Docker,
> `127.0.0.1` may refer to that environment, not the Windows host. Try
> `host.docker.internal` or the configured bridge IP, or run the backend
> natively on the same host as the local model server.

### 5.3 Healthy gate

The truth ladder is unchanged: `healthy` only when the existing
`ProviderProbe` (which handles `kind=local_model` rows via the
`{base_url}` template for Ollama and vLLM) successfully GETs `/api/tags`
or `/v1/models` AND the response carries the expected JSON field
(`models` for Ollama, `data` for vLLM). No row gets `healthy` without a
successful probe.

---

## 6. Main Brain (Part F)

### 6.1 Already wired

`MainBrainPanel.tsx` was already correctly wired in PR
`PR-CONNECTIONS-TRUTH-CLEANUP §2.5`:

- `useConnectionsV2('cli_runtime')` provides truth indexed by slug
- Set Main Brain button is `disabled` when:
  `v2 row exists AND callable === false AND experimentalOverride === false`
- Tooltip surfaces `"V2 says not callable. Probe first or enable
  Experimental Override."`
- Backend (`PUT /api/v1/runtimes/primary` -> `set_primary_runtime` at
  `runtimes.py:487`) persists to `User.settings.primary_runtime`
  JSONB; verified via the lookup at `runtimes.py:131`.

### 6.2 Persistence verified

The brief's contingency `"If backend does not persist main brain,
disable the button and state 'Wiring pending.'"` does NOT apply --
backend persistence is wired. No code changes needed for Part F in
this PR.

### 6.3 Non-callable row visibility

Per the brief's rule "Non-callable rows can be visible but disabled
with reason," the existing behavior already satisfies this:
non-callable runtimes render with the V2 truth chip (rose
"V2 not callable") + the disabled Set Main Brain button + the tooltip
explaining why. No code change needed.

---

## 7. Tests run

### 7.1 New tests (Part C + sentinel-secret audit)

`backend/tests/test_connection_v2_ux_rescue.py` -- 14 tests across 3
classes:

| Class | Tests | Coverage |
|---|---|---|
| `TestCandidatePaths` | 6 | Native paths present; env-override priority; dedup; WSL bridge gate (NOT added when `_is_wsl()`=False); WSL bridge added when WSL + Windows home resolves; `_is_wsl()` safe on any host |
| `TestDiscoverWithDebug` | 5 | `CandidatePathProbe` returned per attempted path; missing path -> `not_found`; invalid JSON -> `parse_error:...`; valid JSON without `mcpServers` -> `no_mcp_block`; **debug payload sentinel audit** (env value planted in source must NOT appear in any probe field) |
| `TestDiscoveryReportShape` | 3 | `report.mcp_paths_searched` populated; **report-level sentinel audit** (env value in detected MCP must NOT appear in `mcp_paths_searched` debug entries); backward-compat `_import_mcp_servers` wrapper still returns `SourceReport` |

### 7.2 Updated PR-CONN-V2-SEED-IMPORT tests

`tests/test_connection_v2_seed_import.py` -- 12 mock sites switched
from `discover_all` -> `discover_with_debug` (with the new tuple
return shape). All 16 prior tests still pass.

### 7.3 Backend regression

```text
pytest tests/test_connection_v2.py
       tests/test_connection_v2_probe_truth.py
       tests/test_connection_v2_reconciliation.py
       tests/test_connection_v2_seed_import.py
       tests/test_connection_v2_ux_rescue.py
       tests/test_phase7_lifespan_seed.py
       tests/test_phase7_provider_probes.py
  -> 103 passed in 1.78s
```

### 7.4 Frontend tsc

```text
$ cd frontend && npx tsc --noEmit
EXIT=0
```

### 7.5 No frontend component tests existed for connections panels

The brief asked for "add/update frontend test if existing connections
component tests exist." Verified -- no `*.test.tsx` files exist for
the connections panels. Adding new ones is out of scope for the UX
rescue (would expand the surface area). Recommend a follow-up
PR-CONN-E2E-SUITE that adds Playwright specs covering:
- Default tab loads `All Connections`
- Show advanced toggle adds `Advanced` tab
- Discover button calls API + persists report to localStorage
- Empty MCP state shows searched paths after discovery

### 7.6 Em-dash hygiene

```
backend/app/services/mcp_sync/detector.py:           0 added
backend/app/services/connection_v2/seeders.py:       0 added
backend/tests/test_connection_v2_seed_import.py:     0 added
backend/tests/test_connection_v2_ux_rescue.py:       0 added
frontend/src/hooks/useConnectionsV2.ts:              0 added
frontend/src/pages/ConnectionsPage.tsx:              0 added
frontend/src/pages/connections/ConnectionsV2Panel.tsx: 0 added
frontend/src/pages/connections/McpServersV2Panel.tsx: 0 added
frontend/src/pages/connections/AppsPanel.tsx:        0 added
frontend/src/pages/connections/LocalModelsPanel.tsx: 0 added
frontend/src/pages/connections/RuntimesPanel.tsx:    0 added
frontend/src/pages/connections/SkillPacksPanel.tsx:  0 added
docs/Ultraview/PR_CONN_UX_RESCUE_REPORT.md:          0
```

---

## 8. Why MCP count may still be 0 (the root diagnosis)

The founder's complaint was "MCP servers from Claude/Codex/Gemini are
not appearing." After this PR, the operator can see EXACTLY why on
their machine:

Live smoke-test result on the founder's Windows host (no WSL):

```
paths_checked=9
paths_existing=3
paths_with_mcp_block=0
total_mcps=0
```

Translation: all three of `~/.claude/mcp.json` / `~/.claude.json` /
`~/AppData/Roaming/Claude/claude_desktop_config.json` exist (likely
from prior Claude Code use), but **none of them carries a
`mcpServers` block**. The operator's MCPs may be configured in
Claude Desktop (the GUI app, separate config) or in another tool.

Two next-step options for the operator:
1. Add MCP entries to one of the supported config paths and re-run
   Discover. The empty-state's per-path debug list shows exactly
   which paths are searched.
2. Set `DAENA_CLAUDE_CONFIG` / `DAENA_CODEX_CONFIG` /
   `DAENA_GEMINI_CONFIG` env vars to point at non-standard config
   locations.

---

## 9. Git dirty files NOT committed (Part G)

Per the brief's rule "Do not commit unrelated tool metadata," I left
all of the following unstaged. The commit only carries PR-relevant
files.

| Path | Owner / why dirty |
|---|---|
| `.axon/meta.json` | axon graph rebuild artifact |
| `backend/.axon/meta.json` | axon graph rebuild artifact |
| `AGENTS.md` | prior session edits |
| `backend/app/api/v1/agent_ops.py` ... and ~30 other src files | pre-existing workspace changes from prior sessions (see git diff for each); none touched by this PR |
| `backend/tests/test_agent_ops.py`, `tests/test_connections.py`, `tests/test_dcp_loader.py` | pre-existing uncommitted V1 workspace changes (these contain the 2 failing V1-install tests called out in PR-CONN-V2-SEED-IMPORT report) |
| `docs/ADR-002-connections-rebuild-locked-decisions.md` (deleted), `CONNECTIONS_*.md` (deleted) | pre-existing cleanup; appears the operator moved them to `docs/Ultraview/` in a prior session |
| `frontend/src/pages/SkillsPage.tsx`, `frontend/src/pages/settings/SettingsModelsRuntimes.tsx` | pre-existing workspace changes |
| `frontend/src/components/connections/ConnectorInstallDialog.tsx` (untracked) | pre-existing untracked dir; not related to this PR |

These can be inspected via `git diff <path>` / committed in a
follow-up cleanup PR after the founder reviews.

---

## 10. Files changed (this PR only)

| File | Status | Lines |
|---|---|---|
| `backend/app/services/mcp_sync/detector.py` | M | +143 / -8 |
| `backend/app/services/connection_v2/seeders.py` | M | +52 / -6 |
| `backend/tests/test_connection_v2_seed_import.py` | M | +12 / -12 (mock signature swap) |
| `backend/tests/test_connection_v2_ux_rescue.py` | A | +303 (NEW, 14 tests) |
| `frontend/src/hooks/useConnectionsV2.ts` | M | +13 / 0 (new types) |
| `frontend/src/pages/ConnectionsPage.tsx` | M | +208 / -75 (full re-structure) |
| `frontend/src/pages/connections/ConnectionsV2Panel.tsx` | M | +149 / -78 |
| `frontend/src/pages/connections/McpServersV2Panel.tsx` | M | +185 / -92 |
| `frontend/src/pages/connections/AppsPanel.tsx` | A | +220 (NEW) |
| `frontend/src/pages/connections/LocalModelsPanel.tsx` | A | +200 (NEW) |
| `frontend/src/pages/connections/RuntimesPanel.tsx` | A | +175 (NEW) |
| `frontend/src/pages/connections/SkillPacksPanel.tsx` | A | +145 (NEW) |
| `docs/Ultraview/PR_CONN_UX_RESCUE_REPORT.md` | A | this report |

`frontend/src/pages/connections/PluginsV2Panel.tsx` is now an orphan
(no longer imported by `ConnectionsPage.tsx`). Per Hard Rule 4 it is
NOT deleted; future cleanup PR can archive it once the operator
confirms the new Apps + Skill Packs split covers all use cases.

No protected files (`vault_adapter.py`, `vault_migration.py`,
`oauth_credentials_store.py` per project Rule 18) were touched.

---

## 11. Remaining blockers before Connections is product-ready

| # | Blocker | Owner / next step |
|---|---|---|
| R1 | Real `McpServerProbe` for `kind=mcp_server` -- `initialize` + `tools/list` JSON-RPC handshake. Today returns `probe_unavailable` for any imported MCP row. | PR-CONN-MCP-PROBE |
| R2 | Real `CliRuntimeProbe` for `kind=cli_runtime` -- spawn binary, version handshake, auth check. | PR-CONN-CLI-PROBE |
| R3 | Real `OAuthAppProbe` for `kind=oauth_app` -- token introspection or harmless authenticated GET. | PR-CONN-OAUTH-PROBE |
| R4 | Real `PluginProbe` for `kind=plugin` -- transport-dependent. | PR-CONN-PLUGIN-PROBE |
| R5 | E2E Playwright spec for the new tab structure (Discover button, advanced toggle, empty MCP state debug list). | PR-CONN-E2E-SUITE |
| R6 | Archive orphan `PluginsV2Panel.tsx` once Apps + Skill Packs split is confirmed. | Cleanup PR |
| R7 | DXT extensions (`~/AppData/Roaming/Claude/Claude Extensions/<name>/manifest.json`) not yet a discovery source. Detector knows about them via `extension_scanner.py` but the seeders don't import them as `kind=mcp_server`. | Optional follow-up PR-CONN-DXT-IMPORT |
| R8 | Frontend localStorage record of last discovery is not size-bounded. If a single discovery returns 100+ paths this could grow noticeably. | Trivial follow-up; cap to last N entries |

---

## 12. Honesty check (project CLAUDE.md Rule 17)

Every UI surface this PR ships passes the "where does this persist?" +
"how does the user see it fail?" test:

- **"Discover installed tools" button**: triggers backend; success is
  reflected in V2 rows (server-persisted) AND
  `localStorage["daena.connections.last_discovery"]` (per-browser).
  Failures land in toast + the global `errorStore`.
- **`DiscoverySummary` per-source badges**: derived from the same
  report; honest because the report is the API response.
- **MCP empty-state path debug list**: derived from
  `report.mcp_paths_searched`; pinned by sentinel-secret tests so the
  list NEVER contains env values.
- **`Show advanced` toggle**: persisted to `localStorage`, honest about
  being per-browser (no server-side sync).
- **"Skill pack" + "not callable" badges**: backed by
  `kind=skill_pack` + `SkillPackProbe.failure_reason`; pinned by tests.
- **Local model "Configured but unreachable" amber box**: rendered ONLY
  after a real probe failure with fresh `failure_at`; not a blanket
  warning.

Nothing in this PR is a "looks complete but does nothing" surface.

---

## 13. Commit message

```
canonicalization: simplify connections product UX
```

Single commit on branch `rebuild-connections-mcp-runtime`.

---

**Stopping here as requested. Awaiting next founder direction.**
