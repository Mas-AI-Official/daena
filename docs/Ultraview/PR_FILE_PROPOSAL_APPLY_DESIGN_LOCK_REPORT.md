# PR-5 -- File Proposal Apply Design Lock

**Sprint:** DAENA-SPRINT-15-GOOGLE-LIVE-AND-FIRST-SEND-UNLOCK
**PR:** 5 of 6
**Date:** 2026-05-06

## Goal

Pin the contract for a future ``local.file_change_proposal.apply``
tool WITHOUT shipping any apply capability. Sprint-15 ends with
the apply tool firmly OUT of WRITE_TOOLS.

## What ships

`backend/app/services/file_proposal_apply_design.py` (new):

* `APPLY_TOOL_ID = "local.file_change_proposal.apply"` -- constant
  reference for tests + future executor.
* `_REQUIRED_APPLY_FIELDS` -- 9-tuple locked at design time.
* `ApplyChangeType = Literal["modify"]` -- ``"delete"`` is
  intentionally absent. PR-5 forbids destructive apply outright.
* `ApplyFileChangeProposalRequest` frozen dataclass with all 9
  fields:
    - `proposal_id`
    - `current_file_hash` (sha256 hex, 64 chars)
    - `approved_diff_hash` (sha256 hex, 64 chars)
    - `repo_root_relative_path`
    - `backup_file_path`
    - `rollback_patch`
    - `tests_to_run_after_apply` (list[str])
    - `commit_approval_id` (separate from the proposal approval)
    - `change_type` (Literal["modify"])
* `FileProposalApplyDesignError` exception.
* `validate_apply_file_change_proposal_request(req)` -- pure
  validator that raises on missing field, short hash, wrong
  change_type. The future executor calls this BEFORE touching disk.

`backend/tests/test_file_proposal_apply_design_lock.py` (new):

17 tests in 5 classes:

* `TestApplyToolStaysOutOfWriteTools` (2): pins
  APPLY_TOOL_ID not in WRITE_TOOLS, no handler registered.
* `TestContractShape` (3): required-fields tuple, dataclass has
  every field, dataclass is frozen.
* `TestValidatorRefusesMissingFields` (10 parametrized): each
  field's missing or short value raises with the expected refusal
  string.
* `TestChangeTypeForbidsDelete` (1): runtime refusal on
  `change_type="delete"`.
* `TestNoHttpEndpointExists` (1): walks the v1 router and asserts
  no route's path mentions both `file_change_proposal` and `apply`,
  no route ends with `/file-apply`.

## Why these 9 fields

| Field | Why it's load-bearing |
|---|---|
| proposal_id | Pins WHICH proposal is being applied; prevents apply-without-approve drift |
| current_file_hash | Refuses if file changed since proposal (operator edited / external edit) |
| approved_diff_hash | Refuses if diff body tampered between approval and apply |
| repo_root_relative_path | Path-traversal guard; reused regex from PR-4 of Sprint-14 |
| backup_file_path | Rollback target; refuse if missing on disk |
| rollback_patch | One-command undo for the operator |
| tests_to_run_after_apply | Auto-rollback if any test fails post-apply |
| commit_approval_id | Apply-then-commit is TWO walls; a single approval doesn't authorize commit |
| change_type | Locked to "modify"; "delete" requires a future contract revision |

## Locked invariants

| Invariant | Where |
|---|---|
| local.file_change_proposal.apply NOT in WRITE_TOOLS | `TestApplyToolStaysOutOfWriteTools::test_apply_tool_id_not_in_write_tools` |
| No apply handler registered | `TestApplyToolStaysOutOfWriteTools::test_no_apply_handler_registered` |
| No HTTP route exposes apply | `TestNoHttpEndpointExists` |
| 9-field contract pinned | `TestContractShape` |
| change_type = "delete" forbidden | `TestChangeTypeForbidsDelete` |
| Validator refuses missing/short fields | `TestValidatorRefusesMissingFields` (10 parametrized) |
| Apply requires SEPARATE commit approval | `commit_approval_id` field locked + validator refuses empty |

## Hard rules audit

| Rule | Status |
|---|---|
| No apply endpoint in this PR | enforced -- `TestNoHttpEndpointExists` |
| Future apply requires 9 fields | enforced -- locked tuple |
| Future apply requires repo-root check | declared in module docstring; reuses PR-4 regex |
| Future apply requires secret-file check | declared; reuses PR-4 regex set |
| Future apply requires backup file | locked field |
| Future apply requires rollback patch | locked field |
| Future apply requires tests after apply | locked field |
| Future apply requires commit approval | locked field; SEPARATE from proposal approval |
| Future apply forbids delete by default | enforced -- ApplyChangeType Literal["modify"] only |

## Tests

```
backend/tests/test_file_proposal_apply_design_lock.py             17 tests
```

17/17 pass. Combined Sprint-15 fast subset:

```
backend/tests/test_controlled_execution_design_lock.py             7
backend/tests/test_gmail_create_draft_handler.py                   7
backend/tests/test_gmail_send_existing_draft_handler.py           14
backend/tests/test_file_proposal_apply_design_lock.py             17
                                                                  ---
                                                                   45
```

PR-6 will run the broader Sprint-14 + Sprint-15 fast subset.

## Files

```
new:        backend/app/services/file_proposal_apply_design.py
new:        backend/tests/test_file_proposal_apply_design_lock.py
new:        docs/Ultraview/PR_FILE_PROPOSAL_APPLY_DESIGN_LOCK_REPORT.md
```

## Next: PR-6 -- Sprint-15 Smoke + Final Report
