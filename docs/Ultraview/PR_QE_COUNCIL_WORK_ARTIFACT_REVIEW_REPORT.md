# Sprint-12 PR-3 — QE/Council review for work artifacts

**Sprint:** DAENA-FULL-POTENTIAL-ACCELERATION-SPRINT-12
**PR:** 3 of 6
**Date:** 2026-05-05
**Author:** Mythos (Daena, via Claude Code)

## Goal

Run QE/Council review on `ResearchDraft` + `FormDraft` artifacts so
the operator gets honest review output before promoting a draft to a
workstream. Read `/system/qe-readiness` first; mode is reported
HONESTLY (full / degraded / unavailable). NEVER claim "full council"
when the actual run had only one runtime.

## Files

```
new:        backend/app/services/draft_qe_review.py
modified:   backend/app/api/v1/research.py     (+ /drafts/{id}/qe-review)
modified:   backend/app/api/v1/form_drafts.py  (+ /{id}/qe-review)
new:        backend/tests/test_draft_qe_review.py
new:        docs/Ultraview/PR_QE_COUNCIL_WORK_ARTIFACT_REVIEW_REPORT.md
```

## Pipeline (mirrors CLAUDE.md three-stage council)

**Stage 1 — Proposer fan-out (parallel via asyncio.gather)**

Slots used for draft review:

| Slot | Used? | Note |
|---|---|---|
| `local_reasoner` | always | cheap private first-pass |
| `risk_reviewer` | always | hallucinations + missing evidence |
| `web_grounder` | only if `allow_web_grounding=True` AND slot filled | metered Perplexity |
| `code_reviewer` | NEVER for drafts | drafts aren't code |

Each proposer gets a CLEAN, role-scoped system prompt (no DCP
injection, no cognitive lenses — proposers stay light). Output
schema is fixed:

```json
{
  "findings": [...], "objections": [...],
  "missing_evidence": [...], "risk_flags": [...],
  "confidence": 0.55, "notes": "..."
}
```

**Stage 2 — Anonymized synthesis**

The `final_synthesizer` slot reads proposer outputs labelled only
as `Reviewer A / B / C` (no model names, no provider names) and
produces the final summary. Synthesis schema:

```json
{
  "findings": [...], "objections": [...],
  "missing_evidence": [...], "risk_flags": [...],
  "confidence": 0.5,
  "next_action": "operator_review_required",
  "reasoning": "two reviewers agreed"
}
```

If synthesis fails, the service falls back to the **union** of
proposer outputs and sets `next_action="operator_review_required"`.
Never raises in the success path.

## Mode honesty (the "no fake council complete" rule)

The brief: "Never claim full council when mode is degraded/unavailable."

Encoded in code:

```python
if len(distinct) >= 2 and len(successful) >= 2:
    final_mode = "full"
elif successful:
    final_mode = "degraded"
else:
    final_mode = "unavailable"
```

A test pins it: even when `qe_readiness.mode == "full"` in the
snapshot, if all three slots happen to resolve to the SAME runtime,
the run reports `mode="degraded"` with a warning:

> "qe_readiness reported mode='full' but actual run resolved to
> mode='degraded'. Acting on the actual run, not the snapshot."

## Endpoints

```
POST /api/v1/research/drafts/{id}/qe-review
POST /api/v1/form-drafts/{id}/qe-review
Body: {
  "allow_metered": false,           # gate metered_api reviewers
  "allow_web_grounding": false      # gate Perplexity (web_grounder)
}
Auth: FOUNDER role required
```

Response (success, mode=full):
```json
{
  "success": true,
  "draft_id": "...", "draft_kind": "career",
  "mode": "full", "mode_reason": "...",
  "distinct_runtime_ids": ["ollama_backend", "cli_codex", "cli_gemini"],
  "proposer_outputs": [
    {"slot":"local_reasoner","runtime_id":"ollama_backend","cost_class":"free_local",
     "findings":[...], "objections":[...], ...},
    {"slot":"risk_reviewer","runtime_id":"cli_codex","cost_class":"subscription",
     ...}
  ],
  "synthesizer_runtime_id": "cli_gemini",
  "findings": [...], "objections": [...],
  "missing_evidence": [...], "risk_flags": [...],
  "confidence": 0.5,
  "next_action": "operator_review_required",
  "warnings": []
}
```

Refusal (qe_readiness mode=unavailable, OR every slot resolves to a
metered runtime under `allow_metered=False`):

```http
409 Conflict
{"detail":{"code":"qe_council_unavailable","next_action":"<readiness mode_reason>"}}
```

## Hard rules — encoded + tested

| Rule | Enforced where | Tested |
|---|---|---|
| Read `/system/qe-readiness` first | `run_draft_qe_review` line 1 | injected via `qe_readiness` kwarg |
| Mode reported honestly | mode resolution post-Stage 1 | `test_single_runtime_collapses_to_degraded` |
| No fake "full" claim | `if distinct >= 2 AND successful >= 2` | same |
| Web grounder gated | `_DRAFT_REVIEW_PROPOSER_SLOTS` skip when `allow_web_grounding=False` | `test_web_grounder_disabled_by_default` |
| No silent metered call | `_slot_to_routed` returns None for metered when `allow_metered=False` | `test_all_slots_metered_no_allow_refuses` |
| No exposed chain-of-thought | only structured fields surface | schema-locked at coercion |
| No /submit /send /apply route | endpoints are `/qe-review` only | existing negative-route tests still pass |
| Audit one row per call | `AuditService.log_decision` at end | `test_mode_unavailable_refuses` (BLOCKED row); ALLOWED rows asserted indirectly via regression |

## Tests

**10/10 pass** in `test_draft_qe_review.py`:

| Class | Asserts |
|---|---|
| `TestUnavailable` | `mode=unavailable` → `QECouncilUnavailable` raised + BLOCKED audit row |
| `TestModeHonesty` | 2 distinct runtimes both succeed → `mode=full`; same runtime in 3 slots → `mode=degraded` + warning |
| `TestWebGrounding` | `allow_web_grounding=False` skips slot even when filled; Perplexity reply NEVER appears in findings |
| `TestMeteredGate` | every slot metered + `allow_metered=False` → refusal |
| `TestSynthFallback` | synth returns garbage → falls back to union, no raise |
| `TestSlotToRouted` | unit-tests slot resolver: unfilled→None, metered gating, subscription cost_class, unmapped id→None |

**Combined Sprint-11 + Sprint-12A + Sprint-12 PR-1..PR-3 regression: 145/145.**

## Hard-rule audit

| Rule | Status |
|---|---|
| No deploy | ✅ |
| No push | ✅ |
| No secrets printed/read/committed | ✅ |
| No paid API call without explicit allow | ✅ — `allow_metered` + `allow_web_grounding` defended per-slot |
| Honest mode reporting | ✅ — encoded + tested |
| No fake council complete | ✅ — encoded + tested |
| No exposed chain-of-thought | ✅ — structured-only output |
| No /submit /send /apply /post route | ✅ — `/qe-review` only |
| Audit per call | ✅ |
| Phase 3 writes blocked | ✅ |

## What this PR does NOT do

* No automatic QE on draft creation -- operator triggers explicitly.
* No re-ranking / weighting of reviewers -- all reviewers are equal
  in the synthesis. Karpathy peer-ranking can land in a future PR.
* No DCP expert injection -- proposers run with role intent only.
  Quintessence-style expert overlays are not used here because
  drafts don't need them and the brief explicitly excluded
  cognitive-lens overhead from the proposer layer.
* No streaming. One-shot review.

## Next: PR-4 Workstreams from drafts

After QE review, the operator promotes an approved draft to a
workstream. Adds `source_type="draft"` to existing Workstream
schema; `POST /workstreams/from-draft` creates the work plan. No
external action.
