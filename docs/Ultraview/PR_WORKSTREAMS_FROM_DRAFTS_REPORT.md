# Sprint-12 PR-4 — Workstreams from drafts

**Sprint:** DAENA-FULL-POTENTIAL-ACCELERATION-SPRINT-12
**PR:** 4 of 6
**Date:** 2026-05-05
**Author:** Mythos (Daena, via Claude Code)

## Goal

Promote an enriched (and ideally QE-reviewed) draft into a real
local Workstream so the operator can plan + track follow-up work
without re-keying context. NEVER triggers an external action -- the
workstream is a LOCAL plan; any subsequent send / submit / apply is
operator-driven.

## Files

```
modified:   backend/app/models/workstream.py            (+ DRAFT enum value)
modified:   backend/app/api/v1/workstreams.py           (+ /from-draft)
new:        backend/tests/test_workstream_from_draft.py
new:        docs/Ultraview/PR_WORKSTREAMS_FROM_DRAFTS_REPORT.md
```

## Architecture decision

The brief read: "Add `source_type='draft'`. Do not reuse `task`."

The existing `WorkstreamSourceType` enum already had MANUAL, CHAT,
SCAN, TASK, DEPARTMENT, COMPANY_MODE, DEV_DEMO. We add `DRAFT`
alongside them. The Workstream model's `source_ref_id: UUID` carries
the ResearchDraft.id or FormDraft.id; the routing decision lives in
`Workstream.context["draft_kind"]` ∈ `{"career","content","form"}`.

CLAUDE.md Rule 2 upheld: no parallel `Plan` / `WorkBundle` model.
The Workstream is the canonical unit of operator-visible autonomy
per the Council R3 lock (2026-04-25).

## Endpoint

```
POST /api/v1/workstreams/from-draft
Body: {
  "draft_kind": "career" | "content" | "form",
  "draft_ref":  "<uuid of ResearchDraft or FormDraft>",
  "goal": "<optional override; falls back to draft.goal>",
  "department_override": "<optional dept name override>"
}
Auth: standard tenant + user scoping (any role with the draft).
```

Response (201):

```json
{
  "success": true,
  "data": { ...standard Workstream serialization... }
}
```

The serialized Workstream includes `source_type="draft"`,
`source_ref_id="<draft uuid>"`, and `context` carrying
`draft_kind`, `draft_ref`, `department_routed_by`, plus
kind-specific hints (seeded next_tasks for ResearchDraft;
form_field_count + form_blocked_count + form_needs_review_count
for FormDraft).

## Department routing

| Draft kind | Default department | Trigger |
|---|---|---|
| `career` | Sales | brief: "Sales / Career OPS" |
| `content` | Marketing | brief: "Marketing / ContentOps" |
| `form` | Operations | brief: "Operations / Founder Office" |
| any | **Legal & Compliance** | `_looks_legal()` returns True (token scan over `goal` + safe payload fields) |
| any | operator-chosen | `department_override` always wins |

Routing reason is recorded in
`workstream.context["department_routed_by"]` ∈
`{"override", "legal_flag", "kind_default"}`. The operator can see
why a workstream landed where it did.

`_looks_legal()` is a deterministic regex-style token scan over a
small whitelist of payload fields (`fit_rationale`,
`outreach_draft_local`, `claims_to_verify`, `risks_to_verify`,
`next_tasks`, `missing_skills`). NO LLM call is made here -- the
routing decision is fast + repeatable. Tokens scanned:
`legal | compliance | regulat | license | licence | patent |
litigation | liability | gdpr | ccpa`.

## Deterministic next-step seeding

The brief asked for "Workstream with tasks/next steps". For PR-4
we seed deterministically (no LLM call -- enrichment-time reasoning
already happened in PR-1):

* **ResearchDraft (career/content)**: if
  `structured_payload.next_tasks` is populated (filled by PR-1
  enrichment), the first task becomes `workstream.next_step_text`
  and the full list lands in `context.seeded_next_tasks`. If
  enrichment has not run yet (`_llm_pending=true`), the next-step
  text says "Run /enrich on this draft before promoting next steps."
* **FormDraft**: counts blocked + needs_review fields and writes a
  next-step text describing what the operator needs to fill manually.
  e.g. `"1 sensitive/payment field(s) require manual fill; 1 other
  field(s) flagged for review."`

## Hard rules — encoded + tested

| Rule | How |
|---|---|
| No external action | endpoint creates a Workstream row only; WorkstreamService.start() emits a STARTED event but no outbound network |
| Tenant + user scoping | both ResearchDraft + FormDraft lookups filter by `tenant_id == user.tenant_id AND user_id == user.id` |
| Department must exist | unseeded tenant → `409 department_not_seeded` |
| One audit row per call | `workstream.from_draft` ALLOWED on success (the WorkstreamService internal STARTED event is a separate audit signal) |
| Deterministic kind→dept map | tested with explicit assertions; legal flag tested with claim list |
| Override wins | tested -- operator forcing Operations on a career draft is honoured |
| No /submit /send /apply route | endpoint is `/from-draft` -- existing source-text negative test continues to pass |
| Phase 3 writes blocked | this PR doesn't touch any integration tool; `INTEGRATIONS_PHASE2_READONLY=true` is unchanged |

## Tests

**11/11 pass** in `test_workstream_from_draft.py`:

| Class | Asserts |
|---|---|
| `TestDepartmentRouting` | career→Sales, content→Marketing, form→Operations |
| `TestLegalAndOverride` | legal token in claims_to_verify routes to "Legal & Compliance"; department_override wins over auto-routing |
| `TestSourceAttribution` | source_type=DRAFT, source_ref_id=draft.id, context carries draft_kind + draft_ref + routing reason; ResearchDraft seeds next_tasks; FormDraft records counts |
| `TestAudit` | workstream.from_draft audit row written ALLOWED |
| `TestNegativePaths` | unknown kind→400; another user's draft→404 (tenant + user-scoped); unseeded department→409 with stable error code |

**Combined Sprint-11 + Sprint-12A + Sprint-12 PR-1..PR-4 regression:
167/167 pass.**

## Hard-rule audit

| Rule | Status |
|---|---|
| No deploy | ✅ |
| No push | ✅ |
| No secrets printed/read/committed | ✅ |
| No external action | ✅ — local Workstream row + audit only |
| No browser automation | ✅ |
| Phase 3 writes blocked | ✅ |
| Audit per call | ✅ |
| Deterministic routing (no LLM call) | ✅ — token scan + override |
| Tenant + user scoped | ✅ — both draft fetches filter on user.id |

## What this PR does NOT do

* No automatic workstream creation. Operator triggers via the
  endpoint -- a /from-draft button on the Workstreams page or a chat
  command (PR-5).
* No multi-task breakdown. The workstream is one row + a seeded
  `next_step_text`. Decomposing into Tasks is a downstream concern
  served by existing `Task` model + workstream sub-services.
* No re-promotion guard. If the operator promotes the same draft
  twice, two workstreams are created. Today's workstream context
  carries `draft_ref`; a list-by-draft index can be added later.

## Next: PR-5 Chat commands for VP work

Wire `"Daena, review this opportunity"` /
`"Enrich this draft"` / `"Create a work plan from this"` /
`"What should I do next?"` / `"Run council on this draft"` into the
chat orchestrator so the operator can drive the whole loop without
ever opening the API surface manually.
