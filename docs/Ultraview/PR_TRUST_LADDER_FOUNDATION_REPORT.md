# PR-5 -- Trust Ladder Foundation

**Sprint:** DAENA-PHASE3-CONTROLLED-WRITES-SPRINT-14
**PR:** 5 of 7
**Date:** 2026-05-06

## Goal

Record approval / rejection history per (tool_id, template_id)
pair so a future sprint can graduate trust. PR-5 is record-only;
no auto-execution surface exists.

## What ships

`backend/app/services/trust_ladder.py` (new). Public API:

```python
record_decision(tool_id, template_id, decision="approved"|"rejected") -> TrustLadderEntry
get_entry(tool_id, template_id) -> TrustLadderEntry | None
list_entries() -> list[TrustLadderEntry]
```

`TrustLadderEntry` carries:

```ts
{
  tool_id:           string,
  template_id:       string,
  approvals_count:   int,
  rejection_count:   int,
  last_approved_at:  ISO 8601 | null,
  last_rejected_at:  ISO 8601 | null,
  max_auto_tier:     string  // operator-controlled; PR-5 NEVER raises
}
```

Persistence: `backend/.trust_ladder.json` (gitignored). Single-file
JSON is sufficient for the founder install. Cloud multi-tenant
will move this to a DB table; that's a future migration.

### What's intentionally absent

The contract test `TestNoAutoExecutionSurface` walks the module's
public callables and asserts none are named `execute / auto_execute
/ apply / run / auto_approve / auto_reject`. PR-5 is data only.

`TestNoAutoTierEscalation` records 12 consecutive approvals and
asserts `max_auto_tier` stays at the default `"none"`. Sprint-15+
graduation must read these counters and set `max_auto_tier`
explicitly -- never auto-raised by record_decision.

## Tests

`backend/tests/test_trust_ladder.py` -- 5 tests:

```
TestRecordDecision::test_approved_then_rejected_round_trip
TestNoAutoTierEscalation::test_max_auto_tier_stays_default_after_many_approvals
TestInvalidInputs::test_unknown_decision_value_raises
TestGitignored::test_persistence_file_in_gitignore
TestNoAutoExecutionSurface::test_no_auto_execute_function
```

Combined Sprint-14 fast subset: 55/55 pass.

## Files

```
new:        backend/app/services/trust_ladder.py            (180 lines)
modified:   backend/.gitignore                              (+1 line: .trust_ladder.json)
new:        backend/tests/test_trust_ladder.py              (130 lines, 5 tests)
new:        docs/Ultraview/PR_TRUST_LADDER_FOUNDATION_REPORT.md
```

## Next: PR-6 -- Phase 3 Approval Modal
