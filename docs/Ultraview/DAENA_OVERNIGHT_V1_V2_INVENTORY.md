# Daena V1 / V2 / Legacy Canonicalization Inventory
Date: 2026-05-07
Author: OVERNIGHT scope (PR-1)
Scope: every V1/V2/legacy reference still mounted in code, ranked by retirement difficulty

## Headline

The user-facing UI is already V2-canonical post-V3-Phase-1. Zero "(V2)" labels, zero "Legacy V1" labels, zero "OLD V1 registry" copy in normal-mode JSX. What remains is **internal vocabulary** (file names, code keys, test fixtures, ADR docs) and a **deliberate Compatibility panel** behind the Diagnostics tab for migration debugging.

This is on purpose. Retiring internal vocabulary is high-effort, low-value (the operator never sees these strings). The right move is to retire only the surfaces that touch the runtime.

## Surfaces inventory

### Tier A — Mounted, runtime-active, non-canonical (none)

There is currently no surface in normal-mode UI that mounts a V1 component. V3 Phase 1 stripped the last user-visible V1/V2 vocabulary.

### Tier B — Mounted, but behind Diagnostics (deliberate, do not retire blindly)

| Surface | File | Why it stays |
|---|---|---|
| Compatibility panels (`legacy_v1` key) | `frontend/src/pages/ConnectionsPage.tsx:362,450` | Migration debugging only. Rose-bordered warning at top reads "Compatibility view -- debug only ... writes to the legacy registry and may not mirror to the canonical truth ladder." |
| `ConnectionsV2Panel.tsx` | `frontend/src/pages/connections/ConnectionsV2Panel.tsx` | Diagnostics-only registry overview pane |
| `McpServersV2Panel.tsx` | `frontend/src/pages/connections/McpServersV2Panel.tsx` | Diagnostics-only MCP raw view |
| `PluginsV2Panel.tsx` | `frontend/src/pages/connections/PluginsV2Panel.tsx` | Diagnostics-only plugin raw view |
| `PluginsCatalogBrowser.tsx` ("Legacy install (not recommended)") | `frontend/src/pages/connections/PluginsCatalogBrowser.tsx` | Legacy install button explicitly demoted; gated by `test_legacy_install_button_relabeled_and_muted` |

These are reachable only when the operator opens the Diagnostics tab AND drills into the corresponding sub-section. The default UI never references them.

### Tier C — Backend code paths (canonical V2; no V1 module exists)

| Path | Status |
|---|---|
| `backend/app/services/connection_v2/` | **Canonical.** All seeders, probes, registry, reconciliation, skill_executor live here. |
| `backend/app/services/connection_v1/` | **Does not exist.** V1 module retired by file long ago. |
| `backend/app/api/v1/connections_v2.py` | Canonical V2 endpoint group |
| `backend/app/schemas/connection_v2.py` | Canonical V2 schema |

Note: `/api/v1/` in route paths is **API path versioning**, NOT product V1. The "v1" in the URL refers to the FastAPI router version. Connection V2 endpoints live AT `/api/v1/connections-v2/...`. This is industry-standard and should not be conflated with the product V1/V2 split.

### Tier D — Test fixtures and ADR docs

These reference V1/V2 in test names and report names. **Do not retire** — they encode acceptance contracts and historical decisions.

- `backend/tests/test_connection_v2_*` (multiple files)
- `backend/tests/test_acceptance_status_panel_contract.py::test_legacy_v1_section_carries_clear_warning` — patched 2026-05-07 to accept new "Compatibility view -- debug only" copy
- `docs/Ultraview/PR_CONN_*` — historical PR reports
- `docs/Ultraview/DAENA_CONNECTIONS_V3_*` — recent V3 phase reports

## Retirement difficulty / safety table

| Surface | Effort | Risk | Recommended action |
|---|---|---|---|
| Tier A (none) | n/a | n/a | Already done |
| `legacy_v1` Compatibility section | Low (1 commit) | **MEDIUM** — operators may use it for migration debugging | KEEP. It's behind Diagnostics, has a rose warning, is in the contract test. Retire only after operator confirms zero use for 30+ days. |
| `ConnectionsV2Panel.tsx` | Low | LOW | Retire only after the canonical Plugins tab absorbs registry-overview diagnostics. Currently mounted only at `section === 'overview'` in Diagnostics. |
| `McpServersV2Panel.tsx` | Low | LOW | Mounted at `section === 'mcp'` in Diagnostics. Useful for raw MCP probe inspection. Keep until canonical "MCP wrong-pkg" UI chip ships (PR not yet scheduled). |
| `PluginsV2Panel.tsx` | Low | LOW | Mounted at no current `section`? Need verification. If unmounted, safe-delete. |
| `PluginsCatalogBrowser.tsx` "Legacy install" path | Low | LOW | Already demoted; safe to delete after one full release cycle confirms no operator click-throughs. |
| `connection_v2/` backend rename | High | HIGH | Would touch ~30 imports. Renaming `connection_v2` → `connection` is cosmetic. Skip. |
| `/api/v1/connections-v2/` URL rename | High | HIGH (breaks frontend clients + external scripts) | Skip. Industry-standard path versioning. |

## Concrete OVERNIGHT-PR-11 retirement candidates

Items that can be safely deleted in a future commit (not done tonight):

1. **`PluginsV2Panel.tsx`** — verify unmounted, then `git rm`
2. **"Legacy install (not recommended)" button** in `PluginsCatalogBrowser.tsx` — replace with a clear "use canonical install via Plugins tab" redirect button
3. **Empty Compatibility panel sections** — `legacy_v1` only renders `<PluginsCatalogBrowser />`. Once the Legacy install button is gone, the section's only utility is reading historical state — narrow it to a read-only timeline.

Items that should stay until further investigation:

1. `legacy_v1` section infrastructure (the routing, the warning block)
2. `ConnectionsV2Panel`, `McpServersV2Panel` (Diagnostics-only registry views)
3. All `connection_v2` backend module names (cosmetic; high-cost, zero-user-value rename)

## Decision rule going forward

Per Honesty rule 17 ("if a feature cannot answer 'where does this persist?' and 'how does the user see it fail?', it does not ship"):

- Diagnostics-tab surfaces are explicitly **operator-debug** scoped. They satisfy the rule because their persistence (legacy registry) and failure visibility (rose warning + contract test) are explicit.
- Default-view surfaces must be V2-canonical. Adding any new V1 reference to default view is a regression.
- Internal vocabulary (file names, test names) is not user-visible and is not subject to the rule.

## Tests pinning the contract

| Test | What it gates |
|---|---|
| `test_legacy_v1_section_carries_clear_warning` | Compatibility section retains explicit "debug only" warning |
| `test_legacy_install_button_relabeled_and_muted` | "Legacy install" button is demoted to muted styling |
| `test_acceptance_status_panel_contract` | Acceptance ladder render contract |

If retiring a surface, run all three before and after to confirm the contract still holds.
