# PR-2 -- File Apply Approval Modal

**Sprint:** DAENA-SPRINT-17-FILE-APPLY-AND-SELF-HEALING-PATCH-LOOP
**PR:** 2 of 7
**Date:** 2026-05-06

## Goal

Make file apply impossible to approve blindly. The modal must
visibly enforce every wall the dispatcher would later refuse on:
target path, hashes, backup, tests-to-run, secret-file +
outside-repo checks. Approve disabled until preview present.

## What ships

`frontend/src/components/governance/Phase3ApprovalModal.tsx`
(modified):

* `PHASE3_TOOL_IDS` grows from 4 to 5 -- adds
  `local.file_change_proposal.apply`.
* `ToolMeta` interface gains `is_file_apply: boolean` flag.
* `TOOL_META` adds the new entry with `risk: "high"`,
  `is_file_apply: true`, FileCog icon, rollback default text
  describing backup-based rollback + separate commit approval.
* New `Phase3FileApplyPreview` interface mirrors the locked
  Sprint-17 PR-1 contract (10 fields).
* `Phase3ApprovalDetails` gains optional
  `file_apply_preview?: Phase3FileApplyPreview | null`.
* New amber-bordered "This modifies local repo files" banner
  (test-id `phase3-file-apply-banner`) renders when
  `meta.is_file_apply` is true.
* New "File apply contract" preview block renders:
    - target_repo_relative (mono, breakable)
    - change_type (emerald when "modify", rose otherwise with
      "(refused -- only 'modify' is allowed)" suffix)
    - current_file_hash (16+8 truncation, tooltip: "refused at
      dispatch if drifted")
    - approved_diff_hash (16+8 truncation)
    - backup_file_path
    - secret-file check pill (emerald pass / rose FAIL)
    - outside-repo check pill (emerald pass / rose FAIL)
    - tests_to_run_after_apply list (emerald per spec; rose
      placeholder when empty)
    - diff_excerpt (scrollable monospace block, max 40rem)
* Hardened `approveDisabled`:
    ```ts
    fileApplyMissingPreview =
      meta.is_file_apply &&
      (!preview ||
       !preview.target_repo_relative ||
       preview.change_type !== 'modify' ||
       preview.tests_to_run_after_apply.length === 0 ||
       !preview.secret_file_check_passed ||
       !preview.outside_repo_check_passed)
    approveDisabled = busy != null || hashMissing || fileApplyMissingPreview
    ```
  Even if the backend would refuse, the client-side button stays
  disabled. The brief's "no approve without preview / tests / for
  secret files / for delete" is enforced at modal render time.

`frontend/src/pages/GovernanceApprovalsPage.tsx` (modified):

* `openPhase3Modal` extracts `action_params.file_apply_preview` with
  full type-safety (each field validated as the right primitive).
* Defaults safe: missing booleans default to `false` for the path
  checks (so missing data fails the wall, never opens it).

`frontend/src/pages/GovernanceAuditPage.tsx` (modified):

* `CONTROLLED_TOOL_IDS` grows from 4 to 5 -- adds
  `local.file_change_proposal.apply`. The audit "Phase 3 only"
  filter and the controlled-execution detail panel now both
  include apply rows.

## Locked invariants

| Invariant | Where |
|---|---|
| Apply approval requires preview | `fileApplyMissingPreview` derivation |
| Approve disabled if change_type != "modify" | same |
| Approve disabled if no tests_to_run | same |
| Approve disabled if secret-file check failed | same |
| Approve disabled if outside-repo check failed | same |
| Banner says "This modifies local repo files" | literal in source |
| Diff excerpt rendered before approve | DOM order |
| Backup path visible | dl row |
| Both hashes visible | dl rows |
| Rollback default mentions backup + separate commit | TOOL_META.rollback_default |

## Hard rules audit (per the brief)

| Rule | Status |
|---|---|
| Show target file | enforced (dl row + test-id) |
| Show diff preview | enforced (diff_excerpt block) |
| Show current_file_hash + approved_diff_hash | enforced |
| Show backup path | enforced |
| Show rollback patch summary | enforced (rollback default + audit row) |
| Show tests to run | enforced (list rendered) |
| Show secret/path checks | enforced (two pills) |
| Warning: "This modifies local repo files" | enforced (banner) |
| No approve without preview | enforced (approveDisabled) |
| No approve without tests_to_run_after_apply | enforced |
| No approve for secret files | enforced |
| No approve for delete | enforced (change_type != "modify" disables) |

## Tests

Frontend type-check: `npx tsc --noEmit` exits 0.

UI invariants are encoded in source as locked literals; PR-7 smoke
will exercise the modal via Playwright.

## Files

```
modified:   frontend/src/components/governance/Phase3ApprovalModal.tsx
modified:   frontend/src/pages/GovernanceApprovalsPage.tsx
modified:   frontend/src/pages/GovernanceAuditPage.tsx
new:        docs/Ultraview/PR_FILE_APPLY_APPROVAL_MODAL_REPORT.md
```

## Next: PR-3 -- Self-Healing Patch Proposal Generator
