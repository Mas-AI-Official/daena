# PR-5 -- Separate Commit Approval Wall

**Sprint:** DAENA-SPRINT-17-FILE-APPLY-AND-SELF-HEALING-PATCH-LOOP
**PR:** 5 of 7
**Date:** 2026-05-06

## Goal

Applying a patch does NOT authorize a commit. Sprint-17 PR-5 adds
the SECOND wall: `local.git_commit_approved_patch`. Operator looks
at the modified file (already applied + tests passed in PR-1),
decides whether to commit, raises a separate approval, dispatches
the commit tool. Two walls, one per consequence.

## What ships

`backend/app/services/controlled_execution_handlers/git_commit_approved_patch.py`
(new):

* Handler accepts only `proposal_id` + `commit_message`.
* Loads the proposal artifact; refuses if missing / not applied /
  no `applied_at` timestamp.
* Inspects `git status --porcelain`. Tolerates ONLY the proposal's
  target file dirty; refuses if any unrelated file shows as dirty.
* Refuses if the target file itself is NOT dirty (already
  committed, rolled back, or someone else cleaned up).
* Sanitizes commit message: strips control chars, caps length,
  prepends `chore(self-healing): ` tag, appends `proposal: <id>`
  body for traceability.
* Runs `git add -- <target>` then `git commit -m <msg>` via
  `subprocess.run(args=[...], shell=False)`. Args-as-list. NEVER
  `shell=True`.
* Captures the new commit SHA via `git rev-parse HEAD`.
* Updates the artifact: `status="committed"`, `committed_at`,
  `commit_sha`.
* NEVER pushes. `TestSuccessAndNoPush::test_handler_never_pushes`
  walks every git subprocess invocation and asserts no `push` /
  `--force` / `-f` / `--no-verify` / `-i` / `rebase` arg ever
  appears.

`backend/app/services/controlled_execution_design.py` (modified):

* `WriteToolId` Literal grows from 5 to 6.
* `WRITE_TOOLS` adds `local.git_commit_approved_patch`.

`backend/app/services/controlled_execution_handlers/__init__.py`
(modified): side-effect-import of the new handler module.

## Refusal codes

```
payload_field_missing:proposal_id
payload_field_missing:commit_message
proposal_not_found
proposal_not_applied                       (status != "applied")
apply_tests_did_not_pass                   (no applied_at timestamp)
git_status_has_unrelated_dirty_files
target_file_not_dirty
git_command_failed                         (add or commit returned !=0)
invalid_commit_message                     (control chars present)
```

## Locked invariants

| Invariant | Where |
|---|---|
| Commit requires approved + applied proposal | `TestProposalChecks` (3 cases) |
| Unrelated dirty files refuse | `TestGitStatusChecks::test_unrelated_dirty_file_refused` |
| Clean tree refuses (nothing to commit) | `test_target_file_not_dirty_refused` |
| Control chars refused | `test_control_chars_refused` |
| Empty commit message refused | `test_empty_commit_message_refused` |
| git add failure caught | `test_git_add_failure_refuses` |
| Success marks artifact committed with SHA | `test_success_marks_committed` |
| Handler NEVER pushes / amends / force-pushes | `test_handler_never_pushes` |
| Commit message tagged with `chore(self-healing): ` | `test_message_prefixed_with_self_healing_chore` |
| Commit message references proposal id | `test_message_prefixed_with_self_healing_chore` |
| WRITE_TOOLS Sprint-17 PR-5 set is exactly 6 | `test_write_tools_is_sprint17_pr5_set` |

## Hard rules audit

| Rule | Status |
|---|---|
| Requires separate commit_approval_id | enforced -- separate `action_type` at gate 4 of dispatch |
| Only commits files changed by the approved apply | enforced -- target_file_not_dirty refuses unrelated trees |
| Commit message must include workstream/proposal id | enforced -- sanitizer appends `proposal: <id>` body |
| Refuse if git status includes unrelated dirty files | enforced -- `git_status_has_unrelated_dirty_files` |
| Refuse if tests from apply did not pass | enforced -- artifact missing `applied_at` -> `apply_tests_did_not_pass` |
| No push | enforced -- `test_handler_never_pushes` walks every subprocess call |
| No force | enforced -- same test |
| No deploy | applied (not in scope of this handler) |

## Tests

```
backend/tests/test_git_commit_approved_patch_handler.py    13 tests
backend/tests/test_controlled_execution_design_lock.py      7 tests (1 renamed for PR-5)
```

20/20 pass.

## Files

```
new:        backend/app/services/controlled_execution_handlers/git_commit_approved_patch.py
new:        backend/tests/test_git_commit_approved_patch_handler.py
modified:   backend/app/services/controlled_execution_design.py
modified:   backend/app/services/controlled_execution_handlers/__init__.py
modified:   backend/tests/test_controlled_execution_design_lock.py
new:        docs/Ultraview/PR_GIT_COMMIT_APPROVAL_WALL_REPORT.md
```

## Next: PR-6 -- Gmail Send Controlled Dispatch Integration Test
