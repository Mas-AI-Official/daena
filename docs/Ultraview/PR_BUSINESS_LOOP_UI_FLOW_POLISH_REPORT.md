# PR-4 -- Business Loop UI Flow Polish (minimal)

**Sprint:** DAENA-SPRINT-20-LIVE-BUSINESS-OPS-ACTIVATION
**PR:** 4 of 8
**Date:** 2026-05-06

## Goal

Make the existing approval-state, source, routing, and rate-limit
information VISIBLE on the Opportunity Inbox page without inventing
new features. Per the Codex peer review of the Sprint-20 plan, this
PR is intentionally minimum -- polish, not redesign.

## What ships

`backend/app/api/v1/opportunities.py`:
* `GET /opportunities/send-rate-limit` returning
  `{today_utc, used, cap, remaining}`. Pure read of the persistent
  counter -- NEVER mutates. Mounted BEFORE `/{opportunity_id}` so
  FastAPI's route matcher does not treat `send-rate-limit` as a
  UUID-shaped path param (verified by tests).

`frontend/src/pages/OpportunityInboxPage.tsx`:
* Header chip showing remaining sends today (`X/Y sends left today`),
  amber when remaining=0.
* `assigned_department` rendered as a gold badge with branch icon on
  every promoted opportunity card.
* Workstream button (PR-3) already in place.

## Mythos design choices

**Visibility, not new features.** The brief listed 7 UI
buttons/states. Most already exist or are PR-3 work. The only NEW
visibility this PR adds:
1. Rate-limit awareness (operator sees the cap before queuing).
2. Department badge (operator sees the routing decision after
   promotion).

That is the minimum to feel like one flow.

**Rate limit shows even if 0/3 used.** Always-visible, not
appears-when-zero. The cap is a feature; the operator sees the budget
constantly.

**Read-only endpoint -- never mutates.** Even five rapid GETs do not
move the counter. Tested.

**Route order is a contract, not coincidence.** A test pins the
fixed path `/send-rate-limit` resolving correctly, so a future PR
adding new path params won't silently break it.

**No "send button" added to the inbox.** External action stays in
the Approvals page. The inbox is for triage + workstream promotion +
draft generation only.

## Locked invariants

| Invariant | Where |
|---|---|
| Endpoint requires auth | `test_requires_auth` |
| Returns expected fields | `test_returns_zero_used_for_fresh_tenant` |
| Reflects increment | `test_remaining_decreases_after_increment` |
| Remaining clamps to 0 | `test_remaining_clamped_at_zero` |
| Endpoint never mutates counter | `test_endpoint_never_mutates_counter` |

## Hard rules audit

| Rule | Status |
|---|---|
| No direct send button without approval | applied -- inbox has no send button |
| No generic send | applied |
| No bulk actions | applied -- per-card buttons only |
| Show rate limit remaining | applied -- header chip |
| Show OAuth blocker clearly | applied (via PR-1 banner already on page) |

## Tests

```
backend/tests/test_opportunities_send_rate_limit_api.py   5 tests
backend/tests/test_opportunities_api.py                   7 tests (regression)
```

12/12 pass. Frontend tsc 0 errors.

## Files

```
modified:   backend/app/api/v1/opportunities.py
modified:   frontend/src/pages/OpportunityInboxPage.tsx
new:        backend/tests/test_opportunities_send_rate_limit_api.py
new:        docs/Ultraview/PR_BUSINESS_LOOP_UI_FLOW_POLISH_REPORT.md
```

## Next: PR-5 -- Safe First Business Outreach Drill (env-flag-gated)
