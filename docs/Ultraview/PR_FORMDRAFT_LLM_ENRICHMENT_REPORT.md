# Sprint-12 PR-2 — FormDraft LLM enrichment

**Sprint:** DAENA-FULL-POTENTIAL-ACCELERATION-SPRINT-12
**PR:** 2 of 6
**Date:** 2026-05-05
**Author:** Mythos (Daena, via Claude Code)

## Goal

Use the routed `main_brain` + optional ResearchDraft context to
suggest LOCAL ONLY answers for `FormDraftField` rows. NEVER autofill
blocked types. NEVER submit. Operator reviews + edits + clicks the
real form's submit themselves.

## Files

```
modified:   backend/app/services/draft_enrichment.py   (already had enrich_form_draft from PR-1)
modified:   backend/app/api/v1/form_drafts.py          (+ /{id}/enrich)
new:        docs/Ultraview/PR_FORMDRAFT_LLM_ENRICHMENT_REPORT.md
```

PR-1 and PR-2 share `draft_enrichment.py` — one canonical service,
two enrichment paths (`enrich_research_draft` and `enrich_form_draft`).
This is intentional and aligns with CLAUDE.md Rule 2 (one canonical
file per concern). The brief explicitly authored both PRs against
the same module.

## Contract enforced

| Rule | How enforced |
|---|---|
| Blocked field types NEVER get suggested_value | `_ENRICHABLE_FIELD_TYPES = {"text","textarea","email","url","phone"}`; loop refuses to write to anything else; adversarial-LLM test proves it |
| No /submit /send /apply /post /publish /dispatch route | Endpoint is `/enrich`; existing test_form_drafts negative assertion still passes |
| No browser autofill | enrichment writes to DB rows only; frontend renders editable cells |
| No payment/sensitive auto-fill | enforced at the field-type level + asserted in tests |
| Low confidence = needs_review | `confidence < 0.6` flips `needs_review=True` |
| Every answer editable | `value` (operator's typed answer) is NEVER touched; only `suggested_value` is filled |
| Audit per call | `draft.enrichment.form` — ALLOWED on success, BLOCKED on refusal |

## Endpoint

```
POST /api/v1/form-drafts/{draft_id}/enrich
Body: {
  "allow_metered": false,
  "research_draft_id": "<optional uuid>"   # optional grounding context
}
Auth: FOUNDER role required
```

Response (success):
```json
{
  "success": true,
  "draft_id": "...",
  "runtime_id": "ollama_backend",
  "cost_class": "free_local",
  "fields_filled": 7,
  "needs_review": ["<field_id>", "..."],
  "llm_failed": false,
  "metadata": {...}
}
```

Refusal:
```http
409 Conflict
{"detail":{"code":"no_ready_main_brain","next_action":"..."}}
```

## Research-context whitelist

When `research_draft_id` is supplied, only these structured-payload
fields are passed to the LLM as grounding context:

```python
WHITELIST = (
    "company", "role", "fit_rationale",
    "missing_skills", "outreach_draft_local", "next_tasks",
)
```

Sensitive / personal data on the operator's existing drafts never
leaks into the form-enrichment prompt beyond this whitelist. The
research draft must belong to the calling user (tenant + user-scoped
query).

## Tests proving the contract

The adversarial test in `test_draft_enrichment.py::TestEnrichFormDraft
::test_blocked_fields_never_get_suggested_value` simulates an LLM
that returns a value for EVERY field including credit card and
passport. After enrichment:

```python
assert cc.suggested_value is None       # blocked_payment   → still None
assert passport.suggested_value is None # blocked_sensitive → still None
assert good_text.suggested_value == "Masoud"
assert good_textarea.suggested_value == "I have built ..."
```

The defence is layered:

1. The eligible-rows query filters by `field_type IN _ENRICHABLE_FIELD_TYPES`
   before the LLM is even called.
2. The post-LLM loop re-checks `field_type` per row before writing.
3. Tests pin both layers.

## What this PR does NOT do

* No autofill of the original webpage. The frontend renders the
  suggested values; operator copies / pastes manually OR types
  them into the real form. Daena's UI does NOT click the submit
  button on any external site.
* No automatic enrichment on draft creation. Operator triggers
  enrichment explicitly via the endpoint. This is intentional --
  enrichment costs (free_local time, or metered tokens if opted-in).
* No multi-pass refinement. Single LLM call → result. Refinement
  passes can land in a future PR if operators want a "tighten this
  answer" button.

## Hard-rule audit

| Rule | Status |
|---|---|
| No deploy | ✅ |
| No push | ✅ |
| No secrets printed/read/committed | ✅ |
| No browser autofill | ✅ — service touches DB only |
| No payment/sensitive autofill | ✅ — `_ENRICHABLE_FIELD_TYPES` excludes them; adversarial test proves |
| No external action | ✅ |
| Phase 3 writes blocked | ✅ |
| Audit per call | ✅ |
| Operator can edit every answer | ✅ — `value` field never touched |

## Next: PR-3 QE/Council review for work artifacts

Run QE/Council review on enriched ResearchDraft + FormDraft. Read
`/system/qe-readiness` first; honest mode reporting (full / degraded
/ unavailable) per the Sprint-12A contract.
