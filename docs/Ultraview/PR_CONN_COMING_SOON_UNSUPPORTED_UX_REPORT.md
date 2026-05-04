# PR-CONN-COMING-SOON-AND-UNSUPPORTED-UX-CLEANUP -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Date:** 2026-05-04
**Sprint:** DAENA-OVERNIGHT-LOCAL-PRODUCTION-SPRINT-6 (PR-3 of 8)

---

## 1. Goal

End the "Browserbase looks broken" / "this card looks like a failed
install but I never installed it" perception. Coming-soon catalog
entries (Browserbase + a handful of others) now render with an
intentional, neutral, slate styling and the operator sees explicit
copy that says "Daena cannot install or probe this connector yet."

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| Coming-soon = neutral, not red | YES -- new `coming_soon` PluginStatus uses slate tone (matches `not_supported_on_os` family); old amber pill removed |
| Verify locally disabled if unsupported | YES -- `deriveAction` keeps `setup_guide` for coming-soon (so the drawer with vendor info stays reachable) but probe / install / connect actions are not surfaced |
| Honest copy | YES -- "Roadmap parity only. Daena cannot install or probe this connector yet -- catalog metadata only." |
| Browserbase no longer red | YES -- backend classifier now beats failure_reason for coming-soon entries; even a stale `unsupported_tool` recorded on a V2 row classifies as `coming_soon`, not `probe_failed` |
| No primary tab change | YES -- styling + copy + classifier only |

---

## 3. Surface area

### Frontend

#### `frontend/src/pages/connections/pluginCard.ts`

* New `PluginStatus` variant: `'coming_soon'`.
* `STATUS_LABELS.coming_soon = 'Coming soon'`.
* `PLUGIN_STATUS_TONE.coming_soon` = neutral slate (subtle border, no
  amber/rose noise).
* `deriveStatus`: `entry.install_method === 'coming-soon'` AND no V2
  row -> `coming_soon` (beats `available` / `failed`).
* `deriveAction`: for `coming_soon` -> `setup_guide` (still useful;
  the drawer surfaces vendor signup link + env var names) but the
  card's primary action stays low-key.
* `skillReadiness`: maps `coming_soon` -> `locked_unsupported`
  family.
* `skillReadinessReason`: dedicated copy for the `coming_soon`
  branch ("on the roadmap... metadata only") instead of the generic
  "not supported on this OS" line.

#### `frontend/src/pages/connections/PluginCardView.tsx`

* Removed the redundant amber "coming soon" pill (the new slate
  status pill carries the signal honestly).
* Added a slate inline notice block for `status === 'coming_soon'`:
  "Roadmap parity only. Daena cannot install or probe this connector
  yet -- catalog metadata only."
* `data-testid="plugin-card-coming-soon-notice"` for downstream
  Playwright/Chrome-DevTools smoke.

#### `frontend/src/pages/connections/MarketplaceCard.tsx`

* "coming soon" pill restyled from amber to slate with explanatory
  tooltip.

### Backend

#### `backend/app/services/connection_v2/marketplace_service.py`

* `_classify_card_blocker` reordered + amended: coming-soon catalog
  entries always return `BLOCKER_REASON_COMING_SOON` regardless of
  lifecycle / V2 row state / stale failure_reason. Without this
  guard, Browserbase (whose `browser_probe` legitimately returns
  `unsupported_tool` and writes that to the V2 row) was classified
  as `probe_failed` and shown in the rose "Top blockers" tile from
  PR-2.

### Tests

#### `backend/tests/test_marketplace_coming_soon_classifier.py` (NEW, 5 tests)

1. Coming-soon + no V2 row -> coming_soon (existing behavior, pinned).
2. Coming-soon + manual import (V2 row exists) -> coming_soon (PR-3).
3. Coming-soon + failed lifecycle -> coming_soon (PR-3, the
   Browserbase fix).
4. Regression: non-coming-soon + failed -> probe_failed (existing
   semantics preserved).
5. Regression: non-coming-soon + configured -> needs_probe (existing
   semantics preserved).

Frontend type check: `npx tsc --noEmit` -> EXIT=0.

---

## 4. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_marketplace_coming_soon_classifier.py tests/test_marketplace_diagnostic.py -q
25 passed in 2.51s

$ npx tsc --noEmit
EXIT=0
```

Sprint progression:
* End of PR-2: 241 in scope
* PR-3 adds: 5 new coming-soon classifier tests = **246 in scope**

Note: PR-3's classifier reorder (coming-soon checked BEFORE the
generic `failed` map) does NOT affect any PR-2 test because the PR-2
synthetic cards use `install_method='npm'` for non-coming-soon paths
and only one explicit `coming-soon` test in PR-2 has no V2 row.
Behavior is unchanged for those.

---

## 5. What did NOT change

* Catalog itself (no entries added/removed/relabeled).
* `browser_probe.py` logic -- it still returns `unsupported_tool`
  honestly. We just classify the result correctly downstream.
* `_derive_lifecycle` -- the marketplace lifecycle ladder is
  unchanged. PR-3 only intercepts the BLOCKER classification + the
  frontend status mapping.
* No new endpoint added.
* Phase 3 writes -- still impossible.

---

## 6. Follow-up PRs

1. **`PR-CONN-COMING-SOON-WAITLIST`** (future): if an operator clicks
   the slate "Setup guide" CTA on a coming-soon card, capture intent
   + email so we can prioritize wiring the right connectors next.
   Defer until at least 3 distinct waitlist requests are observed.
2. **`PR-CONN-BROWSER-PROBE-SKIP-COMING-SOON`** (future): make
   `browser_probe.run()` early-return for coming-soon entries instead
   of writing the `unsupported_tool` failure_reason at all. Pure
   cosmetic cleanup; the classifier now masks the wart.
