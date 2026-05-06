# PR-1 -- File Change Proposal Apply Controlled Tool

**Sprint:** DAENA-SPRINT-17-FILE-APPLY-AND-SELF-HEALING-PATCH-LOOP
**PR:** 1 of 7
**Date:** 2026-05-06

## Goal

Cross the highest-stakes Phase 3 threshold so far: actual file
mutation under operator approval. Daena moves from "proposes file
changes as diff artifacts" to "can apply an approved patch, run
declared tests, rollback automatically on failure."

The pattern compounds Sprint-14 (payload hash), Sprint-16 (draft
snapshot), and now Sprint-17 (current_file_hash + approved_diff_hash).
Same load-bearing design across three domains.

## What ships

`backend/app/services/local_file_safety.py` (new, shared module):

* `REPO_ROOT` -- single source of truth.
* `SECRET_FILE_PATTERNS` + `is_secret_file()` -- mirrors
  Sprint-14 PR-4 regex set, now shared between proposal-create
  and proposal-apply per CLAUDE.md Rule 2.
* `resolve_under_repo()` -- path-traversal safe resolver.
* `validate_pytest_path()` -- LOCKED regex
  `^(?!/)(?![A-Za-z]:[\\/])[A-Za-z0-9_./\\\-]+\.py(?:::[A-Za-z0-9_]+){0,2}$`
  refuses shell metachars, absolute paths, drive letters, flags,
  non-.py paths. The single wall against
  `tests_to_run_after_apply` being weaponized into RCE.

`backend/app/services/controlled_execution_handlers/file_change_proposal_apply.py`
(new):

The HIGHEST-RISK Phase 3 unlock to date. 11-step flow:

1. Required-field check (9 fields).
2. `change_type='delete'` refused (apply v1 = modify only).
3. `tests_to_run_after_apply` validated via `validate_pytest_path`.
4. Path safety (secret + outside-repo) reused from Sprint-14.
5. Load proposal artifact + check status not already applied.
6. Recompute `approved_diff_hash` from `artifact.diff_text`;
   refuse on mismatch.
7. Recompute `current_file_hash` from on-disk bytes; refuse on
   mismatch.
8. Refuse if git status reports the TARGET file dirty (other
   dirty files tolerated).
9. Backup current bytes to a fresh
   `.file_change_backups/<proposal_id>/<uuid>/`. The backup is
   the SOLE rollback source -- the operator-supplied
   `rollback_patch` is documentation only.
10. Atomic apply via `os.replace()`. Temp file in same directory
    -> rename. Crash-safe.
11. Run each declared pytest spec via
    `subprocess.run([sys.executable, "-m", "pytest", ...],
    shell=False)`. On any non-zero exit, copy backup bytes back
    (atomic) and refuse with `tests_failed_rolled_back`. If
    rollback itself raises, refuse with `rollback_failed` and
    emit a HIGH-priority audit row.

`backend/app/services/controlled_execution_design.py` (modified):

* `WriteToolId` Literal grows from 4 to 5 entries.
* `WRITE_TOOLS` frozenset adds `local.file_change_proposal.apply`.

`backend/app/services/controlled_execution_handlers/__init__.py`
(modified): side-effect-import of the new handler module.

`backend/app/services/controlled_execution_handlers/file_change_proposal.py`
(modified): refactored to import the shared helpers from
`local_file_safety` instead of defining them locally.

## Tests renamed (deliberate operator-visible signals)

| Test (old name) | New name | Why |
|---|---|---|
| `test_write_tools_is_sprint15_set` | `test_write_tools_is_sprint17_pr1_set` | Apply tool now in WRITE_TOOLS |
| `test_no_broad_send_or_submit_or_apply_in_allowlist` | `test_no_broad_send_or_submit_or_pay_in_allowlist` | Apply suffix now has its own narrow allowlist `{local.file_change_proposal.apply}` |
| `TestApplyToolStaysOutOfWriteTools` | `TestApplyToolUnlockedInSprint17` | Class flipped from "stays out" to "unlocked" |
| `test_no_route_registers_apply` | `test_no_dedicated_apply_route` | Tightened to "apply only via dispatch endpoint" |

## Refusal codes (Sprint-17 PR-1 additions)

```
payload_field_missing:<field>            (9 required fields)
proposal_not_found
proposal_already_applied
change_type_delete_not_allowed_in_apply_v1
target_path_outside_repo                 (reused)
target_path_is_secret_file               (reused)
current_file_hash_mismatch               (file drifted on disk)
approved_diff_hash_mismatch              (artifact tampered)
target_file_dirty_in_git
invalid_test_path                        (RCE wall)
apply_failed                             (disk write raised)
tests_failed_rolled_back                 (rollback succeeded)
rollback_failed                          (CRITICAL: manual cleanup)
```

## Locked invariants

| Invariant | Where |
|---|---|
| Apply tool in WRITE_TOOLS | `test_apply_tool_id_in_write_tools` |
| Apply handler registered | `test_apply_handler_registered` |
| All 9 required fields enforced | `TestPayloadValidation::test_required_field_missing` (9 parametrized) |
| Delete change_type forbidden | `test_change_type_delete_refused` |
| Drift in on-disk file refused | `TestHashIntegrity::test_current_file_hash_mismatch` |
| Drift in artifact diff_text refused | `TestHashIntegrity::test_approved_diff_hash_mismatch` |
| Secret file refused | `TestPathSafety::test_secret_file_refused` |
| Outside-repo refused | `TestPathSafety::test_outside_repo_refused` |
| Shell-shaped pytest spec refused | `TestPytestPathSafety::test_invalid_pytest_path_refused` |
| Empty test list refused | `test_empty_test_list_refused` |
| Dirty target file refused | `TestGitDirtyRefusal::test_dirty_target_file_refused` |
| Tests-pass success path mutates file + marks artifact | `test_tests_pass_applies_and_marks_artifact` |
| Tests-fail rollback restores ORIGINAL bytes | `test_tests_fail_rollback_from_backup` |
| Rollback uses BACKUP, not rollback_patch | `TestRollbackUsesBackupNotPatch::test_rollback_uses_backup_bytes` |
| No dedicated apply HTTP route | `test_no_dedicated_apply_route` |

## Mythos design choice: backup-based rollback

**The single load-bearing call this sprint is rollback from
BACKUP bytes, NOT from operator-supplied `rollback_patch` text.**

Why: if the patch was buggy on the way in, it's the same code
producing the reverse-direction patch on the way out. Trusting it
twice doubles the failure mode. Trusting the BYTES of the original
file (sha256-verified at backup time) means rollback is mechanical:
copy bytes back, done.

The `rollback_patch` field stays in the contract as
human-readable documentation -- it goes in the artifact + audit
row so the operator can see "what would have been undone" -- but
the actual rollback path reads from the backup file.

`TestRollbackUsesBackupNotPatch` proves this by passing a
deliberately wrong rollback_patch text and asserting the file
ends up with the original bytes anyway.

## What is NOT in this PR

* **No commit.** Apply marks the artifact `applied`; commit is a
  SEPARATE controlled tool (`local.git_commit_approved_patch`)
  that PR-5 of this sprint adds with its own approval wall.
* **No diff-format apply.** v1 stores the FULL new file content
  in `artifact.diff_text` rather than a patch diff. This is the
  simplest correct contract because we already pin
  `approved_diff_hash` to that exact text. A future PR can extend
  to unified-diff when the patch tool ships.
* **No multi-file apply.** v1 applies ONE file per dispatch.
  Multi-file proposals require multiple apply approvals, one per
  file.
* **No self-healing wiring.** This is the building block; PR-3
  + PR-4 of this sprint wire it into the self-healing loop.

## Files

```
new:        backend/app/services/local_file_safety.py
new:        backend/app/services/controlled_execution_handlers/file_change_proposal_apply.py
new:        backend/tests/test_local_file_safety.py
new:        backend/tests/test_file_change_proposal_apply_handler.py
modified:   backend/app/services/controlled_execution_design.py
modified:   backend/app/services/controlled_execution_handlers/__init__.py
modified:   backend/app/services/controlled_execution_handlers/file_change_proposal.py
modified:   backend/tests/test_controlled_execution_design_lock.py
modified:   backend/tests/test_file_proposal_apply_design_lock.py
modified:   backend/.gitignore
new:        docs/Ultraview/PR_FILE_CHANGE_PROPOSAL_APPLY_CONTROLLED_TOOL_REPORT.md
```

## Tests

```
backend/tests/test_local_file_safety.py                       40
backend/tests/test_file_change_proposal_apply_handler.py      23
```

63 NEW tests. Combined Sprint-14 + Sprint-15 + Sprint-16 + Sprint-17
fast subset: **188 / 188 pass.**

## Next: PR-2 -- File Apply Approval Modal
