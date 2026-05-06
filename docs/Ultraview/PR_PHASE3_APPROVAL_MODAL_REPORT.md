# PR-6 -- Phase 3 Approval Modal

**Sprint:** DAENA-PHASE3-CONTROLLED-WRITES-SPRINT-14
**PR:** 6 of 7
**Date:** 2026-05-06

## Goal

Render the rich approval surface for any GoaRequest whose
`action_type` is one of the Sprint-14 controlled-execution tools.
The operator sees the full payload, the canonical hash, the Asset
Shield result, and the rollback instruction BEFORE clicking
approve.

## What ships

`frontend/src/components/governance/Phase3ApprovalModal.tsx` (new):

* Props: `open`, `onClose`, `details`, `onApprove(note)`, `onReject(reason)`.
* Renders:
  - Tool pill (`gmail.create_draft` / etc.)
  - Owner email pill
  - Risk class pill (low / medium)
  - Asset Shield row (pass = green ShieldCheck; fail = rose ShieldAlert)
  - Payload hash (truncated `{first16}…{last8}`; rose "missing" when bad)
  - Payload preview (formatted JSON, scrollable, monospace)
  - Rollback / undo instruction (verbatim or default-per-tool)
  - Audit-note textarea
  - Approve + Reject buttons

### Locked invariants

| Invariant | Where |
|---|---|
| Approve disabled when `payload_hash` is missing or != 64 chars | `approveDisabled = busy != null \|\| hashMissing` |
| Reject requires a non-empty audit note | button disabled when `!note.trim()` |
| Payload preview rendered before action buttons | DOM order |
| No one-click hidden execution | both buttons explicitly call onApprove/onReject; no auto-submit |

`PHASE3_TOOL_IDS` is a closed tuple of the three Sprint-14 tools.
`isPhase3ToolId(action_type)` is the type-guard the page uses to
decide whether to open this modal.

### Wired into GovernanceApprovalsPage

`frontend/src/pages/GovernanceApprovalsPage.tsx`:

* Imports the modal + helper.
* Adds `phase3Details` state + `submitPhase3Decision` helper.
* `handleAction(id, "approve")` first checks
  `isPhase3ToolId(approval.action_type)`. If true, opens the rich
  modal. Otherwise falls through to the existing `promptDialog`
  flow (legacy approvals unchanged).
* Modal is rendered at the bottom of the page tree, controlled by
  `phase3Open`.

The decision still routes to the same
`POST /governance/approvals/{id}/decide` endpoint -- no new backend
surface.

## Tests

Frontend type-check: `npx tsc --noEmit` exits 0.

This PR ships UI without a dedicated unit test file because the
component's invariants are encoded in the source as locked literals
(`PHASE3_TOOL_IDS`, `approveDisabled` derivation, button disabled
predicates). The Sprint-14 PR-7 smoke spec exercises the modal via
Playwright.

## Hard rules audit

| Rule | Status |
|---|---|
| Approval modal shows tool / account / payload / hash / risk / Asset Shield / rollback | enforced -- every field rendered |
| No one-click hidden execution | enforced -- explicit Approve button |
| No approval without preview | enforced -- preview rendered before footer |
| No approval if payload hash missing | enforced -- approveDisabled = hashMissing |

## Files

```
new:        frontend/src/components/governance/Phase3ApprovalModal.tsx     (220 lines)
modified:   frontend/src/pages/GovernanceApprovalsPage.tsx                 (+62 lines: imports + wiring + modal mount)
new:        docs/Ultraview/PR_PHASE3_APPROVAL_MODAL_REPORT.md
```

## Next: PR-7 -- Sprint-14 Smoke + Final Report
