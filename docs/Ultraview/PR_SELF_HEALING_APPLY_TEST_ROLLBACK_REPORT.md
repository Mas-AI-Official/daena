# PR-4 -- Self-Healing Apply / Test / Rollback Loop

**Sprint:** DAENA-SPRINT-17-FILE-APPLY-AND-SELF-HEALING-PATCH-LOOP
**PR:** 4 of 7
**Date:** 2026-05-06

## Goal

Wrap the controlled-execution dispatch for
`local.file_change_proposal.apply` with the audit-before /
audit-after stamping AND the blocker-workstream emission rule
from the brief.

## What ships

`backend/app/services/self_healing_apply_loop.py` (new):

* `SelfHealingApplyResult` dataclass: `outcome` (success /
  tests_rolled_back / rollback_failed / refused / crashed),
  `refusal_code`, `refusal_detail`, `handler_result`,
  `audit_preflight`, `audit_result`, `blocker_workstream`.
* `_audit_row(when, request, ...)` builds the audit-row dict the
  caller persists. Pure shaping; no DB write.
* `_blocker_workstream_payload(request, refusal_detail)` builds
  the P0 workstream payload the orchestrator emits when the
  apply handler refuses with `rollback_failed` or crashes.
* `run_apply_cycle(db, request, payload, tenant_id, user_id)`
  orchestrates:
    1. Stamp audit-preflight row.
    2. Call `dispatch_controlled_execution`.
    3. Classify the outcome:
        - success -> outcome=`success`
        - `ControlledExecutionRefused('tests_failed_rolled_back')`
          -> outcome=`tests_rolled_back` (no blocker; file
          already restored by the handler's backup logic)
        - `ControlledExecutionRefused('rollback_failed')` ->
          outcome=`rollback_failed` + blocker payload (CRITICAL,
          manual cleanup required)
        - any other refusal -> outcome=`refused`, no blocker
        - any other exception -> outcome=`crashed`, blocker
          payload (handler should never raise; this is defense
          in depth)
    4. Stamp audit-result row.
    5. Return the typed result.

## Mythos design choice: NEVER raises

The loop catches every reasonable exception (including bare
`Exception`) so callers can rely on the typed `outcome` field
without try/except scaffolding. Tests parametrize over arbitrary
exception types to prove this.

Why this matters: the autonomous repair loop (a future sprint)
will compose `run_apply_cycle` in a tight feedback cycle. If
unhandled exceptions could bubble, one buggy handler crash would
take down the whole self-healing path. By forcing every failure
into the typed-result channel, the orchestrator stays stable.

## Locked invariants

| Invariant | Where |
|---|---|
| Audit-preflight always stamped | `TestAuditAlwaysStamped::test_success_stamps_pre_and_post` |
| Audit-result always stamped | same |
| Success path returns handler_result + no blocker | same |
| tests_failed_rolled_back -> no blocker (handler already restored) | `test_tests_failed_rolled_back` |
| rollback_failed -> blocker workstream emitted | `test_rollback_failed_emits_blocker` |
| Other refusals -> no blocker | `test_other_refusal_no_blocker` |
| Handler crash -> blocker emitted | `test_handler_raises_emits_blocker` |
| Loop NEVER raises | `TestLoopNeverRaises` (3 parametrized) |

## What is NOT in this PR

* **No GoaRequest creation.** PR-4 consumes an
  already-approved request. The approval-creation flow lives
  upstream (operator clicks Approve in the modal).
* **No DB write.** Audit-row dicts are returned, not persisted.
  The caller (or a future Phase 4 AuditEvent writer) is
  responsible for persistence.
* **No autonomous trigger.** This is the orchestration layer; the
  trigger that calls `run_apply_cycle` lives in the future
  autonomous-repair loop or in a manual operator action.

## Tests

```
backend/tests/test_self_healing_apply_loop.py     8 tests
```

8/8 pass.

## Files

```
new:        backend/app/services/self_healing_apply_loop.py
new:        backend/tests/test_self_healing_apply_loop.py
new:        docs/Ultraview/PR_SELF_HEALING_APPLY_TEST_ROLLBACK_REPORT.md
```

## Next: PR-5 -- Separate Commit Approval Wall
