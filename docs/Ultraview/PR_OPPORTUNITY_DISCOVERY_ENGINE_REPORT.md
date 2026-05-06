# PR-2 -- Opportunity Discovery Engine

**Sprint:** DAENA-AUTONOMOUS-BUSINESS-OPERATOR-SPRINT-13
**PR:** 2 of 9
**Date:** 2026-05-06
**Author:** Mythos (Daena, via Claude Code)

## Goal

Daena scouts revenue + growth opportunities -- grants, accelerators,
hackathons, freelance jobs, customer leads, partnerships, security
bounty programs, RFPs, content opportunities, startup programs --
and produces local-only opportunity drafts. No applying. No sending.
No scraping behind login.

## What ships

### Backend

`backend/app/services/research_flow.py` (extended). The single
canonical research flow gains a third kind alongside `career` +
`content`:

```python
ResearchKind = Literal["career", "content", "business_opportunity"]
ALLOWED_KINDS = ("career", "content", "business_opportunity")
```

Closed `OpportunityType` set (10 elements):

```
grant, accelerator, hackathon, freelance, customer, partnership,
security_bounty, rfp, content, startup_program
```

Adding a new opportunity type requires touching this tuple AND the
PR-3 department map -- they must move in lockstep.

`build_structured_payload(kind="business_opportunity", ...)` produces
the locked shape:

```ts
{
  _schema_version: "2026-05-05.v1"
  _kind: "business_opportunity"
  _llm_pending: true
  title: null
  opportunity_type: <set by API caller>
  deadline: null              // ISO date or null
  fit_score: null              // 0-100
  revenue_potential: null      // USD estimate or text
  effort_estimate: null        // hours / days
  risk_level: null             // low / medium / high
  next_action: null            // one-line
  suggested_department: null   // PR-3 fills from opportunity_type
  evidence: [source_url]
  source_notes: string[]       // bullets from raw extract
  confidence: null             // 0-100
  sources: [source_url, ...extracted_urls]
  goal_echo: <operator goal>
}
```

`create_research_draft` validates:

| Condition | Error |
|---|---|
| kind=business_opportunity, no opportunity_type | `opportunity_type_required` |
| opportunity_type for non-opportunity kind | `opportunity_type_only_with_business_opportunity_kind` |
| Unknown opportunity_type | `opportunity_type_invalid: <value> not in <set>` |

### API

`POST /api/v1/research/opportunity` (FOUNDER-only, mounted under the
existing `/research/` prefix):

Request:
```json
{
  "url": "https://example.org/grant-page",
  "goal": "extract eligibility and deadline",
  "opportunity_type": "grant",
  "max_chars": 8000
}
```

Response: same `ResearchDraftOut` shape as `/career` and `/content`.

### Frontend

`WorkstreamsPage.tsx` Drafts lane gains an "Opportunities" tab next
to Career / Content / Forms. Reuses the existing draft row renderer
so badges (LLM pending / enriched / QE: full / workstream) render
identically across kinds.

### CLAUDE.md Rule 2 upheld

No parallel `OpportunityDraft` table. The single canonical
`ResearchDraft` carries all kinds via the `kind` column + the
extensible `structured_payload` JSONB. Both the route + the model +
the frontend tab list live in one place.

## Tests

`backend/tests/test_opportunity_discovery.py` -- 8 tests, all pass:

```
TestKindAdded::test_business_opportunity_in_allowed_kinds
TestKindAdded::test_opportunity_types_closed_set
TestStructuredPayload::test_shape_locked
TestStructuredPayload::test_no_send_or_submit_field
TestCreateValidation::test_business_opportunity_requires_type
TestCreateValidation::test_career_refuses_opportunity_type
TestCreateValidation::test_unknown_opportunity_type_refused
TestEndpointMounted::test_opportunity_route_under_v1
```

Sanity regression check: Sprint-13 PR-1 + Sprint-MORNING route
contract pass alongside (31/31 pass on the combined fast subset).

`npx tsc --noEmit` exits 0.

## Hard rules audit

| Rule | Status |
|---|---|
| No applying / submitting | enforced -- `status` field is DRAFT or ARCHIVED only |
| No scraping behind login | inherited from `scrape_service` URL safety + SSRF guard |
| No bypassing anti-bot | inherited from ScrapeGraphAI governed adapter |
| No paid API call | scrape pipeline runs the local llama / Ollama path |
| No external send/post/email | encoded into payload key audit (no send/submit/apply/post/publish/pay key allowed) |
| Stable error codes | every refusal carries a stable prefix (operator+UI matchable) |
| Audit per call | inherits the `plugin.skill_invocation` row from `extract_from_url` |
| No duplicate model | reuses canonical `ResearchDraft` table via `kind=business_opportunity` |

## Files

```
modified:   backend/app/services/research_flow.py        (+82 lines)
modified:   backend/app/api/v1/research.py               (+50 lines)
new:        backend/tests/test_opportunity_discovery.py  (190 lines, 8 tests)
modified:   frontend/src/pages/WorkstreamsPage.tsx       (+10 lines: Opportunities tab)
new:        docs/Ultraview/PR_OPPORTUNITY_DISCOVERY_ENGINE_REPORT.md
```

## What this PR does NOT do

- Does NOT yet auto-discover opportunities from a seed catalog. The
  endpoint accepts one URL per call. PR-3 wires the workstream
  generator that consumes drafts; bulk-scout-from-seed-list lives in
  a follow-up.
- Does NOT score fit / revenue / effort / risk / confidence. Those
  fields are present in the schema but `_llm_pending=true` until the
  enrichment pass writes them.
- Does NOT pick a department. PR-3 reads `opportunity_type` ->
  default department deterministically.
- Does NOT register a VP-command intent for opportunity discovery.
  PR-3 adds `find opportunities of type X` as a vp-command.

## Next: PR-3 -- Business Workstream Generator
