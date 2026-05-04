# PR-CONN-CALLABILITY-DIAGNOSTIC-PANEL -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Date:** 2026-05-04
**Sprint:** DAENA-OVERNIGHT-LOCAL-PRODUCTION-SPRINT-6 (PR-2 of 8)

---

## 1. Goal

Address the operator pain point: "0 of 57 callable" makes Daena look
broken. The Overview already showed the count; it never explained
WHY the count was zero. This PR ships a backend-classified diagnostic
that aggregates concrete blocker reasons and surfaces them in a
collapsible Overview panel block.

The classification logic lives in the BACKEND (single source of
truth). The frontend renders what the backend hands it and never
fabricates blocker reasons.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| Honest counts only | YES -- diagnostic.totals.callable comes from the same lifecycle ladder as the Overview tile; no fabrication |
| No fake "callable" pills | YES -- per project Rule 17. The diagnostic is purely additive; nothing in this PR marks anything callable |
| Read-only metadata | YES -- endpoint returns counts + small examples (entry_id + display_name only). No config blob, no env values, no truth dim payloads |
| No new primary tab | YES -- new section lives inside the existing OverviewPanel, only when blocked > 0 |
| Friendly empty state | YES -- when nothing is callable, the BlockersBlock copy guides the operator to the top blocker first |

---

## 3. Surface area

### Backend

#### `backend/app/services/connection_v2/marketplace_service.py`

* Added stable taxonomy of 9 blocker reasons (`BLOCKER_REASON_*`
  constants) with operator-facing labels + next-action copy.
* Added `_classify_card_blocker(card)` pure classifier:
  * `callable` / `enabled` -> `None`
  * `archived` / `disabled` / `skill_pack` / `failed` -> direct map
  * `coming-soon` install_method without V2 row -> `coming_soon`
  * `api_provider` with `provider_key_present=False` -> `needs_api_key`
  * `oauth_app` without V2 row OR with `authenticated=False`
    -> `needs_oauth`
  * `configured` / `installed` / `reachable` -> `needs_probe`
  * `available` without V2 row -> `not_imported`
* Added `build_diagnostic_summary(cards)` aggregator that returns:
  ```
  { totals: {catalog, callable, configured, failed, skill_packs,
             coming_soon, available, blocked},
    top_blockers: [
      {reason, label, next_action, count, examples[<=3]}, ...
    ] }
  ```
* Added `MarketplaceService.diagnostic_summary()` thin wrapper for
  the API endpoint.

#### `backend/app/api/v1/connections_v2.py`

* New route: `GET /api/v1/connections/v2/marketplace/diagnostic`
* Auth-required.
* Returns `{success: true, data: <summary>}` from
  `diagnostic_summary()`. No write side, no body.

### Frontend

#### `frontend/src/hooks/useMarketplace.ts`

* Added `BlockerReason` union, `DiagnosticTotals`, `DiagnosticBlocker`,
  `DiagnosticSummary` types.
* Added `useMarketplaceDiagnostic()` hook -- single fetch on mount,
  `refresh()` for explicit re-poll. No polling because the
  classification only changes when V2 rows or settings change, both
  of which already trigger a card refresh.

#### `frontend/src/pages/connections/OverviewPanel.tsx`

* New `BlockersBlock` component shown below the headline tile when
  `blocked > 0` and at least one blocker is present.
* Renders top 5 blockers ranked by count desc.
* Each row: label, count badge, next-action copy, up to 3 example
  display names, plus an "Open ›" button when the blocker maps to a
  meaningful tab (`mcp` / `apps` / `runtimes`).
* Color-tone matrix per reason:
  * `not_imported` / `needs_probe` -> cyan
  * `needs_api_key` / `needs_oauth` -> amber
  * `probe_failed` -> rose
  * `coming_soon` / `disabled` / `archived` -> slate
  * `skill_pack` -> violet

### Tests

#### `backend/tests/test_marketplace_diagnostic.py` (NEW, 20 tests)

* **TestClassifier (12 tests)**: every lifecycle/kind combo -> the
  expected blocker reason (or None for callable/enabled).
* **TestAggregator (5 tests)**: empty cards yield zero totals;
  totals roll up correctly; top_blockers ranked by count desc;
  examples capped at 3 per blocker; payload carries no secret
  substring.
* **TestHTTPEndpoint (3 tests)**: endpoint requires auth; brand-new
  tenant returns catalog>0 + callable=0 + at least one blocker;
  payload carries no `access_token` / `refresh_token` / `Bearer` /
  `client_secret` / `vault` / `credentials` substring.

---

## 4. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_marketplace_diagnostic.py -q
20 passed in 2.74s

$ npx tsc --noEmit
EXIT=0
```

Sprint progression:
* End of Sprint-5: 221 in scope
* PR-2 adds: 20 new diagnostic tests = 241 in scope

---

## 5. Smoke

```
$ curl http://127.0.0.1:8000/openapi.json | jq '.paths | keys[] | select(test("diagnostic"))'
"/api/v1/connections/v2/marketplace/diagnostic"
```

Backend restarted (PID 8504 killed, fresh uvicorn) -- new route live.
Frontend tsc clean. The BlockersBlock will render on first Overview
load if any catalog entry is non-callable for the current tenant
(which is guaranteed for any fresh laptop install).

---

## 6. What did NOT change

* No catalog entries added/removed.
* No lifecycle ladder change.
* No probe / install / OAuth code change.
* No allowlist / consent / governance enforcement change.
* Phase 3 writes -- still impossible.

---

## 7. Follow-up PRs (not in this PR)

1. **`PR-CONN-DIAGNOSTIC-DRILLDOWN`** -- click an "Open ›" button and
   open the relevant tab pre-filtered to that blocker (e.g. show only
   `failed` cards on MCP tab). Defer until operator confirms the
   current "open the tab and look around" flow is friction.
2. **`PR-CONN-DIAGNOSTIC-IN-SELF-DIAGNOSTIC`** -- expose a slimmed-down
   `top_blockers` list from `/api/v1/system/self-diagnostic` (PR-7) so
   Daena can speak to "your top blocker is X (Y connectors)" in chat.
