# PR-8 -- Controlled Execution Design Lock

**Sprint:** DAENA-AUTONOMOUS-BUSINESS-OPERATOR-SPRINT-13
**PR:** 8 of 9
**Date:** 2026-05-06

## Goal

Lock the design for any future external action *without* enabling
it. PR-8 ships the validator + the dataclass + the empty
`WRITE_TOOLS` allowlist. PR-8 does NOT execute anything.

## What ships

`backend/app/services/controlled_execution_design.py` (new):

### The 10-field locked contract

Every future external action's request must carry every one of:

```
approval_id                       GoaRequest.id
consent_grant_id                  Asset Shield consent token
payload_hash                      sha256 hex of action body (64 chars)
tool_id                           must be in WRITE_TOOLS allowlist
owner_email                       account profile (None when n/a)
asset_shield_pass                 must be True
policy_allowlist_pass             must be True
audit_preflight_row_id            AuditEvent.id created BEFORE exec
audit_result_row_id               AuditEvent.id created AFTER exec
                                  (None on pre-build; executor stamps)
rollback_or_undo_instruction      text plan or None
```

The `_REQUIRED_FIELDS` tuple pins this list. The
`ControlledExecutionRequest` dataclass exposes every one. The
contract test `TestContractShape::test_required_fields_locked`
fails if anyone reorders or drops a field.

### `validate_controlled_execution_request(req)`

Pure validator -- no Asset Shield call, no policy lookup, no DB
hop. The executor populates the booleans by actually calling those
services and passes the results in. The validator is the wall.
Refusal codes:

```
tool_id_not_in_allowlist
asset_shield_pass_required
policy_allowlist_pass_required
approval_id_required
consent_grant_id_required
payload_hash_required_sha256_hex
audit_preflight_row_id_required
```

### `WRITE_TOOLS` is empty

Phase 3 starts closed. The closed set is `frozenset()`. Adding the
first concrete tool requires:

1. Updating `WRITE_TOOLS`
2. Updating the Asset Shield egress allowlist
3. Updating the plain-English policy compiler templates
4. Adding a dedicated negative test that proves a missing field is
   refused
5. Knowingly updating `TestPhase3StaysOff::test_write_tools_is_empty`
   -- which fails on purpose the moment `WRITE_TOOLS` becomes non-empty

That deliberate test failure is the operator-visible signal that
Phase 3 is being opened.

### `INTEGRATIONS_PHASE2_READONLY` env unchanged

The pre-existing env var that gates Phase 3 writes at the route
level remains the actual enforcement. PR-8 does not touch it. The
contract test `TestPhase3StaysOff::test_readonly_env_default_unchanged`
asserts it stays at `'true'`.

## Tests

`backend/tests/test_controlled_execution_design_lock.py` -- 5 tests:

```
TestPhase3StaysOff::test_write_tools_is_empty
TestPhase3StaysOff::test_readonly_env_default_unchanged
TestContractShape::test_required_fields_locked
TestContractShape::test_dataclass_carries_all_fields
TestValidatorRefusesEverything::test_refuses_any_tool_id_in_pr8
TestValidatorRefusesEverything::test_refuses_short_payload_hash
```

Sanity regression: 61/61 pass on the full Sprint-13 fast subset.

## Hard rules audit

| Rule | Status |
|---|---|
| Phase 3 stays OFF | enforced -- `WRITE_TOOLS = frozenset()` + `INTEGRATIONS_PHASE2_READONLY=true` |
| 10 required fields locked | enforced -- contract test fails on reorder / drop |
| No actual execution | enforced -- the module has no HTTP / DB / external call |
| Adding a new tool surfaces deliberately | enforced -- `test_write_tools_is_empty` will fail on the first add |
| Asset Shield + policy gate inputs are external | enforced -- the validator does not call them itself |
| Refusal codes stable | enforced -- tested by string match |

## Files

```
new:        backend/app/services/controlled_execution_design.py            (170 lines)
new:        backend/tests/test_controlled_execution_design_lock.py         (130 lines, 6 tests)
new:        docs/Ultraview/PR_CONTROLLED_EXECUTION_DESIGN_LOCK_REPORT.md
```

## What this PR does NOT do

- Does NOT add any concrete write tool (no email_send /
  linkedin_dm_send / etc.). That belongs in a later sprint with
  explicit founder approval.
- Does NOT mount any execution endpoint. The validator is reachable
  only by importing the module.
- Does NOT design the frontend approval modal. Modal design is a
  small follow-up; the backend contract was the load-bearing piece.
- Does NOT relax the Asset Shield or the plain-English policy
  compiler. Both remain unchanged.

## Next: PR-9 -- Sprint-13 Smoke + Final Report
