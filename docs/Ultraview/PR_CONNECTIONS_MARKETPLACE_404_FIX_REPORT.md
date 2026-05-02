# PR-CONNECTIONS-MARKETPLACE-404-FIX Report

**Date:** 2026-05-02
**Branch:** `rebuild-connections-mcp-runtime`
**Author:** Claude Code (Opus 4.7) under founder direction
**Builds on:** `PR_CONNECTIONS_SIMPLE_PLUGIN_UX_REPORT.md` (commit `5fee79a`)
**Founder report:** `/connections` showed `Backend error: Not Found` and 0 plugins.

> **Thesis.** The new Plugins tab was correct in source (commit
> `5fee79a` registered `GET /catalog`, `GET /marketplace/cards`,
> `GET /marketplace/install-plan/{entry_id}`). The live failure had
> two layered causes:
>
> 1. **Stale backend process** -- a Windows `python.exe` running
>    `run.py` started 2026-05-01 17:05 (uptime 25h 23m) was bound to
>    127.0.0.1:8000. It predated commits `4b52d3f` AND `5fee79a` and
>    therefore had NEITHER `/discovery/refresh` NOR any of the new
>    `/catalog` / `/marketplace/*` endpoints. Every request to those
>    paths returned 404 / `Not Found`.
> 2. **Route ordering bug** -- once a fresh backend was started, the
>    test client surfaced a second hidden bug: `/catalog` and
>    `/marketplace/cards` were declared AFTER the dynamic
>    `GET /{connection_id}` route. FastAPI matches routes in
>    declaration order; with the dynamic route first, a GET to
>    `/catalog` was being parsed as `connection_id="catalog"`, which
>    failed UUID validation with HTTP 422 (not 404, but still the
>    operator-facing error). This was masked in production by the
>    stale backend never reaching the new route.
>
> Both bugs are fixed. Backend restarted. All 3 marketplace endpoints
> verified live with real data (51 catalog entries, 14 categories,
> 51 marketplace cards, 5-step install plan). 148 / 148 V2 tests pass
> including 5 new live HTTP smoke tests + 1 route-registration test
> that pin both bugs from re-emerging.

---

## 0. Hard rules honored

| Rule | Status |
|---|---|
| 1. No production deploy | Yes |
| 2. No `USE_CONNECTION_REGISTRY_V2=true` flip | Yes |
| 3. No `vault --apply` | Yes |
| 4. No file deletions | Yes |
| 5. No secrets printed or committed | Yes -- live JWT used for smoke was generated from the test fixture (FOUNDER role, `22222222-...`) and discarded after the curl loop |
| 6. No external scans | Yes |
| 7. No external messages | Yes |
| 8. No new tabs added | Yes -- Brain / Plugins / Advanced unchanged |
| 9. Brain / Plugins / Advanced simplification preserved | Yes |
| 10. No new features | Yes -- this PR is a 404 + route-ordering fix only |

Project Rule 12 (no em-dashes): **0** added across all modified files.

---

## 1. Root cause

### 1.1 What the operator saw

`/connections` -> Plugins tab -> "Backend error: Not Found" toast and an empty grid.

### 1.2 Diagnosis sequence

1. **Backend identity check.** Two listeners on `127.0.0.1:8000`:
   - PID 23356: Windows `python.exe` running `run.py`, started
     2026-05-01 17:05 (uptime 25h 23m at probe time).
   - PID 33060: `wslrelay.exe` (the WSL2 port relay).

   The Windows process was authoritative -- WSL relay only forwards.
   WSL backend (PID 30) had failed to bind because the port was held.

2. **Source-code route check.** `app.routes` enumerated against the
   in-memory `create_app()` showed all 3 marketplace routes registered
   correctly:
   ```
   GET  /api/v1/connections/v2/catalog
   GET  /api/v1/connections/v2/marketplace/cards
   GET  /api/v1/connections/v2/marketplace/install-plan/{entry_id}
   ```

3. **Live OpenAPI check.** `GET /openapi.json` against the running
   backend showed those 3 routes were ABSENT, AND `discovery/refresh`
   from commit `4b52d3f` was also absent. Confirmed: stale process.

4. **Frontend path check.** `frontend/src/hooks/useMarketplace.ts`
   correctly calls `/connections/v2/marketplace/cards` against the
   axios `API_BASE = '/api/v1'` -> resolved URL
   `/api/v1/connections/v2/marketplace/cards`. Path was correct.

5. **Restart.** Killed PIDs 23356 + 23948 (the multiprocessing-fork
   child holding the actual socket) and restarted. Live OpenAPI now
   showed all routes.

6. **Hidden second bug surfaced.** Wrote a TestClient smoke that
   asserted `/catalog` returns 200 -- it returned **422
   Unprocessable Entity** with a UUID parse error, not 200. The
   dynamic route `GET /{connection_id}` declared at line 140 was
   shadowing the static `/catalog` declared at line 355. Per
   FastAPI / Starlette route-resolution rules, a single-segment path
   `/catalog` matches the wildcard `{connection_id}` and tries to
   parse the literal string `catalog` as a UUID.

7. **Fix.** Moved the marketplace block (`/catalog`,
   `/marketplace/cards`, `/marketplace/install-plan/{entry_id}`)
   ABOVE the `/{connection_id}` declaration. Multi-segment routes
   (`/reconciliation/status`, `/discovery/refresh`,
   `/marketplace/cards`) had been working because Starlette's path
   matcher correctly distinguishes `/{x}` (1 segment) from `/x/y`
   (2 segments) -- the bug was specific to single-segment static
   routes declared after a single-segment dynamic route.

### 1.3 Exact endpoint the frontend called

`GET /api/v1/connections/v2/marketplace/cards`

Resolved by:
- `frontend/src/lib/api.ts` `API_BASE = '/api/v1'`
- `frontend/src/hooks/useMarketplace.ts:215` `api.get('/connections/v2/marketplace/cards')`
- `frontend/src/pages/connections/PluginsPanel.tsx` invokes `useMarketplaceCards()`

### 1.4 Why "Not Found" and not "422 Validation Error"

The stale backend simply did not have `/catalog` or `/marketplace/*`
in its OpenAPI -- so FastAPI's catch-all matcher returned 404 for
the unknown path. After the restart and BEFORE the route-ordering
fix, the same path would have returned 422. The founder saw the 404
because of the stale-process layer.

---

## 2. Files changed

| File | Status | Purpose |
|---|---|---|
| `backend/app/api/v1/connections_v2.py` | M | Move `/catalog`, `/marketplace/cards`, `/marketplace/install-plan/{entry_id}` decorators ABOVE `/{connection_id}`. Removed the now-duplicate marketplace block lower in the file. Added a header comment explaining the ordering invariant for future contributors. |
| `backend/tests/test_connection_v2_marketplace.py` | M | +6 new tests (1 route-registration + 5 live HTTP smoke covering 200 OK + correct shape + 404 on unknown id + 401 without auth). 39 -> 45 tests. |
| `docs/Ultraview/PR_CONNECTIONS_MARKETPLACE_404_FIX_REPORT.md` | A | This report. |

No frontend changes required. No service-code changes required. The
catalog + service modules are unchanged.

---

## 3. Live verification

### 3.1 OpenAPI

```text
$ curl -s http://127.0.0.1:8000/openapi.json | jq '.paths | keys[] | select(. | contains("connections/v2"))' | sort
"/api/v1/connections/v2"
"/api/v1/connections/v2/catalog"
"/api/v1/connections/v2/discovery/refresh"
"/api/v1/connections/v2/marketplace/cards"
"/api/v1/connections/v2/marketplace/install-plan/{entry_id}"
"/api/v1/connections/v2/reconciliation/run"
"/api/v1/connections/v2/reconciliation/seed-providers"
"/api/v1/connections/v2/reconciliation/status"
"/api/v1/connections/v2/{connection_id}"
"/api/v1/connections/v2/{connection_id}/disable"
"/api/v1/connections/v2/{connection_id}/enable"
"/api/v1/connections/v2/{connection_id}/probe"
"/api/v1/connections/v2/{connection_id}/test"
```

### 3.2 Endpoint smoke (with auth)

```text
$ curl -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/api/v1/connections/v2/catalog
  -> success=True, entries=51, categories=14

$ curl -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/api/v1/connections/v2/marketplace/cards
  -> success=True, cards=51, first_lifecycle=available, first_action=setup_guide

$ curl -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/api/v1/connections/v2/marketplace/install-plan/mcp-github
  -> success=True, entry_id=mcp-github, executable=False, steps=5

$ curl -X POST -H "Authorization: Bearer $JWT" http://127.0.0.1:8000/api/v1/connections/v2/discovery/refresh
  -> success=True, total_created=0, total_skipped_existing=0, mcp_paths_searched=9
```

All four endpoints respond 200 with valid shapes. The 9 MCP paths
searched matches the founder's earlier observation that no MCP
configs exist on disk yet -- the empty-state UI will explain this
honestly via the discovery toast.

### 3.3 Honesty check on cards (project Rule 17)

The first card (sorted by ID, alphabetical) was `app-canva` with
`lifecycle="available"` and `primary_action="setup_guide"`. No V2
row exists for this tenant yet, so the card surfaces as available
with a Setup-guide CTA. **NO card in the smoke was marked
"connected" or "callable" -- the truth ladder honestly reflects the
empty tenant state.**

---

## 4. Tests run

### 4.1 Backend marketplace tests (45 / 45 PASS)

```text
$ pytest tests/test_connection_v2_marketplace.py
  TestCatalogShape                    6/6   PASS
  TestCatalogCoverage                 5+14/19 PASS  (parametrized over categories)
  TestNoSecretLeak                    2/2   PASS
  TestInstallPlans                    5/5   PASS
  TestMarketplaceServiceOverlay       5/5   PASS
  TestListHelpers                     2/2   PASS
  TestMarketplaceRouteRegistration    1/1   PASS  (NEW: pins routes registered)
  TestMarketplaceLiveSmoke            5/5   PASS  (NEW: 200 OK + shape + 404 + 401)
  ----------------------------------------
  total                              45/45  PASS in 2.85s
```

### 4.2 Full V2 regression (148 / 148 PASS)

```text
$ pytest tests/test_connection_v2*.py tests/test_phase7_*.py
  tests/test_connection_v2.py                       22/22 PASS
  tests/test_connection_v2_probe_truth.py            8/8  PASS
  tests/test_connection_v2_reconciliation.py        12/12 PASS
  tests/test_connection_v2_seed_import.py           16/16 PASS
  tests/test_connection_v2_ux_rescue.py             14/14 PASS
  tests/test_connection_v2_marketplace.py           45/45 PASS  (+6 since prior PR)
  tests/test_phase7_lifespan_seed.py                 3/3  PASS
  tests/test_phase7_provider_probes.py              28/28 PASS
  ----------------------------------------------------------
  combined                                         148/148 PASS in 4.13s
```

### 4.3 Frontend typecheck

```text
$ cd frontend && npx tsc --noEmit
EXIT=0
```

No frontend code changes -- the typecheck is a regression guard.

---

## 5. New tests pinning the regression

### 5.1 `TestMarketplaceRouteRegistration` (1 test)

Walks `app.routes` from `create_app()` and asserts each of the 3
required marketplace routes (with their HTTP methods + paths) IS
registered. If a future contributor:

* removes the `connections_v2` import from `api/v1/__init__.py`,
* removes one of the `@router.get(...)` decorators,
* renames the route prefix at mount time,

...this test fails immediately at unit-test time, not at the
operator's "Not Found" toast.

### 5.2 `TestMarketplaceLiveSmoke` (5 tests)

* `test_catalog_endpoint_returns_entries` -- 200 + `entries=len(CATALOG)`. **This is the test that surfaced the route-ordering bug.**
* `test_marketplace_cards_returns_one_per_entry` -- 200 + `cards=len(CATALOG)`, every card `lifecycle in ("available", "needs_setup")` for the empty-tenant case.
* `test_install_plan_returns_steps_for_known_entry` -- 200 + `entry_id="mcp-github"`, `executable=False`, `steps>0`.
* `test_install_plan_returns_404_for_unknown_entry` -- 404 + `detail="catalog_entry_not_found"`. Pins that the route does NOT silently return an empty plan for an unknown id.
* `test_marketplace_routes_require_auth` -- 401 without auth header. Pins that the auth dependency stays in place.

---

## 6. Operational notes

### 6.1 Backend restart procedure

`run.py` uses uvicorn with multiprocessing. Killing the parent PID
alone leaves the child socket open. The reliable kill is:

```powershell
$pid = (Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess
Stop-Process -Id $pid -Force
# Then check Get-CimInstance Win32_Process for any remaining
# multiprocessing-fork children and stop those too.
```

After the kill, port 8000 is free and `python run.py` from
`backend/` (or the standard `start-daena.bat`) brings up the fresh
backend. The startup writes `.daena-port` so the launcher and tests
can read the actual port (auto-fallback if 8000 is busy).

### 6.2 Why two backends were running

The Windows `python run.py` from 2026-05-01 was a developer
foreground launch that was never stopped. When `start-daena.bat` ran
later in WSL2, the WSL backend tried to bind 0.0.0.0:8000 inside its
namespace, but `wslrelay.exe` couldn't forward Windows-side because
the Windows process held the loopback. Net result: WSL backend
failed silently, Windows backend served stale code for 25h.

### 6.3 Recommended hygiene

* Add a `pre-commit` or `start-daena.bat` early-exit if port 8000 is
  already held by a different process. (Out of scope for this PR --
  noted as a follow-up.)
* The new route-registration test catches future drift; the live
  smoke catches future ordering bugs in the connections_v2 router.

---

## 7. Remaining blockers

None for the immediate "Backend error: Not Found" symptom. After the
backend restart and route-ordering fix, the founder's `/connections`
page should render the Plugins tab with 51 cards immediately, even
before any discovery has run, because the catalog ships in source.

The same blockers from `PR_CONNECTIONS_SIMPLE_PLUGIN_UX_REPORT.md`
remain (PR-CONN-MCP-PROBE, PR-CONN-CLI-PROBE, PR-CONN-OAUTH-PROBE,
PR-CONN-MCP-INSTALL, etc.) -- none of which are blockers for the
404 fix.

---

## 8. Browser smoke (operator step)

Founder can verify by:

1. Hard-refresh `http://localhost:5173/connections` (or the
   configured frontend dev URL).
2. Plugins tab should render the 51 cards immediately (no
   "Backend error: Not Found" toast).
3. Brain tab should still work (unchanged).
4. Advanced tab should still contain the registry / debug sub-sections.
5. Click `Discover installed tools` in the header -- toast should
   show per-source counts and the "No installed MCP configs found
   (searched 9 paths)" hint.
6. Open a card -> Setup guide drawer should render the curated
   install steps without auto-executing anything.

---

## 9. Commit message

```
fix: wire connections marketplace routes
```

Single commit on branch `rebuild-connections-mcp-runtime`.

---

**Stopping here as requested. Awaiting next founder direction.**
