# PR-4 -- Routine Autonomy Scheduler

**Sprint:** DAENA-SPRINT-18-TRUST-LADDER-AND-ROUTINE-AUTONOMY
**PR:** 4 of 6
**Date:** 2026-05-06

## Goal

Skeleton-only scheduler that lets the operator register routines
Daena CAN run on demand. **No cron daemon is activated in
Sprint-18.** The skeleton + state surface is in place so a future
sprint can layer cron on top without changing the contract.

The single load-bearing fact: every scheduler-initiated dispatch
flows through `DispatchInitiator.SCHEDULER`, which trust policy
wall #2 ALWAYS refuses. So routines can produce drafts and
proposals, but NOTHING they create can auto-execute. The operator
still has to approve manually.

## What ships

`backend/app/services/routine_autonomy.py` (new):

* `RoutineKind` enum -- exactly the 6 Sprint-18 allowed kinds.
* `RoutineOutcome` enum -- `ok / paused / global_paused /
  unknown_routine / invalid_kind / refused_forbidden_action /
  handler_not_registered / handler_raised`.
* `register_routine` -- refuses unknown kind.
* `pause_routine` / `resume_routine` -- per-routine pause.
* `pause_all` / `resume_all` / `is_global_paused` -- emergency
  stop.
* `register_handler(kind, handler)` + `run_once(routine_id, **kw)`
  orchestration.
* `run_once` NEVER raises -- returns a typed `RoutineRunResult`
  for every input, including bizarre routine ids.
* JSON state at `backend/.routine_autonomy.json` (gitignored).

`backend/app/api/v1/routines.py` (new):

* `GET /api/v1/routines` -- list registered routines
* `GET /api/v1/routines/kinds` -- locked Sprint-18 kind set
* `POST /api/v1/routines/register`
* `POST /api/v1/routines/{id}/pause` / `/resume` / `/run-once`
* `GET /api/v1/routines/global/state`
* `POST /api/v1/routines/global/pause` / `/resume`

`backend/app/api/v1/__init__.py` (modified): mounts the new
router under `/api/v1/routines`.

## Allowed Sprint-18 routine kinds (locked)

```
opportunity_discovery
business_workstream_proposal
local_draft_action_creation
self_diagnostic
readiness_check
repair_workstream_proposal
```

Forbidden surface (cannot exist as routine kinds):

```
external_send / external_submit / external_post / external_pay
file_apply  / git_commit  / git_push
security_scan
```

## Mythos design choices

**Skeleton, not full cron.** The brief said skeleton. A real cron
daemon spawning routine runs in the background is exactly the
surface where bugs amplify: a buggy handler runs every minute for
6 hours before anyone notices. Sprint-18 ships pause/resume/run-
once + state persistence; activation is Sprint-19+. The contract
is forward-compatible.

**Initiator = SCHEDULER, always.** Nowhere in this module can a
caller pass `OPERATOR`. That alone collapses the auto-approve
surface to manual-only for routine outputs.

**Module surface bans the verbs.** `TestForbiddenSurfaceAbsent`
walks `dir(routine_autonomy)` and refuses any callable named
`send / submit / post / pay / apply / commit / push`. Future
contributors get a unit-test failure if they try to add one. This
is the same self-policing pattern used in `trust_ladder` and
`trust_policy`.

**`run_once` NEVER raises.** Every reasonable failure mode --
unknown routine, paused, no handler, handler explosion -- returns
a typed `RoutineRunResult` with an `outcome` field. The API can
serialize the result verbatim; no try/except scaffolding needed.
Tested with bizarre inputs (`""`, 1000-char strings, null bytes,
path traversal) to prove the contract.

**JSON persistence, not DB.** Same pattern as `trust_policy.py`
and `trust_ladder.py`. Founder-install single-process is fine on
JSON. Multi-tenant cloud will move to DB; that migration is
identical for all three modules.

## Locked invariants

| Invariant | Where |
|---|---|
| 6 kinds locked | `TestKindEnum::test_six_kinds_locked` |
| No SEND/SUBMIT/POST/PAY/APPLY/COMMIT in kind values | same |
| Unknown kind refused at register | `TestRegister::test_unknown_kind_refused` |
| Per-routine pause / resume works | `TestPauseResume::test_pause_and_resume_per_routine` |
| Pausing unknown returns None | `test_pause_unknown_returns_none` |
| Global pause / resume works | `test_global_pause_resume` |
| Global pause blocks `run_once` | `TestRunOnce::test_global_paused_blocks` |
| Per-routine pause blocks `run_once` | `test_paused_routine_blocked` |
| Unknown routine returns UNKNOWN_ROUTINE | `test_unknown_routine_returns_unknown` |
| Missing handler returns HANDLER_NOT_REGISTERED | `test_handler_not_registered` |
| Handler that raises returns HANDLER_RAISED, NO propagate | `test_handler_raises_does_not_propagate` |
| Successful handler updates last_run state | `test_successful_handler` |
| `run_once` NEVER raises for any input | `test_run_once_never_raises_for_any_input` |
| Module exposes no send/submit/post/pay/apply/commit | `TestForbiddenSurfaceAbsent` |
| State file is gitignored | `TestGitignored` |

## Hard rules audit

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied |
| No external send / submit / post / pay surface | enforced -- not in kind set + module surface bans the verbs |
| No file apply | enforced -- forbidden tools cannot graduate; routine kind set excludes |
| No git commit | enforced -- same |
| No security scan kind | enforced -- not in kind set |
| Schedule writes local workstreams / drafts only | enforced -- routine handlers cannot reach external write surface |
| Operator can pause all routines | enforced -- `/global/pause` endpoint |
| Daena cannot raise own trust tier via scheduler | enforced -- scheduler initiator never graduates |
| Routine-initiated dispatches NEVER auto-approve | enforced -- `DispatchInitiator.SCHEDULER` never satisfies `should_auto_approve` wall #2 |

## Tests

```
backend/tests/test_routine_autonomy.py   15 tests
```

15/15 pass.

## Files

```
new:        backend/app/services/routine_autonomy.py
new:        backend/app/api/v1/routines.py
new:        backend/tests/test_routine_autonomy.py
modified:   backend/app/api/v1/__init__.py
new:        docs/Ultraview/PR_ROUTINE_AUTONOMY_SCHEDULER_REPORT.md
```

## Next: PR-5 -- Trust-aware VP chat
