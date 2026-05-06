# PR-4 -- Draft Action Factory

**Sprint:** DAENA-AUTONOMOUS-BUSINESS-OPERATOR-SPRINT-13
**PR:** 4 of 9
**Date:** 2026-05-06
**Author:** Mythos (Daena, via Claude Code)

## Goal

For each business-opportunity workstream, suggest the per-stage
local action drafts the operator (or a future trust-graduated
autonomous loop) needs to produce. Daena proposes; never
auto-executes.

## What ships

`backend/app/services/draft_action_factory.py` (new). One pure
function:

```python
suggested_action_drafts(opportunity_type: str) -> list[dict]
```

Returns the deterministic action draft suggestions for a closed-set
opportunity type:

| opportunity_type | Suggested action drafts (in order) |
|---|---|
| grant | grant_application, partnership_pitch |
| accelerator | program_application, partnership_pitch |
| hackathon | hackathon_entry, content_brief |
| freelance | customer_proposal, cold_email |
| customer | cold_email, linkedin_msg, customer_proposal |
| partnership | partnership_pitch, cold_email |
| security_bounty | bounty_report |
| rfp | rfp_response |
| content | content_brief |
| startup_program | program_application |

### Locked draft shape

```ts
{
  id:                 "<opportunity_type>:<action_kind>"  // stable
  kind:               ActionDraftKind                      // closed enum
  title:              string
  rationale:          string
  requires_approval:  true                                 // locked
  delivery:           "manual_only"                        // locked
  payload_hash:       null                                 // Phase 3 fills
}
```

The shape is locked: no `send / submit / apply / post_to_ / publish /
pay_ / payment` field is allowed. The contract test sweeps every
opportunity_type's draft list and asserts no forbidden field-name
appears.

### Wired into the workstream timeline

`POST /workstreams/from-draft` for opportunity drafts now adds:

```ts
initial_context.seeded_action_drafts: ActionDraft[]
```

The Workstreams console reads `initial_context.seeded_action_drafts`
and renders them as a "what comes next" preview. The drafts are
metadata only -- they do NOT seed real `Task` rows or `FormDraft` /
`ResearchDraft` rows yet. PR-8 (Controlled Execution Design Lock)
designs the wiring; nothing in this PR sends, submits, or applies
anything.

### CLAUDE.md Rule 2 upheld

Single canonical factory. No parallel `OutreachFactory` /
`ProposalFactory` modules. No new model. Reuses the existing
`Workstream.context` JSONB column.

## Tests

`backend/tests/test_draft_action_factory.py` -- 6 tests:

```
TestActionKindsClosed::test_kinds_locked
TestCoverage::test_every_opportunity_type_has_actions
TestCoverage::test_unknown_opportunity_type_returns_empty
TestLockedShape::test_keys_locked
TestLockedShape::test_no_forbidden_field_names
TestLockedShape::test_every_draft_requires_approval
TestStableIds::test_id_is_opportunity_type_colon_kind
```

`test_no_forbidden_field_names` is the hard wall: matches exact
field names + prefixes + suffixes against `send / submit / apply /
publish / pay_ / post_to_`. The "pay" check is precise (not a
substring) so legitimate names like `payload_hash` pass.

`test_every_draft_requires_approval` pins the THREE locked fields:
`requires_approval=True`, `delivery="manual_only"`, `payload_hash=None`
-- the "Daena proposes; never auto-executes" rule encoded as data,
not a default.

Sanity regression: 30/30 fast subset pass alongside.

## Hard rules audit

| Rule | Status |
|---|---|
| Daena proposes; never auto-executes | encoded as locked field + tested |
| No send / submit / apply field | enforced + tested |
| No automatic OS install or shell | unaffected -- factory returns metadata only |
| No paid API surface | unaffected |
| Closed action-kind set | enforced + tested |
| Stable proposal id | enforced (`opportunity_type:action_kind`) |
| Phase 3 stays OFF | confirmed -- no write surface here |

## Files

```
new:        backend/app/services/draft_action_factory.py     (135 lines)
modified:   backend/app/api/v1/workstreams.py                (+15 lines: seed initial_context)
new:        backend/tests/test_draft_action_factory.py       (140 lines, 7 tests)
new:        docs/Ultraview/PR_DRAFT_ACTION_FACTORY_REPORT.md
```

## What this PR does NOT do

- Does NOT create real `Task` rows on the workstream. The seeded
  list lives in `initial_context.seeded_action_drafts`. Promoting
  any draft into a real Task with editable body + recipient lives
  in PR-8's Controlled Execution Design Lock.
- Does NOT include a trust-graduation ladder yet. The brief's
  intent (after N approvals on the same template, auto-approve next)
  needs the Phase 3 write spine first; PR-8 stubs that.
- Does NOT render `seeded_action_drafts` in the frontend. The data
  is on the workstream context; future PR adds the timeline UI.

## Next: PR-5 -- Authorized Security Program Scout
