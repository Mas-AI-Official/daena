# Phase 5 PR 1 — Connections Frontend Rebuilt on V2 Truth

**Status:** Complete (local dev only).
**Date:** 2026-05-01.
**Branch:** `rebuild-connections-mcp-runtime`.
**Builds on:** Phase 4b PR 3 (commit `681cfa9`).

## What this PR ships

A new "All Connections (V2)" tab on `/connections` that renders rows
straight from the `ConnectionRegistryV2` truth tables. Every row shows
the 6 truth dimensions and the derived label from `derive_label`. **No
row says &ldquo;connected&rdquo; unless `callable=true`.**

## Files

| File | Role |
|---|---|
| `frontend/src/hooks/useConnectionsV2.ts` | NEW — polls `/api/v1/connections/v2`, exposes mutations (probe / enable / disable / archive), abort-cancels stale fetches on kind switch |
| `frontend/src/pages/connections/ConnectionsV2Panel.tsx` | NEW — main panel: summary cards strip, search, filter, grouped table, details drawer, mode banner |
| `frontend/src/pages/ConnectionsPage.tsx` | Adds new "All Connections (V2)" tab (default), keeps the 3 legacy tabs intact |

## Truth-rule UI invariants enforced

| Rule | How the UI honors it |
|---|---|
| `imported != callable` | Status pill never says &ldquo;healthy&rdquo; unless `row.label == healthy` (computed by `derive_label` from real truth dims, not from row presence) |
| `detected != reachable` | The truth-ladder mini chips show each dim independently with color: green=ok, red=failed, slate=unproven |
| `reachable != authenticated` | Drawer shows per-dim `failure_reason` and `failure_at` so an op can see exactly which step the probe couldn't get past |
| `authenticated != callable` | A row with `authenticated=true, callable=false` renders as `failed` in pill + `auth ok / callable not yet proven` in the ladder |
| stale != failed | `healthy_stale` and `degraded_stale` get muted variants of healthy/degraded colors, NOT the rose/red treatment of `failed` |
| op-in-progress visible | `installing`, `auth_pending`, `probing` get pulsing dots and their own muted styles |

## Buttons

Every button is wired to a real backend endpoint (no dummy actions):

| Button | Endpoint | Notes |
|---|---|---|
| Probe | `POST /api/v1/connections/v2/{id}/probe` | non-silent (toasts on failure) |
| Enable | `POST /api/v1/connections/v2/{id}/enable` | flips `disabled=false` |
| Disable | `POST /api/v1/connections/v2/{id}/disable` | flips `disabled=true`; archives keep their state |
| Archive | `DELETE /api/v1/connections/v2/{id}` | soft-delete, requires &ldquo;Click again to confirm&rdquo; |
| Refresh | `GET /api/v1/connections/v2` | manual refetch, debounce-free |

## Mode banner

The page reads `v2_enabled` from `GET /api/v1/connections/v2/reconciliation/status`
(silent on 403, defaults to OFF) and shows:

- **Amber banner** when `USE_CONNECTION_REGISTRY_V2 = false` — explains
  that legacy mode is in effect; mutations from legacy routes will not
  mirror to V2 and statuses fall back to `_status_for_install`.
- **Emerald banner** when flag is on — &ldquo;Status reflects real probe
  results.&rdquo;

This is the antidote to the previous &ldquo;UI says connected, backend says broken&rdquo;
drift the founder flagged.

## Layout

- **Summary strip** (6 cards, one per kind) — total / healthy / failed
  counts. Clickable: filters the table to that kind.
- **Toolbar** — search, kind dropdown, refresh.
- **Grouped table** — collapsible per kind. `cli_runtime`, `mcp_server`,
  `provider`, `oauth_app`, `plugin`, `local_model`.
- **Truth ladder mini** on each row — six small chips with tooltip
  showing `failure_reason` if any.
- **Details drawer** — full truth ladder with per-dim timestamps,
  failure reasons, governance tier, healthy ratio, and a &ldquo;Run live
  probe&rdquo; button.

## Performance

- Single endpoint call per refresh (no N+1).
- 30s polling chain via `setTimeout` (not interval), so a long fetch
  pauses the next tick instead of stacking.
- `AbortController` cancels in-flight fetches when `kind` changes.
- Unmount cleans up: aborts pending request, clears poll timer,
  removes retry-pending listener.
- Filter + group computations are `useMemo`-cached.
- The page renders even if backend is offline — error banner appears,
  buttons stay disabled until next successful fetch.

## States covered

- **Loading** — &ldquo;Loading connections...&rdquo; placeholder, only when no rows yet.
- **Empty** — instructional copy directing to `/connections` legacy
  flows or the V2 import endpoint.
- **Error** — banner with backend error message, but the rest of the
  UI stays usable.
- **Backend offline** — `useErrorStore` (api.ts interceptor) records
  the failure; banner shows the message; existing rows remain on screen.

## Untouched

Per founder spec, this PR did NOT redesign:

- Main Brain tab (Phase 5 PR 2)
- Plugins / Catalog tab
- MCP Servers tab
- Any unrelated pages

The V2 panel is the new default tab so it's first thing the operator
sees, but the three legacy tabs are still one click away.

## Tests

- Frontend `tsc --noEmit`: CLEAN.
- Backend Phase 4b PR 1 + PR 2 + PR 3 + runtime adapter suite: 113/113 PASS.

A manual smoke checklist is in `docs/PHASE_5_CONNECTIONS_FRONTEND_REPORT.md`
(this file). Live-browser smoke deferred to operator since dev server
isn't running in autonomous mode.

## Manual smoke checklist (founder)

1. `cd D:\Ideas\Daena\backend && .venv/Scripts/uvicorn app.main:app --reload --port 8000`
2. `cd D:\Ideas\Daena\frontend && npm run dev`
3. Navigate to `/connections` → "All Connections (V2)" tab is default.
4. Banner visible: amber if `USE_CONNECTION_REGISTRY_V2=false`, emerald otherwise.
5. With flag off: import a legacy connector via the existing Plugins tab,
   confirm no V2 row appears in the V2 panel.
6. With flag on: import a legacy connector, refresh V2 panel,
   confirm a row appears with `imported=true` and `reachable=false` →
   label `failed`, status pill rose-tinted.
7. Click "Probe" on a CLI runtime row that has a real binary installed:
   the probe should run; if auth is missing the pill flips to
   `needs_auth` (orange); if all dims pass the pill flips to `healthy`
   (emerald) and `callable_at` populates in the drawer.
8. Click row name → drawer opens with full truth ladder + failure
   reasons.
9. Disable / Enable buttons toggle the row state; Archive requires
   "Click again to confirm" within 3 seconds.

## Production blockers (unchanged)

- `USE_CONNECTION_REGISTRY_V2` still defaults to False
- Legacy `ConnectionsPage` tabs still rendered (intentional during soak)
- Old MCP Servers / Plugins tabs not yet rewritten on V2 truth (out of scope)

## Risks / limits

- The V2 panel queries `/connections/v2/reconciliation/status` to read
  the feature flag. That endpoint is FOUNDER+; non-FOUNDER users will
  silently see the panel render in &ldquo;assume OFF&rdquo; mode (amber banner).
  This is the safe default but worth noting.
- The slug derivation (`name-userIdPrefix8`) is stable but human-ugly
  (`testapikey-3c5a8b1d`). For Phase 5 PR 2 we'll consider exposing
  `display_name` more prominently.
- The legacy 3 tabs (`MainBrainPanel`, `PluginsCatalogBrowser`,
  `McpServersPanel`) still display old data. Phase 5 PR 2 unifies the
  Main Brain tab onto V2 truth; the other two stay as-is for now.

## Commit

`phase5: rebuild connections frontend on registry v2 truth`
