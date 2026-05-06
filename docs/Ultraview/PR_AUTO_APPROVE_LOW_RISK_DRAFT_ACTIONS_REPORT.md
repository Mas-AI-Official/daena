# PR-3 -- Auto-Approve Low-Risk Draft Actions

**Sprint:** DAENA-SPRINT-18-TRUST-LADDER-AND-ROUTINE-AUTONOMY
**PR:** 3 of 6
**Date:** 2026-05-06

## Goal

Wire `trust_policy.should_auto_approve` into the GoaRequest
lifecycle. When all six trust walls pass for a freshly-created
approval row, the helper mutates the row to status="APPROVED"
in-place with `decision_reason="trust_graduated:<template_class>"`.
The operator never sees a modal; the dispatcher's gate 4 finds an
already-approved row and proceeds.

## What ships

`backend/app/services/trust_auto_approve.py` (new):

* `maybe_apply_trust_auto_approval(db, *, approval, payload,
  initiator, decided_by) -> AutoApprovalDecision`
* Mutates the in-session `GoaRequest` only when ALL six walls
  pass. Otherwise leaves status="PENDING".
* NEVER raises -- returns the decision struct so the caller can
  audit-log the reason regardless.
* NEVER touches `trust_ladder` counters. Auto-approvals are the
  *consequence* of operator review history, not new entries in it.

## Mythos design choices

**Auto-approval does NOT inflate the ladder.** The ladder records
GENUINE operator decisions only. If we re-recorded on auto-approve,
counters would compound and "5 approvals = graduate" would mean
"5 operator approvals OR 5 auto-approvals" -- the trust signal
would degrade into noise. Wall: `trust_ladder.record_decision` is
called from the approve / reject endpoint paths only. This module
NEVER calls it.

**In-place mutation rather than separate "auto-approval" table.**
The dispatcher's gate 4 already reads `GoaRequest.status`. By
mutating the row to APPROVED in the same flush, we reuse the
existing dispatch path with zero changes. Auditability is preserved
because `decision_reason` carries the explicit
`trust_graduated:<template_class>` sentinel -- a query against
`goa_requests WHERE decision_reason LIKE 'trust_graduated:%'`
returns every auto-approval ever made.

**Initiator parameter required, not defaulted.** Caller MUST pass
`DispatchInitiator.OPERATOR / SCHEDULER / SELF_HEALING / DELEGATED`.
There is no implicit default. This forces every wiring site to
think about who started the dispatch -- which is the only thing
keeping scheduler-initiated drafts from quietly auto-approving.

**Helper NEVER raises.** Every reasonable failure mode (missing
payload, unknown tool, flush error) returns a decision struct
with `auto_approve=False`. Future autonomous loops can compose
this helper without try/except scaffolding.

## Locked invariants

| Invariant | Where |
|---|---|
| Forbidden tool never auto-approves | `TestForbiddenToolNeverAutoApproves` (3 parametric cases) |
| Scheduler initiator blocked even when policy open | `test_scheduler_blocked_even_when_policy_open` |
| Eligible tool with all walls passing flips status to APPROVED | `TestHappyPath::test_all_walls_pass_mutates_approval` |
| Auto-approval does NOT inflate ladder counters | same test asserts pre/post `approvals_count` equal |
| `decision_reason` carries `trust_graduated:` prefix | same test |
| `decided_at` and `decided_by` are stamped | same test |
| Empty payload does NOT raise, returns auto_approve=False | `TestNeverRaises::test_missing_payload_does_not_raise` |
| Unknown tool returns `tool_not_in_eligible_set` | `test_unknown_tool_does_not_auto_approve` |

## Hard rules audit

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied |
| No submit / post / pay surface unlocked | applied -- this PR adds nothing to WRITE_TOOLS |
| No file delete | applied |
| No multi-file apply | applied |
| Auto-approve does NOT execute | applied -- helper only flips status; caller still has to invoke dispatcher |
| Forbidden tools cannot graduate | enforced via `should_auto_approve` walls + tested with all 3 forbidden tool ids |
| Scheduler / self-healing / delegated never graduate | enforced via wall #2 + tested |
| Trust counters not inflated by auto-approval | enforced -- helper does not call `trust_ladder.record_decision` + tested |
| Daena cannot raise own tier | unchanged -- this PR uses `set_max_auto_tier` for setup only in tests |

## Tests

```
backend/tests/test_trust_auto_approve.py   7 tests
```

7/7 pass. Backend regression: every prior Sprint-18 + Sprint-17
test still passes.

## Files

```
new:        backend/app/services/trust_auto_approve.py
new:        backend/tests/test_trust_auto_approve.py
new:        docs/Ultraview/PR_AUTO_APPROVE_LOW_RISK_DRAFT_ACTIONS_REPORT.md
```

## Note on integration

This PR ships the helper + test contract but does NOT yet wire it
into a specific call site (e.g. the chat orchestrator's draft-creation
flow). Integration is intentionally Sprint-18 PR-4 / PR-5 work --
when the routine autonomy scheduler and VP chat commands land, they
will call `maybe_apply_trust_auto_approval` at the GoaRequest creation
seam. Until then, the helper is dormant: it exists, it is tested,
and any future caller can adopt it with one line.

## Next: PR-4 -- Routine Autonomy Scheduler skeleton
