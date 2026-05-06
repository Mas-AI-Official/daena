# PR-3 -- Opportunity-to-Workstream Completion

**Sprint:** DAENA-SPRINT-20-LIVE-BUSINESS-OPS-ACTIVATION
**PR:** 3 of 8
**Date:** 2026-05-06

## Goal

Close the Sprint-19 gap. An opportunity sitting in the inbox with no
owner is just a row; a workstream owned by a department with a goal,
context, decision log, and audit trail is real work. PR-3 makes
promotion the first-class action available on every discovered
opportunity, with a deterministic type-to-department map and a hard
ban on duplicate promotion.

## What ships

`backend/app/models/workstream.py`:
* `WorkstreamSourceType.OPPORTUNITY` added to the closed enum so the
  frontend's source badge map and the spine inventory stay in sync.

`backend/app/services/business_pipeline/workstream_bridge.py` (new):
* `OPP_TYPE_TO_PRIMARY_DEPT` -- locked map. Every opportunity type
  has exactly one primary department (test pins this).
* `OPP_TYPE_TO_COLLABORATORS` -- locked secondary list per type
  (rendered as workstream context badges in PR-4).
* `create_workstream_for_opportunity(db, *, tenant_id, user_id,
  opportunity_id) -> BridgeResult`.
* Stable refusal codes: `opportunity_not_found`,
  `unknown_opportunity_type`, `department_not_found`,
  `duplicate_workstream`. The API surfaces these verbatim.

`backend/app/api/v1/opportunities.py`:
* New `POST /opportunities/{id}/create-workstream` endpoint mapping
  bridge errors to stable HTTP codes (404/400/409).

`frontend/src/pages/OpportunityInboxPage.tsx`:
* New "Workstream" button on every `discovered` opportunity card.
  Triggers promotion + surfaces the department + workstream id in the
  page summary line.

## Mythos design choices

**One workstream per opportunity.** Two parallel workstreams for the
same opportunity would split ownership and confuse the operator. The
bridge refuses with a stable code + the existing workstream id so the
UI can navigate to the existing workstream rather than producing a
generic error.

**Snapshot opportunity fields into workstream.context.** If the
opportunity row is later mutated (rescoring, status change), the
workstream still carries the values it had AT PROMOTION. This is the
audit-trail rule -- decisions are made with the data that existed at
the time, not the data that exists now.

**Single primary department, collaborators in context.** Routing
fan-out into multiple workstreams is tempting (grant goes to
Finance + Founder Office) but produces ambiguous ownership. One
workstream owns the work; collaborators are tracked in
`context.collaborators` for visibility without splitting accountability.

**Status advance from `discovered` to `queued`.** The opportunity row
shows the operator that promotion happened. `assigned_department` is
also stamped so the inbox card displays the routing decision.

**STARTED event appended.** The Workstream timeline begins with a
visible `STARTED` event carrying the opportunity_id + department +
collaborators. The timeline is the workstream's audit trail; an empty
timeline would mean a workstream existed without a creation reason.

**No external action whatsoever.** The bridge does not import the
controlled execution surface, does not create approval rows, does not
call Gmail / posting / payment. A test greps the source file for
forbidden symbols.

**Deterministic Python, no LLM.** Routing is a closed map. Adding a
new opportunity type without a department mapping fails the contract
test, not at runtime.

## Locked invariants

| Invariant | Where |
|---|---|
| `WorkstreamSourceType.OPPORTUNITY` exists | enum extended |
| Every opportunity type has a primary dept | `TestRoutingMap::test_every_opportunity_type_maps_to_a_department` |
| Routing anchors (grant->Finance, hackathon->Engineering, etc.) | `test_routing_anchors` + per-type tests |
| Bridge refuses unknown opportunity type | `TestRefusals::test_unknown_opportunity_type` |
| Bridge refuses missing department | `test_missing_department` |
| Bridge refuses duplicate promotion | `test_duplicate_promotion_refused` |
| Bridge refuses unknown opportunity id | `test_unknown_opportunity_id` |
| Workstream context snapshots opportunity fields | `TestWorkstreamArtifact::test_workstream_carries_snapshot_context` |
| STARTED event appended | `test_started_event_appended` |
| Bridge creates NO GoaRequest | `TestNoExternalAction::test_bridge_does_not_create_goa_request` |
| Bridge source carries no outbound symbols | `test_bridge_source_grep_for_forbidden_calls` |
| API endpoint returns 200 + workstream_id | `TestApiEndpoint::test_promote_endpoint_returns_workstream_id` |
| API endpoint returns 409 on duplicate | `test_promote_returns_409_on_duplicate` |
| API endpoint returns 404 for unknown opp | `test_promote_returns_404_for_unknown_opportunity` |
| API endpoint returns 400 for bad uuid | `test_promote_returns_400_for_bad_uuid` |

## Hard rules audit

| Rule | Status |
|---|---|
| No external action | enforced -- bridge module greps clean of send/create_draft/controlled_execution |
| No approval row creation | enforced -- bridge does not touch GoaRequest |
| Local workstream only | enforced -- only Workstream + WorkstreamEvent inserts |
| Audit row required | applied -- WorkstreamEvent.STARTED |
| Duplicate refused | enforced -- DuplicateWorkstream raised + tested |
| Department routing deterministic | enforced -- closed map + contract test |

## Tests

```
backend/tests/test_opportunity_workstream_bridge.py   19 tests
```

19/19 pass. `test_opportunities_api.py` (Sprint-19 PR-2 regression)
remains 7/7 green.

## Files

```
modified:   backend/app/models/workstream.py
new:        backend/app/services/business_pipeline/workstream_bridge.py
modified:   backend/app/api/v1/opportunities.py
modified:   frontend/src/pages/OpportunityInboxPage.tsx
new:        backend/tests/test_opportunity_workstream_bridge.py
new:        docs/Ultraview/PR_OPPORTUNITY_TO_WORKSTREAM_COMPLETION_REPORT.md
```

## Next: PR-4 -- Business Loop UI Flow Polish (minimal)
