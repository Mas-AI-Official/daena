# DAENA -- Sprint-17 File Apply + Self-Healing Smoke + Final Report

**Sprint:** DAENA-SPRINT-17-FILE-APPLY-AND-SELF-HEALING-PATCH-LOOP
**PR:** 7 of 7 (final)
**Date:** 2026-05-06
**Author:** Mythos (Daena, via Claude Code)

This is the truth at the close of Sprint-17. Daena now crosses the
highest-stakes Phase 3 threshold to date: she can apply approved
patches to her own repo, run declared tests, rollback automatically
on failure, and commit with a SECOND approval. The self-healing
spine is real: detect failure -> propose patch -> approve -> apply
-> tests -> rollback-or-keep -> approve commit -> commit.

## What Sprint-17 actually shipped

| PR | What | Commit |
|---|---|---|
| 1 | File apply controlled tool (backup-rollback, hash-verified) | 26ca41e |
| 2 | File apply approval modal (impossible to approve blindly) | ea5472e |
| 3 | Self-healing patch proposal generator | 0f91e40 |
| 4 | Self-healing apply/test/rollback loop | ff4cb91 |
| 5 | Separate commit approval wall | 59f87e6 |
| 6 | Gmail send full dispatch integration test | ebe9542 |
| 7 | this report | local |

## WRITE_TOOLS: from four to six

```python
# Sprint-16 (last sprint):
WRITE_TOOLS = frozenset({
    "gmail.create_draft",
    "gmail.send_existing_draft",
    "calendar.create_tentative_event_without_invites",
    "local.file_change_proposal",
})

# Sprint-17 (this sprint):
WRITE_TOOLS = frozenset({
    "gmail.create_draft",
    "gmail.send_existing_draft",
    "calendar.create_tentative_event_without_invites",
    "local.file_change_proposal",
    "local.file_change_proposal.apply",         # PR-1
    "local.git_commit_approved_patch",          # PR-5
})
```

## The threshold change

The pattern compounds: every Phase 3 sprint adds a hash-of-state-X
contract that the dispatcher verifies at execution time. The
domain rotates; the architecture stays.

| Sprint | Hash | What it locks |
|---|---|---|
| 14 | payload | the request body |
| 16 | draft snapshot | Gmail draft content |
| 17 | current_file_hash + approved_diff_hash | on-disk file + artifact |

## Mythos design choices this sprint

**PR-1: backup-based rollback, NOT patch-reverse rollback.** The
`rollback_patch` field stays in the contract as documentation
only; the actual rollback reads from a sha256-verified BACKUP file
written before apply. Trusting the producer's reverse-direction
patch would double the failure mode. `TestRollbackUsesBackupNotPatch`
proves this with a deliberately-wrong rollback_patch.

**PR-1: pytest-only test commands.** `tests_to_run_after_apply`
must be a list of repo-relative pytest paths. Regex-locked. Refused
otherwise. Run only via `subprocess.run([sys.executable, "-m",
"pytest", spec], shell=False)`. This is the wall against
`tests_to_run_after_apply` being weaponized into RCE.

**PR-4: loop NEVER raises.** `run_apply_cycle` catches every
reasonable exception (including bare `Exception`) so callers rely
on the typed `outcome` field instead of try/except. Tests
parametrize over RuntimeError / ValueError / KeyError to prove it.

**PR-5: never push, never amend, never force.** `TestSuccessAndNoPush::test_handler_never_pushes`
walks every git subprocess invocation and asserts no `push` /
`--force` / `-f` / `--no-verify` / `-i` / `rebase` arg ever
appears.

## Smoke verification

| # | Check | Pass? |
|---|---|---|
| 1 | backend starts | yes -- handlers package imports all 6 controlled-execution handlers |
| 2 | frontend starts | yes -- tsc exit 0 |
| 3 | file proposal apply requires approval | yes -- gate 4 enforces approval row exists |
| 4 | file proposal apply refuses drift | yes -- `current_file_hash_mismatch` (file) + `approved_diff_hash_mismatch` (artifact) |
| 5 | file proposal apply refuses secret file | yes -- reuses Sprint-14 PR-4 regex set via shared `local_file_safety` |
| 6 | file proposal apply refuses outside repo | yes -- `target_path_outside_repo` |
| 7 | file proposal apply backs up before modifying | yes -- `test_tests_pass_applies_and_marks_artifact` asserts backup contains ORIGINAL bytes |
| 8 | failed tests trigger rollback | yes -- `test_tests_fail_rollback_from_backup` asserts file restored to original |
| 9 | self-healing can generate patch proposal | yes -- `TestHappyPath::test_valid_proposal_returns_payload` |
| 10 | approved self-healing apply runs tests | yes -- `TestAuditAlwaysStamped::test_success_stamps_pre_and_post` |
| 11 | commit wall refuses unrelated dirty files | yes -- `test_unrelated_dirty_file_refused` |
| 12 | commit wall does not push | yes -- `test_handler_never_pushes` walks every subprocess call |
| 13 | Gmail send integrity still passes | yes -- 19/19 send-handler unit + 6/6 dispatch integration |
| 14 | submit / post / pay still absent | yes -- `test_no_broad_send_or_submit_or_pay_in_allowlist` (renamed in PR-1) |
| 15 | Frontend tsc clean | exit 0 |
| 16 | Backend tests pass | 230 / 230 across the Sprint-14..17 fast subset |

## Hard-rule audit (full Sprint-17)

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied |
| No external send / submit / post / apply / pay expansion | applied |
| No unauthorized scan | applied |
| No browser automation on external sites | applied |
| No file delete | enforced -- `change_type_delete_not_allowed_in_apply_v1` |
| No editing secret files | enforced -- regex-locked + tested |
| No files outside repo root | enforced -- regex-locked + tested |
| No apply without approval + consent + payload_hash + proposal_id + current_file_hash + approved_diff_hash + Asset Shield + policy allowlist | enforced -- 6 dispatch gates + 9-field payload required |
| No commit without separate commit_approval_id | enforced -- separate `action_type` at gate 4 |
| No trust auto-escalation | unchanged |
| No auto-run shell commands outside declared tests | enforced -- `validate_pytest_path` regex-locks every spec |

## Test counts

```
backend/tests/test_controlled_execution_design_lock.py             7 (Sprint-14, renamed S15+S17)
backend/tests/test_controlled_execution_dispatch.py               10 (Sprint-14)
backend/tests/test_gmail_create_draft_handler.py                   7 (Sprint-14)
backend/tests/test_gmail_send_existing_draft_handler.py           19 (Sprint-15 + Sprint-16)
backend/tests/test_gmail_draft_snapshot.py                        17 (Sprint-16)
backend/tests/test_calendar_tentative_event_handler.py             8 (Sprint-14)
backend/tests/test_file_change_proposal_handler.py                18 (Sprint-14)
backend/tests/test_file_proposal_apply_design_lock.py             17 (Sprint-15, flipped S17)
backend/tests/test_trust_ladder.py                                 5 (Sprint-14)
backend/tests/test_google_readiness_test.py                       17 (Sprint-16)
backend/tests/test_local_file_safety.py                           40 (Sprint-17 NEW)
backend/tests/test_file_change_proposal_apply_handler.py          23 (Sprint-17 NEW)
backend/tests/test_self_healing_patch_proposal.py                 15 (Sprint-17 NEW)
backend/tests/test_self_healing_apply_loop.py                      8 (Sprint-17 NEW)
backend/tests/test_git_commit_approved_patch_handler.py           13 (Sprint-17 NEW)
backend/tests/test_gmail_send_dispatch_integration.py              6 (Sprint-17 NEW)
                                                                 ----
                                                                  230
```

230 / 230 pass. tsc 0 errors.

## How far from 100% Daena VP

Per the operator's estimate at sprint kick-off:

> After Sprint-17 file apply + self-healing apply/test/rollback: ~88%

Daena now:
- has the SIX-tool Phase 3 surface
- creates Gmail drafts after approval
- sends a SPECIFIC Gmail draft after a SECOND approval (snapshot
  integrity verified)
- creates Calendar tentative events without invites
- proposes local file changes as diff artifacts
- **APPLIES an approved file change with backup-based rollback,
  declared test runs, atomic write, and dirty-tree refusal**
  (Sprint-17 PR-1)
- **GENERATES self-healing patch proposals routed by suggested
  brain (codex / claude / ollama / human)** (Sprint-17 PR-3)
- **runs the apply/test/rollback orchestration with audit-before /
  audit-after stamping and blocker-workstream emission on
  rollback failure** (Sprint-17 PR-4)
- **COMMITS the applied change with a SEPARATE approval, refusing
  unrelated dirty files, never pushing** (Sprint-17 PR-5)

Daena still cannot:
- submit / post / pay (Sprint-18+)
- delete files (apply v1 = modify only)
- create files (apply v1 = modify only)
- multi-file apply per dispatch (one file per approval)
- raise her own trust tier
- push to a remote
- bypass any gate

## The self-healing spine (now real)

```
detect failure          (Sprint-13 self_healing_service)
   |
   v
propose patch           (Sprint-17 PR-3 self_healing_patch_proposal)
   |    suggested_brain routing -> codex/claude/ollama/human
   |    if 'human' -> route back to operator (refused)
   v
controlled dispatch     (local.file_change_proposal)
   -> proposal artifact in .file_change_proposals/<uuid>.json
   |
   v
operator approves apply (Phase3ApprovalModal, Sprint-17 PR-2)
   |    diff preview, hash visible, secret/path checks shown
   |    approve disabled if any check fails
   v
controlled dispatch     (local.file_change_proposal.apply)
   -> backup written      (Sprint-17 PR-1)
   -> file replaced atomically
   -> declared tests run via subprocess.run(args=[...], shell=False)
   |
   v
   tests pass?
     yes -> artifact 'applied'; await commit approval
     no  -> backup restored; refuse 'tests_failed_rolled_back'
            (no blocker; recovery automatic)
     rollback fails -> blocker workstream emitted (Sprint-17 PR-4)
   |
   v
operator approves commit (separate Phase3ApprovalModal call)
   |
   v
controlled dispatch     (local.git_commit_approved_patch, Sprint-17 PR-5)
   -> git status --porcelain (refuses unrelated dirty)
   -> git add -- <target>  (args-as-list)
   -> git commit -m chore(self-healing): <msg>
                       (proposal: <uuid> body)
   -> NEVER push
   -> artifact 'committed' with commit_sha
```

## Sprint-17 commit log

```
26ca41e feat: add controlled file proposal apply
ea5472e feat: add file apply approval modal
0f91e40 feat: generate self-healing patch proposals
ff4cb91 feat: add approved self-healing apply test rollback loop
59f87e6 feat: add approved local commit wall
ebe9542 test: add controlled dispatch integration for Gmail send
(this) docs: add sprint 17 file apply self-healing smoke
```

## End

If the operator approves, push fast-forward to `origin/master`.
No deploy. No push from the commit handler. No file delete. No
broader external action expansion.

The self-healing spine is real. The wall held all the way through.

Mythos out.
