# PR-4 -- Controlled Execution Audit Viewer Filter

**Sprint:** DAENA-SPRINT-15-GOOGLE-LIVE-AND-FIRST-SEND-UNLOCK
**PR:** 4 of 6
**Date:** 2026-05-06

## Goal

Make every controlled-execution action visible at one click. The
audit log already records every Phase 3 dispatch + refusal; PR-4
adds a one-click "Phase 3 only" filter so the operator can narrow
to those rows without combining other filters.

## What ships

`frontend/src/pages/GovernanceAuditPage.tsx` (modified):

* New module-level constant `CONTROLLED_TOOL_IDS` mirrors the
  backend `WRITE_TOOLS` allowlist (4 entries as of Sprint-15).
* New `CONTROLLED_AUDIT_PREFIX = "controlled_execution."` matches
  the dispatcher's audit-channel prefix used for refusal rows.
* New `isControlledExecutionRow(action_type)` helper returns true
  when the row is either a tool-id match or a dispatcher-channel
  match.
* New `filterControlledOnly: boolean` state.
* New "Phase 3 only" toggle button (Shield icon, violet styling
  when active) sits adjacent to the existing "Filters" button.
* `filtered` memo applies the controlled-only narrow when the
  toggle is on.
* `clearFilters` resets it.
* `hasActiveFilters` includes it so the count badge increments.

The toggle has data-testid `audit-filter-controlled-only` for
Playwright smoke selection.

## What is NOT in this PR (intentionally)

* No new payload-redaction logic. The backend AuditEvent surface
  already enforces secret scrubbing (Sprint-13/14) -- the
  controlled-execution handlers themselves return safe results
  with `access_token` / `refresh_token` paths excluded by
  construction. PR-4 does not need to filter at render-time.
* No body preview truncation. The handler results (`audit_to`,
  `audit_subject`) are short by design; full body is never written
  to the audit row.
* No new backend endpoint. The existing
  `GET /api/v1/governance/audit` already returns
  controlled-execution rows; PR-4 is render-only.

## Rendered fields per the brief

| Field | Source | Visible in row |
|---|---|---|
| tool_id | `entry.action_type` | yes (existing column) |
| approval_id | `entry.action_params.approval_id` | yes (existing params block) |
| consent_grant_id | `entry.action_params.consent_grant_id` | yes |
| owner_email | `entry.action_params.owner_email` | yes |
| payload_hash short | `entry.action_params.payload_hash` (first 16 chars) | yes |
| preflight result | `entry.action_params.audit_preflight_row_id` | yes |
| execution result | `entry.result` | yes (existing column) |
| refusal code | `entry.action_params.refusal_code` (when refused) | yes |
| timestamp | `entry.created_at` | yes (existing column) |
| rollback instruction | `entry.action_params.rollback_or_undo_instruction` | yes |

The existing audit row renderer already displays
`entry.action_params` as a key-value block; controlled-execution
rows therefore surface every field above without page-side code.

## Locked invariants

| Invariant | Where |
|---|---|
| No secret values rendered | enforced -- handler results scrub access_token / refresh_token; backend AuditEvent payload scrubs at write |
| No token values | enforced -- same |
| Filter narrows to controlled-execution rows only | `filterControlledOnly && !isControlledExecutionRow(...)` |
| Tool-id list stays in lockstep with backend | mirrors `WRITE_TOOLS`; PR-6 smoke verifies |
| Toggle has stable test-id | `audit-filter-controlled-only` |

## Tests

Frontend type-check: `npx tsc --noEmit` passes (verified).

The toggle behaviour is testable via Playwright in PR-6 smoke; this
PR ships UI without a dedicated unit test because the filter
predicate is a pure function (`isControlledExecutionRow`) and the
state update is one boolean.

## Hard rules audit

| Rule | Status |
|---|---|
| No secret values | applied -- not added by PR-4 |
| No token values | applied -- not added by PR-4 |
| No full payload if sensitive; preview only | applied -- audit_to / audit_subject are SHORT by handler design |
| Every controlled action visible | enforced -- one-click filter |
| Filter is honest about what it shows | enforced -- both tool-id rows AND dispatcher channel rows show |

## Files

```
modified:   frontend/src/pages/GovernanceAuditPage.tsx
new:        docs/Ultraview/PR_CONTROLLED_EXECUTION_AUDIT_VIEWER_REPORT.md
```

## Next: PR-5 -- File Proposal Apply Design Lock
