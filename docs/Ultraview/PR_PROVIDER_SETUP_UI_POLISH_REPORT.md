# PR-4 — Provider setup UI polish (Sprint-12A)

**Sprint:** DAENA-RUNTIME-QE-ROUTER-READINESS-SPRINT-12A
**Date:** 2026-05-05
**Author:** Mythos (Daena, via Claude Code)

## Goal

Surface the readiness inventory + QE/Council mode in the existing
settings surface so the operator sees what's ready, what's degraded,
and what needs setup — without spinning up a parallel runtime page
(CLAUDE.md Rule 2).

## What changed

### 1. New component: `frontend/src/components/common/BrainReadinessPanel.tsx`

Self-contained, read-only React component that consumes:

- `GET /api/v1/system/runtime-readiness`
- `GET /api/v1/system/qe-readiness`

Renders three sections:

#### (a) Router decisions block

Shows the current pick for each role:

- **main brain** (with `cost_class` label: `Free / local`, `Subscription`, `Metered API`)
- **web grounding**
- **coder**
- **researcher**
- **QE mode pill**: `QE Full` (green) / `QE Degraded` (amber) /
  `QE Unavailable` (red), with mode_reason as tooltip.

If a role has no ready candidate, the value is rendered as
`— none ready —` in amber. The `next_action` plain-English string
appears below the grid as a "next:" callout.

#### (b) QE/Council slot assignment (collapsible details)

Per-slot row: slot name, runtime that filled it, fill source
(`preferred` / `fallback_role` / `unfilled`).

#### (c) Per-runtime list

One row per detected runtime with:

- Kind icon (CPU for `local_llm`, terminal for `cli_runtime`,
  activity for `api_provider`)
- Display name + id (monospace)
- `cost_class` label
- **Readiness state pill** with five honest states:
  - `Ready` (emerald)
  - `Configured, untested` (amber)
  - `Detected, offline` (orange)
  - `Not configured` (slate)
  - `Unknown` (slate)
- Recommended role + endpoint URL (if present)
- `safe_failure_reason` rendered inline when state ≠ ready

### 2. Mounted into `SettingsModelsRuntimes`

The panel sits at the **top** of the unified Models & Runtimes tab.
Reason: when an operator opens Settings to check why an enrichment
isn't working, the readiness picture should be the first thing they
see — not buried under three sections.

No duplicate Settings page. No new Connections page. The panel is
also reusable on Connections / a future Brain page when those
surfaces want it.

### 3. Honesty + Persistence + Visibility (CLAUDE.md rule 17)

| Honesty rule | Implementation |
|---|---|
| No silent error suppression | Errors from the two endpoints land in inline `<div className="text-amber-300">` |
| No fake "online" pills | `Ready` only appears when `readiness_state === 'ready'`. Configured-but-not-callable is `Configured, untested`. |
| No "demo data" fallbacks | Empty list renders `"No runtimes detected. Click Refresh to probe."` |
| No silent metered usage | `Metered API` cost-class label visible on the main-brain row when applicable; the operator can refuse it |

### 4. No secret rendering

The component types declare no `api_key`, `token`, or `secret` field.
The backend never emits one (regex test in `test_runtime_readiness.py`
enforces). The UI cannot leak what it never receives.

## Tests

Frontend: `npx tsc --noEmit` exit 0. The component is type-safe;
no new pytest suite added because PR-4 is a frontend wiring change
of read-only data, and the data shape is already covered by
`test_runtime_readiness.py` (PR-1+2) + `test_qe_council_assignment.py`
(PR-3).

## Hard-rule audit

| Rule | Status |
|---|---|
| No secret values in inline fields | ✅ — secrets stay in the existing Provider Keys flow |
| No "connected" without callable proof | ✅ — pill logic enforces |
| No duplicate Settings | ✅ — extends `SettingsModelsRuntimes` |
| No paid call fires from panel | ✅ — read-only endpoints |

## Files touched

```
new:        frontend/src/components/common/BrainReadinessPanel.tsx
modified:   frontend/src/pages/settings/SettingsModelsRuntimes.tsx
new:        docs/Ultraview/PR_PROVIDER_SETUP_UI_POLISH_REPORT.md
```

## What this PR does *not* do (deferred)

- Click-through "Test provider" button per row. Per-provider
  zero-cost test endpoints don't exist yet (the backend plumbing
  is the follow-up to PR-1).
- "Mark provider disabled" toggle. The truth registry doesn't
  expose a disable knob; that's a separate small PR.
- Inline secret entry. Per the brief: secret entry stays in the
  existing Provider Keys flow.

## Next step

PR-5 — Sprint-12A smoke. Verifies the runtime readiness ladder
end-to-end and confirms it's safe to start Sprint-12 brain
enrichment on top.
