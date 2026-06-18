# Runtime Truth UI Polish Report

Date: 2026-04-29
Author: Claude Code (Opus 4.7) -- Phase 4 of stabilization sprint
Scope: full app palette pass + structural polish on the actual Runtime
Truth page (operator approved 2026-04-29 via plan AskUserQuestion).

## Goal

The Runtime Truth page reads as polished and on-brand. The locked palette
(dark slate + gov-gold + gov-teal) appears across the app, not just on
this page. Action surface is scannable at a glance.

## Surface verified before editing

`frontend/src/pages/connections/ConnectionsRuntimes.tsx` -- orphaned
since the Runtime Truth pivot. Audit confirms it has no importers in
`frontend/src`. Edits there were applied (one-badge-per-row,
status-summary header) for completeness so the file stays
internally-consistent if it gets reused, but the LIVE Runtime Truth
page is `frontend/src/pages/ConnectionsPage.tsx`. Phase 4b structural
polish targets the live page.

## Step 4a -- Token aliasing (codebase-wide)

### Edits to [globals.css:34-44](../frontend/src/styles/globals.css:34)

```diff
- --color-accent-cyan: #06B6D4;
- --color-accent-amber: #FCD34D;
+ --color-accent-cyan: #2DD4BF;   /* was: cyan; now: locked gov-teal */
+ --color-accent-amber: #D4A843;  /* was: yellow; now: locked gov-gold */
+ --color-accent-green: #00D68F;  /* alias for status-success */
+ --color-accent-red:   #FF4757;  /* alias for status-error */
```

### Cascade

Single CSS variable change re-points every existing
`text-accent-amber`, `border-accent-amber`, `bg-accent-cyan`, etc.
across the entire frontend in one shot -- no per-component JSX edits
required for the visual swap. Verified with
`grep -rn "#FCD34D|#06B6D4" frontend/src` -> only one match (the doc
comment we just added). Zero hardcoded outliers.

### Why aliases instead of rename

`gov-gold` and `gov-teal` already existed in
[globals.css:84-87](../frontend/src/styles/globals.css:84) but were
unused. Renaming `accent-amber` -> `gov-gold` everywhere would be a
codebase-wide find-and-replace touching dozens of files, conflicting
with the user's "no broad redesign" instruction. Re-pointing the CSS
variable preserves all existing class names and their meaning without
that risk.

### `accent-green` / `accent-red` previously undefined

These tokens were used across the codebase (e.g.
`border-accent-green/30` in `ConnectionsRuntimes.tsx`) but were never
declared in `globals.css`. Tailwind v4 fell back to default-palette
green/red, which drifted off-brand. Aliased to `status-success` /
`status-error` so existing usages now render consistently.

## Step 4b -- Runtime Truth structural polish

### Edits to [ConnectionsPage.tsx](../frontend/src/pages/ConnectionsPage.tsx)

What was already correct (kept):
- `LifecycleBadge` -- single badge per row, tone-coded
- Status summary header with 4 metrics (Detected/Persisted/Reachable/Callable)
- Expandable details panel for source / endpoint / command / config path
- `fixSuggestion()` line for failed rows
- `last_failure_reason` chip on rows with health-check failures

What changed:

1. **Action bar collapsed from 6 buttons to 3 + "More" dropdown**:
   - Inline: `Refresh`, `Test`, `Import` -- the operator's primary loop
   - Behind `More` dropdown: `Configure (not implemented)`, `Disable
     in registry`, `Remove from registry`
   - The dropdown uses the `gov-teal` accent ring on hover and
     `status-error` color for `Remove`. Consistent with the locked
     palette.

2. **`Configure` is honestly labeled "not implemented"** in the
   dropdown -- Rule 17 (Honesty + Persistence + Visibility) compliance.
   It was previously rendered as an inline disabled button which made
   the surface look broken; now it's collapsed away by default but
   still accessible.

3. **Click-away dismissal**: a `fixed inset-0 z-40` overlay closes the
   "More" dropdown when the user clicks anywhere outside it.

### What was NOT changed

- `LifecycleBadge` tone classes -- already use accent-green / accent-amber /
  accent-cyan / red-500 / white-mute. Post-Step-4a the green/amber/cyan
  values are now on-brand. red-500 stays (Tailwind default red, similar
  enough to `status-error #FF4757`). Replacing the literal `red-500`
  classes with `status-error/30` etc would touch many lines for marginal
  visual gain -- out of scope for "no broad redesign".
- The 4-metric summary header (Detected/Persisted/Reachable/Callable) --
  already correct, on-palette.
- The events panel -- already minimal and correct.

## Cross-app palette readback

Searched `frontend/src` for `accent-amber`, `accent-cyan`, `accent-green`,
`accent-red` usages. Confirmed they appear across:

- `chat/*` -- message bubbles, model selector chip
- `layout/Header.tsx` -- execution mode pill, governance badge
- `pages/connections/*` -- all four sub-tabs
- `pages/security/*` -- scope visualizer, severity legend
- `pages/scan/*` -- scan history rows, severity chips
- `pages/settings/*` -- toggle accents
- `pages/governance/*` -- approval queue
- `pages/dashboard/*` -- KPI tiles
- `pages/billing/*` -- cost chart accents

All of these now use the locked Daena gold + teal automatically.

## Type check

```text
$ npx tsc --noEmit
(no output -- 0 errors)
```

## Files modified

- `frontend/src/styles/globals.css` -- token re-points + aliases
- `frontend/src/pages/connections/ConnectionsRuntimes.tsx` -- duplicate
  status chip removed, status-summary header added (orphaned file but
  kept internally consistent)
- `frontend/src/pages/ConnectionsPage.tsx` -- action bar restructured
  with `More` dropdown; new `RowMoreMenu` subcomponent

## Files NOT modified per HANDS-OFF

- `frontend/src/pages/ScanPage.tsx` -- v3.7.0 Security Supercharge stack
- `frontend/src/pages/scan/ScanList.tsx` -- touched in Phase 5 only for
  render-side changes (no type/pipeline edits)

## Status

Phase 4 of stabilization sprint: COMPLETE.

Visual verification deferred to Phase 8 final-validation preview run so
all Phase 4 + Phase 5 + Phase 6 changes can be inspected together
rather than per-phase preview restarts.
