# PR-6 -- Business Routine Run-Once

**Sprint:** DAENA-SPRINT-19-BUSINESS-EXECUTION-LOOPS
**PR:** 6 of 8
**Date:** 2026-05-06

## Goal

Wire the business pipeline orchestrator to the Sprint-18
`routine_autonomy` scheduler as the handler for the
`opportunity_discovery` kind. Operator can register a routine
and `/api/v1/routines/{id}/run-once` it. Initiator is ALWAYS
`SCHEDULER`, so every downstream `GoaRequest` produced by routine
activity is FORBIDDEN from auto-approval.

## What ships

`backend/app/services/business_pipeline/routine_handler.py` (new):

* `opportunity_discovery_handler(*, db, tenant_id, user_id, top_n)`
  -- async, forwards to `run_discovery_loop` with
  `initiator='scheduler'`. NEVER raises.
* `register()` -- registers the handler with `routine_autonomy`
  for kind `opportunity_discovery`. Idempotent (re-registration
  replaces).
* Auto-registers on module import (side-effect import from
  `business_pipeline/__init__.py`).

`backend/app/services/business_pipeline/__init__.py` (modified):
side-effect import of `routine_handler`.

`backend/app/api/v1/routines.py` (modified): `POST /{id}/run-once`
now forwards `db`, `tenant_id`, `user_id` as kwargs to the
handler, then commits if outcome is OK. Sprint-18 routine tests
still pass (regression: 15/15).

## Mythos design choices

**Initiator is hardcoded to `'scheduler'` in the handler.** The
caller cannot override. Even if a test passes
`initiator='operator'` as a kwarg, the handler ignores it and
calls the orchestrator with `'scheduler'`. This is the load-bearing
fact: routine-initiated dispatches CANNOT auto-approve, ever,
because Sprint-18 wall #2 refuses `SCHEDULER` initiators.

**Routine handler does NOT call the bridges (yet).** PR-6 ships
the discovery -> opportunity persistence loop only. Bridges
(PR-4 outreach->Gmail draft, PR-5 send) are NOT triggered by the
routine. The brief allows "create local drafts" and "queue
approvals" as routine-level actions, but the safer path is:
- Sprint-19 PR-6: routine produces opportunities only.
- Sprint-20+: routine optionally triggers draft factory + Gmail
  bridge for the top-N opportunities (still SCHEDULER initiator,
  still cannot auto-approve sends).

This keeps the explosion radius narrow on first ship.

**Side-effect import auto-registers the handler.** Mirrors the
controlled-execution-handlers pattern (Sprint-14). On backend
startup, `business_pipeline` is imported (via API router), which
imports `routine_handler`, which calls `register()`. No bootstrap
config needed.

**`run_once` API endpoint forwards context kwargs.** The
Sprint-18 routine_autonomy contract was that handlers may take
arbitrary kwargs. PR-6 extends the API endpoint to actually pass
`db / tenant_id / user_id` so handlers that need DB scope have
it. Old handlers that ignore kwargs continue to work
(backwards-compatible).

## Locked invariants

| Invariant | Where |
|---|---|
| Handler is registered for `opportunity_discovery` | `TestHandlerRegistered::test_opportunity_discovery_handler_in_registry` |
| Seeded source produces persisted opportunities via routine | `TestHandlerProducesArtifacts::test_seeded_file_persists_opportunities` |
| Missing context returns typed result, no raise | `TestNeverRaises::test_missing_context_returns_typed_result` |
| `run_once` API forwards db/tenant context | `TestRunOnceForwardsContext::test_run_once_passes_context` |
| Routine initiator is SCHEDULER | enforced in handler code; PR-4/5 bridge tests already pin SCHEDULER cannot auto-approve |
| Sprint-18 routine_autonomy tests still pass | regression: 15/15 |

## Hard rules audit

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied |
| No external send / submit / post / pay reachable from routine | applied -- handler only persists opportunities |
| No file apply | applied |
| No git commit | applied |
| No security scan | applied |
| Schedule writes local opportunities only (Sprint-19 scope) | applied |
| Operator can pause all routines | unchanged from Sprint-18 (`/global/pause`) |
| No cron daemon yet | applied -- PR-6 ships handler + run-once only |
| Scheduler initiator never auto-approves | enforced -- handler hardcodes `initiator='scheduler'` |

## Tests

```
backend/tests/test_business_routine.py   4 tests
backend/tests/test_routine_autonomy.py  15 tests (regression)
```

19/19 pass.

## Files

```
new:        backend/app/services/business_pipeline/routine_handler.py
new:        backend/tests/test_business_routine.py
modified:   backend/app/services/business_pipeline/__init__.py
modified:   backend/app/api/v1/routines.py
new:        docs/Ultraview/PR_BUSINESS_ROUTINE_RUN_ONCE_REPORT.md
```

## Next: PR-7 -- VP Business Chat Commands
