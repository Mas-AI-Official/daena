# PR-5 -- Phase 3 Send UX Reliability Polish

**Sprint:** DAENA-SPRINT-16-SEND-INTEGRITY-AND-LIVE-GOOGLE-PROOF
**PR:** 5 of 6
**Date:** 2026-05-06

## Goal

Make the Phase 3 UI impossible to misunderstand. Surface the
snapshot hash + capture time in the approval modal so the operator
can match the modal to the audit log byte for byte; render a
dedicated Phase 3 panel in the audit detail view so refusal codes
and snapshot integrity proofs are visible at a glance.

## What ships

`frontend/src/components/governance/Phase3ApprovalModal.tsx`
(modified):

* `Phase3DraftPreview` interface gains two optional fields:
    - `snapshot_captured_at: string | null`
    - `snapshot_hash: string | null`
* The send-mode draft snapshot block now renders two extra rows
  when those fields are present:
    - `Captured:` -- ISO timestamp from
      `action_params.draft_snapshot.captured_at`
    - `Hash:` -- 16+8 truncation of the snapshot hash, with full
      value in the `title` tooltip and a stable test-id
      `phase3-send-draft-snapshot-hash`

`frontend/src/pages/GovernanceApprovalsPage.tsx` (modified):

* `openPhase3Modal` now reads both shapes:
    - `action_params.draft_preview` (Sprint-15 UI-shaped key)
    - `action_params.draft_snapshot` (Sprint-16 contract key)
* Whichever has the field wins, with `draft_snapshot` taking
  precedence for `captured_at` (only it carries that field).
* `draft_snapshot_hash` is read from
  `action_params.draft_snapshot_hash` (the upstream creator is
  responsible for setting this; the hash itself is computed by
  the backend's `compute_draft_metadata_hash` from the
  snapshot dict and stored alongside it).

`frontend/src/pages/GovernanceAuditPage.tsx` (modified):

* New `Phase 3 controlled execution` panel rendered in the audit
  detail view for any row whose `action_type` matches
  `isControlledExecutionRow(...)`. Renders:
    - Tool id (violet)
    - Owner email
    - Recipient (`audit_to`)
    - Subject (`audit_subject`, truncated to 120 chars + ellipsis)
    - Payload hash (16-char prefix)
    - Approved snapshot hash (emerald)
    - Verified snapshot hash (emerald when matches approved,
      rose when drift -- though drift would never reach the audit
      log because the dispatcher refuses)
    - Refusal code (rose) when present
* Stable test-ids `audit-detail-approved-snapshot-hash` /
  `audit-detail-verified-snapshot-hash` for smoke selection.
* Panel only renders when the row is a controlled-execution row,
  so non-Phase-3 audit rows are unaffected.

## Locked invariants

| Invariant | Where |
|---|---|
| Send approval shows snapshot capture time | modal `phase3-send-draft-captured-at` test-id |
| Send approval shows snapshot hash | modal `phase3-send-draft-snapshot-hash` test-id |
| Audit row shows BOTH approved + verified hashes | audit page `audit-detail-{approved,verified}-snapshot-hash` test-ids |
| Audit row shows refusal code when present | new panel renders refusal_code in rose |
| Hash colour reflects integrity match | emerald when approved == verified, rose otherwise |
| Both UI shapes (draft_preview, draft_snapshot) accepted | page extractor falls back gracefully |

## Hard rules audit (per the brief)

| Rule | Status |
|---|---|
| Draft creation vs Send visually different | enforced (Sprint-15 PR-3 banner + Sprint-16 PR-5 snapshot rows) |
| "This sends externally" warning for send | enforced (Sprint-15 PR-3 irrevocability banner) |
| "Email cannot be unsent" warning | enforced (modal rollback default + handler result) |
| Current OAuth account visible | enforced (owner_email pill + audit panel) |
| Snapshot time visible | NEW (Sprint-16 PR-5) |
| Recipient / subject / snippet visible | enforced (Sprint-15 PR-3 + Sprint-16 PR-5) |
| Payload hash visible | enforced |
| Asset Shield pass/fail visible | enforced |
| Exact refusal reason visible | NEW (audit panel renders refusal_code) |
| Audit viewer shows snapshot hash | NEW (Sprint-16 PR-5) |
| Audit viewer shows send result | enforced (entry.result column unchanged) |
| Audit viewer shows refusal code if mismatch | NEW (Sprint-16 PR-5 panel) |

## What is NOT in this PR

* **No backend changes.** The modal + audit panel render fields
  the upstream creator + handler are already responsible for
  populating. PR-1 + PR-2 already shipped the producer side; PR-5
  is the consumer.
* **No drift simulation.** Drift would have caused dispatch to
  refuse, so it never appears in the audit success path. The
  rose styling is reserved for the rare case where someone
  hand-edits an audit row out of sequence.

## Tests

Frontend type-check: `npx tsc --noEmit` exits 0.

The PR ships UI without dedicated unit tests because the modal
component's invariants are encoded in source as locked literals
(`PHASE3_TOOL_IDS`, `approveDisabled` derivation, button-disabled
predicates). The audit panel is a pure render of action_params
fields; PR-6 smoke verifies it renders.

## Files

```
modified:   frontend/src/components/governance/Phase3ApprovalModal.tsx
modified:   frontend/src/pages/GovernanceApprovalsPage.tsx
modified:   frontend/src/pages/GovernanceAuditPage.tsx
new:        docs/Ultraview/PR_PHASE3_SEND_UX_RELIABILITY_POLISH_REPORT.md
```

## Next: PR-6 -- Sprint-16 Smoke + Final Report
