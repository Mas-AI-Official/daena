# Sprint-12 PR-1 — ResearchDraft LLM enrichment

**Sprint:** DAENA-FULL-POTENTIAL-ACCELERATION-SPRINT-12
**PR:** 1 of 6
**Date:** 2026-05-05
**Author:** Mythos (Daena, via Claude Code)

## Goal

Use the routed `main_brain` (selected by Sprint-12A's readiness
layer, NOT a hardcoded provider) to fill the `_llm_pending` fields
on `ResearchDraft.structured_payload` for both `kind=career` and
`kind=content` drafts. Refuse honestly when no main brain is ready.

## Files

```
new:        backend/app/services/draft_enrichment.py
modified:   backend/app/api/v1/research.py        (+ /drafts/{id}/enrich)
new:        backend/tests/test_draft_enrichment.py
new:        docs/Ultraview/PR_RESEARCHDRAFT_LLM_ENRICHMENT_REPORT.md
```

## Contract enforced

| Rule | How enforced |
|---|---|
| No hardcoded `llama-server` / Ollama / Anthropic | `select_provider()` reads `runtime_readiness.router_summary.main_brain_id` and maps via `RUNTIME_TO_PROVIDER` |
| Refuse on no main brain | `NoReadyMainBrain` raised → `409 {code: no_ready_main_brain, next_action: ...}` |
| Local-first | metered_api selection refused unless `allow_metered=True` is passed explicitly |
| Per-field confidence | `_llm_field_confidence` dict on the merged payload |
| `needs_review` per field | `_llm_needs_review` array, includes any field with `confidence<0.6` OR LLM-flagged |
| LLM garbage tolerated | merger sets `_llm_failed=true` + flags every field for review; never raises |
| Audit on every call | `draft.enrichment.career` / `.content` — ALLOWED on success, BLOCKED on refusal |
| No external action | service surface exposes only `select_provider`, `enrich_research_draft`, `enrich_form_draft` -- no send/submit verb |
| Deterministic fields preserved | merger only fills when existing value is None / empty -- regex-extracted values always win |

## Endpoint

```
POST /api/v1/research/drafts/{draft_id}/enrich
Body: {"allow_metered": false}        # default
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
  "needs_review": ["fit_score", "outreach_draft_local"],
  "llm_failed": false,
  "metadata": {"model_id":"...","latency_ms":12,"token_count_input":10,
               "token_count_output":50,"cost_usd":0.0}
}
```

Refusal:
```http
409 Conflict
{"detail":{"code":"no_ready_main_brain","next_action":"Start the local llama-server / vLLM endpoint at VLLM_BASE_URL or Ollama at OLLAMA_BASE_URL. No main brain is ready, so brain-enrichment work is blocked."}}
```

## Audit trail shape

```
action_type:      draft.enrichment.career  |  draft.enrichment.content
result:           ALLOWED  |  BLOCKED
governance_tier:  1
risk_level:       LOW
action_params:
  draft_id          str
  runtime_id        str         (ALLOWED)
  cost_class        str         (ALLOWED)
  fields_filled     int         (ALLOWED)
  needs_review_count int        (ALLOWED)
  llm_failed        bool        (ALLOWED)
  model_id          str|null    (ALLOWED)
  refusal_code      str         (BLOCKED)
  next_action       str         (BLOCKED)
```

## Tests

24/24 pass in `test_draft_enrichment.py`. Combined Sprint-11 +
Sprint-12A + Sprint-12 PR-1 + PR-2 regression: 135/135 pass.

| Class | Asserts |
|---|---|
| `TestSelectProvider` | NoReadyMainBrain raised + next_action surfaced; metered refused by default; metered allowed when explicit; local main_brain resolves to OLLAMA enum |
| `TestExtractJson` | Bare object, leading "json" word, fenced ```json``` block, greedy braces, garbage→None |
| `TestMergeCareer` | Deterministic fields not overwritten; low confidence flags needs_review; LLM None marks all needs_review; fit_score clamps; suggested_answers garbage filtered |
| `TestMergeContent` | Brief shape merged correctly; existing outline preserved |
| `TestEnrichResearchDraftFlow` | Happy path writes ALLOWED audit + merges payload; no main brain writes BLOCKED audit with refusal_code; LLM garbage → llm_failed=true, no raise |
| `TestEnrichFormDraft` | Blocked field types NEVER receive suggested_value (adversarial LLM tested); low confidence flags needs_review; refusal writes BLOCKED audit |
| `TestCoverage` | Every `RUNTIME_CLASSIFICATION` id has a `RUNTIME_TO_PROVIDER` entry; blocked types not in `_ENRICHABLE_FIELD_TYPES` |

## What this PR does NOT do

* No automatic enrichment trigger -- this is operator-initiated only
  (the endpoint must be POSTed). Auto-enrichment is a future PR
  gated by an explicit policy rule.
* No model-id selection knob -- the provider picks its default
  model. Per-runtime model preference is a follow-up.
* No streaming response -- enrichment is one-shot. SSE could be
  added later for live progress feedback.
* Web grounding (Perplexity) is NOT used here. Sprint-12 PR-3
  introduces QE/Council where web_grounder fills its own slot if
  Perplexity is `ready`. Today it's `configured_untested` so it
  stays out of every preference list.

## Hard-rule audit

| Rule | Status |
|---|---|
| No deploy | ✅ |
| No push | ✅ (PR-1 stays local until sprint complete) |
| No secrets printed/read/committed | ✅ |
| No paid API call without explicit allow | ✅ — `MeteredApiNotAllowed` defends per-call |
| No /submit /send /apply /post /publish /dispatch endpoint | ✅ — enrichment endpoint is `/enrich`; tests assert no banned route |
| Phase 3 writes blocked | ✅ — `INTEGRATIONS_PHASE2_READONLY=true` unchanged |
| Audit row per call | ✅ — verified by regression tests |
| Deterministic fields preserved | ✅ — verified by `test_does_not_overwrite_deterministic_fields` |

## Next: PR-2 FormDraft LLM enrichment

The implementation actually shipped in PR-1 (one canonical
`draft_enrichment` module covering both kinds), so PR-2 is just
the report + endpoint mount confirmation. Detailed report follows.
