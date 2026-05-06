# PR-3 -- Business Workstream Generator

**Sprint:** DAENA-AUTONOMOUS-BUSINESS-OPERATOR-SPRINT-13
**PR:** 3 of 9
**Date:** 2026-05-06
**Author:** Mythos (Daena, via Claude Code)

## Goal

Turn a discovered business opportunity into a Workstream
automatically, with the right department picked from the closed
`opportunity_type` set and a deterministic next-step text. No
external action.

## What ships

### Backend

`backend/app/api/v1/workstreams.py` `POST /workstreams/from-draft`
extended:

* Accepts `draft_kind="business_opportunity"`.
* Loads the opportunity draft from `ResearchDraft` filtered by kind.
* Picks the department deterministically from the new
  `_OPPORTUNITY_TYPE_TO_DEPARTMENT_NAME` map:

| opportunity_type | default department |
|---|---|
| grant | Finance |
| accelerator | Operations |
| hackathon | Engineering |
| freelance | Sales |
| customer | Sales |
| partnership | Sales |
| security_bounty | Security Operations |
| rfp | Sales |
| content | Marketing |
| startup_program | Operations |

* Legal-flag heuristic still wins -- if the draft text contains
  `legal / compliance / regulat / license / patent / litigation /
  liability / gdpr / ccpa`, the workstream lands in **Legal &
  Compliance** instead.
* Manual `department_override` still wins over both.

### Initial context + next step

For `business_opportunity` workstreams the workstream's
`initial_context` carries:

```ts
{
  draft_kind: "business_opportunity",
  draft_ref: <draft.id>,
  department_routed_by: "override" | "legal_flag" | "kind_default" | "opportunity_type_map",
  llm_pending: bool,
  llm_failed: bool,
  opportunity_type: string,
  deadline: string | null,
  fit_score: number | null,
  risk_level: string | null,
  confidence: number | null,
}
```

`next_step_text` is derived deterministically:

| Condition | next_step_text |
|---|---|
| `next_action` set | `next_action` (capped at 500) |
| `_llm_pending=true` | "Run /enrich on this opportunity to score fit, deadline, and next action before drafting outreach." |
| `deadline` set | "Review eligibility before deadline: {deadline}" |
| else | "Review eligibility and decide whether to pursue this opportunity locally." |

### CLAUDE.md Rule 2 upheld

Reuses `POST /workstreams/from-draft` and the canonical
`WorkstreamService.start()` path. No `/from-opportunity` parallel
endpoint. No `OpportunityWorkstream` model.

## Tests

`backend/tests/test_workstream_from_opportunity.py` -- 5 tests:

```
TestOpportunityDepartmentMap::test_covers_every_opportunity_type
TestOpportunityDepartmentMap::test_no_orphan_department_names
TestOpportunityDepartmentMap::test_security_bounty_routes_to_security_ops
TestOpportunityDepartmentMap::test_grant_routes_to_finance
TestKindAccepted::test_business_opportunity_in_kind_default_map
```

The first two are the contract: every value in
`research_flow.ALLOWED_OPPORTUNITY_TYPES` must appear in the dept
map; every dept name must exist in `core.constants.SEED_DEPARTMENTS`.
Adding a type without extending the map fails CI.

Sanity regression check: existing `test_workstream_from_draft.py`
(11 tests) still passes alongside (34/34 on the combined fast
subset).

## Hard rules audit

| Rule | Status |
|---|---|
| No external action | enforced -- workstream is a local plan; no send / submit / apply path exists |
| Deterministic department routing | full closed map, contract-tested |
| Legal & Compliance override stays in force | unchanged |
| Manual override still wins | unchanged |
| No duplicate endpoint | extended `/from-draft`, no new route |
| Audit per call | inherits the existing `workstream.from_draft` audit row |

## Files

```
modified:   backend/app/api/v1/workstreams.py             (+45 lines)
new:        backend/tests/test_workstream_from_opportunity.py  (75 lines, 5 tests)
new:        docs/Ultraview/PR_BUSINESS_WORKSTREAM_GENERATOR_REPORT.md
```

## What this PR does NOT do

- Does NOT auto-promote opportunity drafts. The operator (or a future
  autonomous loop in PR-6) calls the endpoint.
- Does NOT seed task rows on the workstream. PR-4 ships the draft
  action factory which authors the per-stage drafts (eligibility
  research, application draft, QE review, approval queue).
- Does NOT cross-check `opportunity_type` against the original draft
  payload's `_kind`. The closed set + legal-flag heuristic is the
  guard.

## Next: PR-4 -- Draft Action Factory + Trust Ladder
