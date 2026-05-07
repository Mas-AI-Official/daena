# Daena V1 Retirement Gate — Plan
Date: 2026-05-07
Author: OVERNIGHT scope (PR-11)
Status: **PLAN ONLY — NO DELETIONS TONIGHT**

## Why this is a gate, not a sprint

The V1/V2 inventory (PR-1) confirmed there is no V1 surface left in normal-mode UI. What remains is:

1. A `legacy_v1` Diagnostics section, kept on purpose for migration debugging.
2. Three `*V2Panel.tsx` files mounted only inside Diagnostics.
3. A `PluginsCatalogBrowser.tsx` "Legacy install" button explicitly demoted.

Retiring these has near-zero user-visible upside (founder never sees them) and meaningful downside (loss of debug surface, broken contract tests, regressions during migration windows). So this is a **gate** — work that should only proceed when an explicit trigger fires, not a sprint that should be scheduled now.

## Gate conditions

Each tier below has a "promote when" condition. Do not promote without it.

### Tier 1 — Already shipped (V3 Phase 1)

- ✓ Strip "(V2)" suffix from Diagnostics tab labels
- ✓ Rename "Legacy V1 panels" → "Compatibility panels"
- ✓ Rename "Advanced" → "Diagnostics" (label only; routing key unchanged)
- ✓ Rewrite "Internal V2 / V1 surfaces" banner copy to mode-neutral language

### Tier 2 — Promote when operator confirms zero use for 30 days

- `legacy_v1` Compatibility section — entire `section === 'legacy_v1'` branch in `frontend/src/pages/ConnectionsPage.tsx:450`
  - **Trigger**: telemetry shows zero clicks on the section for 30 consecutive days, AND operator explicitly confirms they no longer need migration debugging
  - **Test impact**: must update `test_legacy_v1_section_carries_clear_warning` to skip or delete
  - **Safety check before deletion**: backup the rose warning + Compatibility view rendering as a separate `MigrationDebugPanel.tsx` mounted at `/admin/migration-debug` for emergency access

### Tier 3 — Promote when canonical Plugins tab absorbs the diagnostic

- `ConnectionsV2Panel.tsx` (registry overview) — promote when the canonical Plugins tab gains an "All connectors / overview" view
- `McpServersV2Panel.tsx` (raw MCP) — promote when the canonical Plugins tab gains a per-card "Show probe payload" expander
- `PluginsV2Panel.tsx` — verify if currently mounted; if unmounted, safe-delete now

### Tier 4 — Promote when API path versioning policy changes

- `/api/v1/connections-v2/` URL pattern — DO NOT RENAME until the project-wide API versioning policy explicitly bumps to v2 or v3. The "v1" in the URL refers to the FastAPI router version, not the product V1.
- `backend/app/services/connection_v2/` module name — cosmetic; high import-touch cost; rename only as part of a broader backend module reorg.

## Pre-flight checklist for any future deletion

When the time comes to retire a tier-2 or tier-3 surface:

1. Run the contract tests pinned in `DAENA_OVERNIGHT_V1_V2_INVENTORY.md` "Tests pinning the contract" section.
2. Grep the rest of the codebase for the file/symbol name; verify no other consumer.
3. Tag the commit before deletion (`git tag pre-retire-<surface>`).
4. Open a PR with a single deletion + the test update; do NOT bundle with feature work.
5. After merge, run the full backend test suite + frontend tsc + manual smoke of `/connections` Diagnostics tab.
6. If any contract test breaks unexpectedly, revert via the tag.

## Anti-checklist (DO NOT do these)

- ❌ `rm` the Compatibility section in the same commit as a feature change
- ❌ Rename internal `connection_v2` to `connection` (cosmetic, high-cost, zero-user-value)
- ❌ Bump `/api/v1/...` URLs without a written API versioning policy change
- ❌ Delete `*V2Panel.tsx` files without confirming no remaining consumer
- ❌ Edit the contract tests to make a bad deletion pass

## Decision rule going forward

Per Honesty rule 17: a retirement is justified only if removing the surface improves operator clarity AND no debug path is lost. If either fails, the surface stays.

The current Diagnostics-tab surfaces all pass this rule for "stay":
- They improve clarity by isolating debug views from the canonical UI (already done in V3 Phase 1)
- Removing them would lose the migration debugging path

This will change once telemetry confirms zero use OR the canonical Plugins tab absorbs the equivalent diagnostic.

## TL;DR

**Do nothing tonight.** The V3 Phase 1 changes are sufficient for "morning ready." Retirement of the remaining surfaces should wait for explicit triggers (zero-use telemetry, canonical absorption, or a project-wide versioning policy change). The plan above documents the path so that future retirement work is procedural, not exploratory.
