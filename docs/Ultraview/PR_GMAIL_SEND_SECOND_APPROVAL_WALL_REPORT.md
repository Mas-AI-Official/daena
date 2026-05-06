# PR-3 -- Second Approval Wall for Send

**Sprint:** DAENA-SPRINT-15-GOOGLE-LIVE-AND-FIRST-SEND-UNLOCK
**PR:** 3 of 6
**Date:** 2026-05-06

## Goal

Send approval is a SEPARATE wall from create-draft approval. The
create-draft approval authorizes Gmail to hold a draft; the send
approval authorizes Gmail to deliver it. The modal must look and
read DIFFERENTLY so the operator never confuses the two.

## What ships

`frontend/src/components/governance/Phase3ApprovalModal.tsx`
(modified):

* `PHASE3_TOOL_IDS` grows from 3 to 4 -- adds
  `gmail.send_existing_draft`.
* `TOOL_META` adds the new tool with:
    - `risk: "high"`
    - `is_send: true` (new field on the meta dataclass)
    - rose-coloured icon (Lucide `Send`)
    - rollback default: irrevocability text matching the handler's
      result rollback string.
* New `Phase3DraftPreview` interface: optional `{to, subject,
  snippet}` snapshot. The upstream send-approval creator
  captures this at approval-creation time so the modal is honest
  about what is about to leave Gmail.
* New `Phase3ApprovalDetails.draft_preview?: Phase3DraftPreview |
  null` field.
* When `meta.is_send`, two new blocks render at the top of the
  modal body:
    1. A rose-bordered irrevocability banner with the literal copy
       "This will send an email externally". Test-id
       `phase3-send-irrevocability-banner`.
    2. An amber-bordered draft-snapshot block. When
       `details.draft_preview` is non-null it renders a `<dl>` with
       `To`, `Subject`, optional `Snippet`. When null it renders an
       explicit "Draft preview not snapshotted at approval time"
       hint pointing the operator to Gmail Drafts. Test-ids:
       `phase3-send-draft-preview`, `phase3-send-draft-{to,subject,snippet}`,
       `phase3-send-draft-preview-missing`.
* Risk pill colour now branches on `risk: "high"` (rose) /
  `"medium"` (amber) / `"low"` (emerald).

`frontend/src/pages/GovernanceApprovalsPage.tsx` (modified):

* `openPhase3Modal` now extracts `action_params.draft_preview`
  (typing each field as `string | null`) and passes it through to
  the modal.

NO new backend endpoint. The `draft_preview` snapshot is the
RESPONSIBILITY of whichever upstream code creates the send
approval row -- that path doesn't exist yet (it ships in a future
sprint when send-approvals get raised by the agent flow). The
modal handles the missing-snapshot case gracefully.

## Locked invariants

| Invariant | Where |
|---|---|
| Approve disabled when payload_hash missing/non-64 | unchanged from Sprint-14 PR-6 |
| Reject requires non-empty audit note | unchanged |
| Send modal looks different from draft modal | `meta.is_send` branches |
| Irrevocability banner rendered BEFORE detail rows | DOM order |
| Draft preview rendered BEFORE Approve button | DOM order |
| No one-click hidden execution | unchanged |
| Modal handles missing draft_preview gracefully | placeholder block |

## Tests

Frontend type-check: `npx tsc --noEmit` passes (verified during
this PR; PR-6 will re-run as part of smoke).

The existing Sprint-14 PR-6 component invariants remain in source
as locked literals (`PHASE3_TOOL_IDS` is a `readonly` tuple,
`approveDisabled` derivation, button disabled predicates). Adding
the fourth tool grew the tuple at compile time -- a future PR that
forgets to update `PHASE3_TOOL_IDS` would fail TypeScript narrowing
in `openPhase3Modal`.

## Hard rules audit

| Rule | Status |
|---|---|
| Send approval distinct from create-draft approval | enforced -- separate `is_send` styling + banner |
| Modal copy says "This will send an email externally" | enforced -- literal in banner |
| Recipient + subject visible before Approve | enforced -- `<dl>` rows with test-ids |
| Owner email visible | enforced -- pill in header |
| Payload hash visible | unchanged from Sprint-14 PR-6 |
| Asset Shield result visible | unchanged |
| Rollback limitation visible | enforced -- meta.rollback_default + Sprint-14 rollback row |
| Reject button required | unchanged |
| No approval without preview block rendered | enforced -- modal always renders preview row before footer |

## Files

```
modified:   frontend/src/components/governance/Phase3ApprovalModal.tsx
modified:   frontend/src/pages/GovernanceApprovalsPage.tsx
new:        docs/Ultraview/PR_GMAIL_SEND_SECOND_APPROVAL_WALL_REPORT.md
```

## Next: PR-4 -- Audit Viewer Controlled Execution Filter
