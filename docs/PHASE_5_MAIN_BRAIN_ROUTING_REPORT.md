# Phase 5 PR 2 — Main Brain Routing on V2 Truth

**Status:** Complete (local dev only).
**Date:** 2026-05-01.
**Branch:** `rebuild-connections-mcp-runtime`.
**Builds on:** Phase 5 PR 1 (commit `5c9b999`).

## What this PR does

Makes the Main Brain selection backend-enforce a real callable check.
Operators can no longer pin a runtime as Main Brain just because the
binary exists on disk — when `USE_CONNECTION_REGISTRY_V2` is on, the
last probe must have proven `callable=true`. Founder can opt in to
an Experimental Override which is loudly audit-logged.

## Files

| File | Role |
|---|---|
| `backend/app/api/v1/runtimes.py` | `set_primary_runtime` now consults V2 truth + accepts `experimental_override` |
| `backend/tests/test_phase5_main_brain_callable_gate.py` | NEW — 7 tests covering all founder-mandated cases |
| `frontend/src/pages/connections/MainBrainPanel.tsx` | Surfaces V2 truth chips + last probe time + per-dim failure reason; disables "Set Main Brain" when V2 says not callable; toggle for Experimental Override |

## Backend gate

```python
class PrimaryRuntimeRequest(BaseModel):
    runtime_id: str
    experimental_override: bool = False
```

When `is_v2_enabled()` AND a `ConnectionV2` row exists for
`(tenant_id, kind=cli_runtime, slug=runtime_id)`:

- `callable=True` → **allow** (normal path)
- `callable=False` AND no override → **refuse** with payload:
  ```json
  {
    "success": false,
    "error": {
      "message": "<display_name> cannot be set as Main Brain because its last probe did not prove callable. Run a probe first, or pass experimental_override=true to pin anyway (logged).",
      "code": "runtime_not_callable",
      "v2_callable": false,
      "v2_truth": {"detected": true, "configured": true, "imported": true, "reachable": false, "authenticated": false, "callable": false}
    }
  }
  ```
- `callable=False` AND `experimental_override=true` → **allow** with
  audit log entry `runtimes.primary_override_not_callable` capturing
  user_id, role, runtime_id, tenant_id

When V2 row does NOT exist yet: **allow** with
`callable_check_skipped_reason="no V2 row yet (legacy probe path; will
be checked on next real probe via ConnectionRegistryV2)"`.

When `is_v2_enabled()` is False: **bypass entirely** — legacy behavior
preserved byte-for-byte.

## Frontend changes

The Main Brain panel's CLI runtime rows now show:

- **V2 truth pill** — emerald `V2 callable` or rose `V2 not callable`.
  Tooltip shows `last proved callable at <ISO>`.
- **Inline V2 failure reason** when the row is not callable
  (e.g. "round-trip timed out after 25.0s").
- **Last probe timestamp** as a small footnote.
- **"No V2 row yet — selection allowed"** when the runtime hasn't
  been mirrored to V2 (legacy probe path).
- **Set Main Brain disabled** when V2 says not callable AND the
  Experimental Override checkbox is off. Tooltip explains why.

A page-level **Experimental Override** checkbox sits in the header of
the runtimes section so the operator can flip it once and pin
multiple non-callable runtimes for testing.

## Tests (7/7 PASS)

| Test | Asserts |
|---|---|
| `test_cannot_select_non_callable_runtime_when_flag_on` | refuse + `runtime_not_callable` code |
| `test_can_select_callable_runtime_when_flag_on` | allow path returns success |
| `test_flag_off_preserves_legacy_behavior` | gate bypassed entirely |
| `test_experimental_override_pins_non_callable` | override flips refuse → allow |
| `test_no_v2_row_yet_allowed_with_skip_reason` | missing V2 row falls through to legacy path with skip reason |
| `test_route_module_uses_runtime_not_callable_code` | route source still emits the code the frontend depends on |
| `test_pydantic_request_model_accepts_override_flag` | request model contract intact |

Combined Phase 4b PR1+PR2+PR3 + Phase 5 PR2 + adapter suite:
**120/120 PASS**.

### Why these are unit-level not E2E

The route uses `async_session_factory()` directly (its own session,
not FastAPI's overridden `get_db`), so the gate cannot be exercised
end-to-end against the test SQLite engine without restructuring the
route. The unit test directly seeds the `connection_v2` table on the
test session and asserts the gate logic. The route's *contract*
(`runtime_not_callable` code, `experimental_override` body field) is
asserted by string-matching the route source so the frontend can rely
on it.

A future cleanup PR could refactor `set_primary_runtime` to take a
`db: AsyncSession = Depends(get_db)` parameter so HTTP-level tests
can exercise the path. Out of scope for this PR — the gate is
already enforced and tested.

## Truth-rule contract honored

| Rule | How |
|---|---|
| `imported != callable` | Mere existence of a CLI binary (legacy `installed=True`) is no longer sufficient to pin Main Brain |
| `authenticated != callable` | Subscription auth check passing (legacy `subscription.is_authenticated`) is no longer sufficient — a real round-trip must have flipped V2 callable |
| `failure visible` | Per-dim failure reason rendered inline next to the row |
| `stale != failed` | A row whose V2 callable_at is older than 24h is still callable=True (state_machine returns `healthy_stale`); the gate allows it. The reconciler reports it as drift for operator follow-up |

## Production blockers (unchanged)

- `USE_CONNECTION_REGISTRY_V2` still defaults to False
- No production deploy
- Legacy `vault.py` + `oauth_credentials_store.py` intact

## Risks / known issues

- Dev tests cannot exercise the HTTP endpoint because the route
  uses `async_session_factory()` directly. Refactoring this is
  out of PR scope.
- The frontend disables the button when V2 says not callable, but
  a determined user could still POST manually to the endpoint with
  `experimental_override=true`. This is by design — founder must
  be able to override; the audit log captures it.
- The route logs the override at WARNING level via `get_logger`.
  No formal AuditLog entry is created (the existing audit_service
  doesn't have a hook for this event yet). Adding one is a
  backlog item.
- Provider-id-based selections (OPENAI, GEMINI, etc.) bypass the
  V2 gate entirely because the V2 registry doesn't model
  hosted-API providers as a `cli_runtime` kind. Those rely on the
  legacy provider-key-presence check. Phase 6+ will add
  `kind=provider` rows to V2 and extend the gate.

## Next founder actions

1. Review this report.
2. Enable `USE_CONNECTION_REGISTRY_V2=true` in `backend/.env` for dev
   testing if not already set.
3. Run a real probe against `/api/v1/connections/v2/{cli_runtime_id}/probe`
   to flip callable=True for runtimes you actually have installed
   + authenticated.
4. Try setting Main Brain to a non-callable runtime in the UI —
   you should see a clear "not callable" rejection.
5. Toggle Experimental Override and try again — should pin and
   show "(experimental override -- audit logged)" toast.

## Commit

`phase5: wire main brain selection to registry v2 callable runtimes`
