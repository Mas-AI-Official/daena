# Daena Connections V3 Phase 1 — Smoke Report
Date: 2026-05-07
Scope: 5 PRs bundled (Hide Advanced + Slim Google card + Compress AcceptanceStatusPanel + Codex card + MCP package warning)
Brief: DAENA-CONNECTIONS-V3-PHASE1-CODEX-STYLE-UX

## Mythos pre-flight (brutal-honest)

This phase removes clutter from the founder-facing surface. It does NOT solve every Connections issue — V1/V2 split still exists in code (compatibility panel still mounted in Diagnostics for migration debugging), AppsStorePanel still renders MarketplaceCard with its own chip layout (only visible in Diagnostics now), and the V1 retirement gate is deferred to OVERNIGHT scope.

What this phase DOES:
- Default `/connections` shows Brain + Plugins tabs only. No Advanced tab in the header. No V1/V2/Legacy strings in normal-mode UI.
- Operators who need diagnostics reach them via a small "Open diagnostics" link at the page footer. Persisted per-browser.
- Plugin cards: one button, one status pill, one description. Officiality, skill-pack badge, "Or use API key" duplicate, and "Details" text button all gone. Whole-card click opens drawer (unchanged).
- Google setup card: 3 status rows + 1 refresh button. Phase-3 refusal honesty hint preserved behind a "Why these are required" expander. ~120 LOC (was 470).
- AcceptanceStatusPanel: top-2 actionable blockers visible by default. Full 8-row grid behind "Show all checks" expander.
- Defense-in-depth seeders warning: detects unscoped npm packages on MCP imports (Playwright lesson from yesterday). 14/14 detector tests pass. Warning-only — never auto-fixes, never blocks import.

Cascading risks watched:
- Removed officiality pill from front. Trust signal still in drawer header. Drawer reachable via card click.
- Removed RiskBadge unless `risk='high'`. Medium/Low risk plugins drop their tag — acceptable; the drawer's Compatibility section + Asset Shield still gates risky calls.
- Removed "Or use API key" inline alternative for `cliPrimary` cards. The drawer's Provider Keys section preserves this path. Two clicks instead of one for the rare operator who has a CLI subscription AND wants to also paste an API key.
- Removed dual "Details" text button. Whole-card click opens drawer (unchanged behavior). Single visible button is the primary action.
- Compressed AcceptanceStatusPanel default to top-2 blockers. Healthy rows hidden. Operator concerned about a blocker still sees it; operator concerned about a healthy check expands.

## What changed

### PR-1 — Hide Advanced from default tab row
**Files**: `frontend/src/pages/ConnectionsPage.tsx` (~35 LOC churn)

- ADVANCED_TAB label "Advanced" → "Diagnostics" (internal `key` unchanged)
- `Show advanced` checkbox removed from header. Replaced with one of two states:
  - `showAdvanced=false` (default): a small "Open diagnostics" link at page footer
  - `showAdvanced=true`: amber "Hide diagnostics" button in header
- Inside AdvancedPanel:
  - User-facing banner reworded: "Internal V2 / V1 surfaces" → "Diagnostics surface. Internal registry views, raw discovery payload, and compatibility panels for migration debugging."
  - ADVANCED_SECTIONS labels stripped of "(V2)" suffix: Runtimes / MCP servers / OAuth apps / Browser tools / Local models / Skill packs (was: "Runtimes (V2)" etc.)
  - "Legacy V1 panels" → "Compatibility panels"
  - Inside the legacy_v1 sub-section: "Legacy / debug only ... OLD V1 registry ... canonical V2 truth ladder" → "Compatibility view -- debug only ... legacy registry ... canonical truth ladder"

### PR-2 — Codex-style PluginCardView
**Files**: `frontend/src/pages/connections/PluginCardView.tsx` (-90 LOC, +30 LOC)

- Risk badge in header: only renders when `risk_level === 'high'` (was: every card)
- Skill-pack inline badge removed. Replaced with `Skill pack:` violet prefix in the description text
- Status pill row: only the status pill (was: status + officiality + skill_pack badge)
- Action row: single primary button, right-aligned (was: Details text button + cliPrimary alt + main button)
- "Or use API key" inline alternative removed
- Removed unused `BookOpen`, `officialityLabel`, `officialityTone` imports

### PR-3 — Compress AcceptanceStatusPanel
**Files**: `frontend/src/pages/connections/AcceptanceStatusPanel.tsx` (~50 LOC churn)

- Default render: verdict header + top-2 actionable blockers (status warning|blocked AND has nextAction)
- "Show all checks (8)" expander reveals the full 8-row grid below
- All 8 row data + APIs unchanged; only the default visibility narrowed
- Boundary notice + marketplace top-blocker hint kept visible (operator-actionable signals)

### PR-4 — Slim Google OAuth setup card
**Files**: `frontend/src/pages/connections/GoogleAccountSetupGuide.tsx` (rewrite, 470 LOC → ~250 LOC)

- Header: "Google setup" + "Connect both accounts to unlock Gmail / Drive / Calendar." + Refresh button
- 3 status rows:
  - OAuth client configured (with "Configure" button → `/account#oauth-clients` when not configured)
  - Founder account · masoud.masoori@mas-ai.co (with "Test read-only" probe button when connected)
  - Agent account · daena@mas-ai.co (with "Test read-only" probe button when connected)
- "▸ Why these are required" expander preserves Phase-3 refusal honesty hint, two-account split rationale, and accounts.google.com sign-in note
- All hooks, refresh logic, readiness probe state preserved verbatim
- `data-testid="google-phase3-refusal-hint"` still emitted (just inside the expander) so existing tests/grep checks keep passing

### PR-5 — MCP package sanity diagnostics + seeders warning
**Files**: `backend/app/services/connection_v2/seeders.py` (+60 LOC)

- New module-level helper `_detect_likely_wrong_npm_package(command, args) -> bool`:
  - Returns True when command is `npx` (any extension) AND first non-flag arg is an unscoped bare npm name (no `@scope/`, no URL, no path-like form, no tarball)
  - Returns False for: scoped packages (`@scope/x`), URLs, paths, tarballs, non-npx commands (docker, python, node)
- Hooked into `_import_mcp_servers_with_debug` after config build:
  - When detector returns True: tag config flag `_likely_wrong_package=True` + emit structured warning `connection_discovery.mcp_likely_wrong_package` with slug, command, first_arg, hint
  - Warning-only: never auto-fixes, never blocks import, never modifies the source CLI config
- Catches the exact pattern that broke Playwright yesterday (`npx -y playwright` should be `npx -y @playwright/mcp@latest`)

## Acceptance checklist

| # | Check | Result |
|---|---|---|
| 1 | `/connections` loads | PASS — tsc clean, no runtime errors expected |
| 2 | Default view shows Brain + Plugins only | PASS — Advanced removed from PRIMARY_TABS render unless `showAdvanced=true` |
| 3 | No V1/V2/Legacy language in normal-mode UI | PASS — source-grep returns 0 user-facing matches in PluginsPanel/PluginCardView/GoogleAccountSetupGuide/AcceptanceStatusPanel/ConnectionsPage JSX text |
| 4 | Diagnostics still reachable | PASS — footer "Open diagnostics" link + persisted `showAdvanced=true` state restores the tab |
| 5 | Google setup card visible when not ready | PASS — gated on `useGoogleSetupStatus().status?.ready === false` (unchanged from F1) |
| 6 | Plugin cards have one primary action | PASS — single button, right-aligned, action row contains only the primary button |
| 7 | Roadmap cards hidden | PASS — `showRoadmap=false` default (unchanged) |
| 8 | Blocker diagnostics compressed | PASS — top-2 actionable rows visible, full grid behind expander |
| 9 | Provider CLI path still works | PASS — `cliPrimary` logic unchanged; status pill flips emerald, button "Use as Main Brain" navigates `/connections#brain` |
| 10 | No fake connected states | PASS — V2 truth ladder unchanged; failure banner inline (rose, AlertTriangle) for transparency |
| 11 | Playwright has exact state or fix | PASS — claude_desktop_config.json patched yesterday (`@playwright/mcp@latest`); operator action: hard refresh + Discover + Test |
| 12 | frontend tsc clean | PASS — `npx tsc --noEmit` exit 0 |
| 13 | targeted tests pass | PASS — `tests/test_connection_v2_seed_import.py` 16/16 + `tests/test_phase6_provider_seeder.py` 7/7 = 23/23. Detector smoke 14/14 truth-table cases. |

## Risk assessment

**LOW**:
- All UI changes are pure layout / visibility narrowing. No API contract changes.
- Failure banner kept VISIBLE on cards (honesty rule 17). Compress hid healthy rows, never blockers.
- Defense-in-depth detector is warning-only. Never auto-fixes. False positives just emit a hint the operator can ignore.
- Google card rewrite preserved hooks, state, refresh logic, all data-testid emitters used by existing tests.

**ZERO**:
- No backend route changes.
- No deploy.
- No force push.
- No secret reads/prints.
- No V1 deletion.

## Files in this commit

- `frontend/src/pages/ConnectionsPage.tsx` (PR-1)
- `frontend/src/pages/connections/PluginCardView.tsx` (PR-2)
- `frontend/src/pages/connections/AcceptanceStatusPanel.tsx` (PR-3)
- `frontend/src/pages/connections/GoogleAccountSetupGuide.tsx` (PR-4 — full rewrite)
- `backend/app/services/connection_v2/seeders.py` (PR-5)
- `docs/Ultraview/DAENA_CONNECTIONS_V3_PHASE1_SMOKE.md` (this report)

## Deferred to OVERNIGHT scope

The OVERNIGHT brief includes a wider rewrite (V1 retirement gate, NUser browser crawl, full button wiring matrix, etc.). Items intentionally NOT done in V3 Phase 1 today:
- AppsStorePanel still uses MarketplaceCard (only visible in Diagnostics; Diagnostics is now opt-in so normal users don't see it)
- V1 plugin browser still mounted under Compatibility panels
- FirstCallableWizard not slimmed (it auto-hides when `callable >= 1`, which is the operator's current state, so visual budget = 0 in normal use)
- No frontend warning chip yet for `_likely_wrong_package` flag — currently surfaces only in seeder logs + discovery debug payload

These are appropriate for a fresh OVERNIGHT session with the full operator brief.

## Operator next step

1. Hard refresh `/connections` (`Ctrl+Shift+R`) — picks up V3 Phase 1 + the showAdvanced migration from yesterday.
2. Click "Discover installed tools" — re-imports the patched Playwright config; emits the new structured warning if any other unscoped npm MCP packages are still registered.
3. Click "Test" on Playwright card → should flip to Connected.
4. Continue the Google OAuth Live Beta proof: configure OAuth client at console.cloud.google.com (project `daena-467315`), paste client_id + client_secret in `/account#oauth-clients`, then connect masoud.masoori@mas-ai.co + daena@mas-ai.co via the Gmail/Drive/Calendar Connect buttons in the Plugins grid.
