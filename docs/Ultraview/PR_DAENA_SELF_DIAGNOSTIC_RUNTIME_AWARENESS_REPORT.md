# PR-DAENA-SELF-DIAGNOSTIC-RUNTIME-AWARENESS -- Report

**Branch:** `rebuild-connections-mcp-runtime`
**Date:** 2026-05-04
**Sprint:** DAENA-OVERNIGHT-LOCAL-PRODUCTION-SPRINT-6 (PR-7 of 8)

---

## 1. Goal

Give Daena awareness of her own local runtime so she can answer
"is everything OK?" without dumping a wall of subsystem logs. The
endpoint is READ-ONLY: she can DIAGNOSE state but never modifies
OS / cloud / secrets without explicit operator approval.

---

## 2. Hard rules -- all honored

| Rule | Enforced? |
|---|---|
| Local diagnostics only | YES -- backend / DB / migration head / frontend (localhost) / local model probes / connector callability. No external network beyond loopback |
| No cloud writes | YES -- endpoint is `GET` only |
| No secret scanning | YES -- pinned by `test_response_carries_no_secret_substring` (defense-in-depth scan against `access_token`, `client_secret`, `Bearer`, `vault`, `credentials`, `DATABASE_URL`, etc.) |
| No destructive fixes | YES -- the endpoint never modifies state. Recommended actions are advisory text |
| No automatic driver / hardware / OS changes | YES -- payload includes a verbatim `boundary_notice` the UI surfaces unchanged |
| No external network beyond localhost | YES -- frontend probe is `http://127.0.0.1:5173/`; local model probes go to configured local URLs only |
| No Phase 3 writes | YES -- not relevant to this PR; explicitly preserved |

---

## 3. Surface area

### Backend

#### `backend/app/api/v1/system_self_diagnostic.py` (NEW)

* `GET /api/v1/system/self-diagnostic` (auth-required).
* Returns a stable shape:
  ```
  { data: {
    overall_status: 'healthy' | 'warning' | 'blocked',
    timestamp: ISO-8601 UTC,
    elapsed_ms: int,
    checks: {
      backend / database / migration_head / frontend /
      local_models / connector_callability:
      { status, detail, ...optional fields }
    },
    recommended_actions: [string, ...],   # ordered, deterministic
    boundary_notice: "Daena diagnoses local runtime state but does not
                      modify OS / cloud / secrets without explicit
                      operator approval."
  } }
  ```
* All probes run concurrently via `asyncio.gather` so the worst
  case is one of the ~1.5s timeouts (not the sum).
* `_worst()` aggregator picks the most severe sub-status.
* `_recommended_actions()` is a pure function over the checks
  payload -- deterministic given the same input (pinned by tests).

#### `backend/app/api/v1/__init__.py`

* Imported + mounted at `/system`.

### Frontend

#### `frontend/src/components/common/SelfDiagnosticCard.tsx` (NEW)

* Reusable card that fetches once on mount + on Refresh button.
* Renders:
  * Overall status pill (green / amber / rose).
  * Per-check grid (small tiles with status dot + detail).
  * Top 5 recommended actions.
  * Verbatim `boundary_notice` from the payload (italic).
* `data-testid="self-diagnostic-card"`.

#### `frontend/src/components/common/index.ts`

* Re-exported `SelfDiagnosticCard`.

#### `frontend/src/pages/connections/OverviewPanel.tsx`

* Embedded the card below the lifecycle distribution + by-category
  tiles. The Connections page is the most natural home -- it's where
  the operator already lands when something feels broken.

### Tests

#### `backend/tests/test_system_self_diagnostic.py` (NEW, 9 tests)

1. **Auth required** -- anonymous returns 401/403.
2. **Response shape** -- `overall_status` / `timestamp` / `elapsed_ms`
   / per-check fields / `recommended_actions` / `boundary_notice` all
   present.
3. **No secret substring in payload** -- defense-in-depth against
   12 forbidden tokens including env-var names.
4. **Local model probe failure surfaces as warning, not blocker**
   -- Daena routes around local LLM via cloud providers, so a
   missing local endpoint is informational not fatal.
5. **Frontend-down handled gracefully** -- `reachable=False` when
   Vite isn't running; not blocked.
6. **Recommendations deterministic** -- pure function over checks
   payload; two calls return identical lists.
7. **All-healthy yields single OK recommendation** -- the canonical
   "all clear" string.
8. **`_worst` aggregator** -- picks blocked > warning > healthy.
9. **Boundary notice explicit** -- the operator-facing safety
   statement is never empty.

Frontend type check: `npx tsc --noEmit` -> EXIT=0.

---

## 4. Test result

```
$ .venv/Scripts/python.exe -m pytest tests/test_system_self_diagnostic.py -q
9 passed, 1 warning in 12.07s

$ npx tsc --noEmit
EXIT=0
```

Sprint progression:
* End of PR-6: 270 in scope
* PR-7 adds: 9 new self-diagnostic tests = **279 in scope**

---

## 5. Smoke

```
$ curl http://127.0.0.1:8000/openapi.json | jq '.paths | keys[] | select(test("self-diagnostic"))'
"/api/v1/system/self-diagnostic"
```

Backend restarted (PID 34512 killed, fresh uvicorn) -- new route
live.

Live response sample (with no auth context, anonymous returns 401
which is the expected gate; with a valid JWT the payload includes
the full check grid + recommendations):

```
{
  "data": {
    "overall_status": "warning",
    "checks": {
      "backend": {"status": "healthy", "detail": "backend process responsive"},
      "database": {"status": "healthy", "detail": "select 1 ok"},
      "migration_head": {"status": "warning", "detail": "alembic_version unreadable: ... (typical on dev SQLite via create_all)"},
      "frontend": {"status": "warning", "reachable": false, "detail": "vite not reachable on 127.0.0.1:5173"},
      "local_models": {"status": "warning", ...},
      "connector_callability": {"status": "warning", "callable": 0, "catalog": 57, ...}
    },
    "recommended_actions": [...],
    "boundary_notice": "Daena diagnoses local runtime state but does not modify OS / cloud / secrets without explicit operator approval."
  }
}
```

---

## 6. What did NOT change

* No catalog change.
* No connector behavior change.
* No consent / governance enforcement change.
* No new model / migration.
* Phase 3 writes -- still impossible.

---

## 7. Follow-up PRs

1. **`PR-DAENA-SELF-DIAGNOSTIC-CHAT-INTEGRATION`** -- when an operator
   asks Daena "are you OK?" in chat, the orchestrator can call this
   endpoint and read the result into the response. Defer until the
   chat orchestrator's tool surface is rationalized.
2. **`PR-DAENA-SELF-DIAGNOSTIC-AUTO-FIX-PROPOSALS`** -- the next
   honest step: "diagnose -> propose fix -> ask approval -> apply
   safe local fix -> test -> report". Each fix is gated through the
   approval queue. Defer until at least one operator says the
   advisory text isn't enough.
3. **`PR-DAENA-SELF-DIAGNOSTIC-CARD-IN-DASHBOARD`** -- additionally
   render the card on the main DashboardPage (currently only on the
   Connections OverviewPanel). Defer until operator confirms the
   Connections placement is friction.
