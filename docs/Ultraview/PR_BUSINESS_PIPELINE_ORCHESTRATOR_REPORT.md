# PR-1 -- Business Pipeline Orchestrator

**Sprint:** DAENA-SPRINT-19-BUSINESS-EXECUTION-LOOPS
**PR:** 1 of 8
**Date:** 2026-05-06

## Goal

Single orchestrator for the growth loop. Discover -> dedupe ->
score -> top-N cap -> persist as `Opportunity` rows. Pure local
write; NEVER auto-approves anything; NEVER calls a tool handler.

## What ships

`backend/app/models/business.py` (new):

* `Opportunity` -- discovered business opportunity, tenant-scoped
  with deterministic `dedupe_key` (sha256 of source_name + title).
* `BizOutreachDraft` -- placeholder for PR-3 (named to disambiguate
  from existing `crm.OutreachDraft`).
* `OPPORTUNITY_TYPES` (locked Sprint-19): customer_lead, grant,
  accelerator, hackathon, freelance_project, partnership,
  bug_bounty_program, content_opportunity.
* Status / draft-kind / draft-status enum-ish tuples.

`backend/app/services/business_pipeline/__init__.py` (new):
public re-exports.

`backend/app/services/business_pipeline/discoverer.py` (new):

* Pluggable source registry: `register_source(name, fn)` /
  `unregister_source` / `registered_sources`.
* `DiscoveredOpportunity` pre-DB dataclass.
* Built-in `manual_seed_source` reading
  `backend/.opportunity_seed.json` (gitignored). Tolerates
  missing / malformed file.
* No scraping behind login. No browser automation. Pure local.

`backend/app/services/business_pipeline/scorer.py` (new):

* Pure Python, no LLM, no model imports.
* 4 components clamped 0..25: deadline_proximity, value_score,
  effort_inverse, type_weight. Total clamped 0..100.
* `score_opportunity(op) -> int` and `score_components(op) -> dict`
  for audit / debug.

`backend/app/services/business_pipeline/orchestrator.py` (new):

* `run_discovery_loop(db, *, tenant_id, top_n, initiator) ->
  DiscoveryRunResult`.
* Iterates sources, dedupes, scores, sorts desc, caps at top_n.
* Upserts into `opportunities` table. Source explosion does NOT
  propagate (captured into `sources_failed`).
* Updates score / drift fields on existing rows; preserves
  operator-advanced status.

`backend/app/models/__init__.py` (modified): registers
`Opportunity` and `BizOutreachDraft`.

`backend/.gitignore` (modified): adds
`.opportunity_seed.json`, `.send_rate_limit.json`,
`.recipient_suppression.json`.

## Mythos design choices

**Top-N cap is the load-bearing rule.** Without it, discovery
finds 50 leads → 50 outreach drafts → 50 approval modals →
operator approves blindly. The cap turns "spam your founder"
into "show your founder the 5 best." Default top_n=10; PR-3
will cap draft generation lower (default 3-5).

**Scoring is deterministic Python, NEVER LLM.** Test pins this
by reading the scorer source and asserting it does NOT import
`llm_service`, `model_router`, `anthropic`, `openai`. Same input
always produces the same score; operator decisions are auditable.

**Source allowlist over content credibility.** Per-source
credibility doesn't appear in the score function. If a source
is registered, it's credible; if not, it doesn't run. This stops
attackers with seed-file-write access from dialling credibility
to 11 by hand.

**Dedupe by (source_name, title.lower()) sha256.** Two sources
finding the same lead = two rows (audit shows both sources). Same
source emitting the same title twice = one row. Sane behavior for
both upsert and audit.

**Sources are read-only.** Module surface walked in test:
no `send` / `submit` / `post` / `pay` / `send_email` callables.

## Locked invariants

| Invariant | Where |
|---|---|
| 8 opportunity types locked | `TestOpportunityTypes::test_locked_eight_types` |
| Scoring is deterministic | `TestScorer::test_score_deterministic` |
| Overdue deadline scores 0 proximity | `test_overdue_deadline_zero_proximity` |
| High-value low-effort grant scores >= 80 | `test_high_value_low_effort_grant_scores_high` |
| Unknown type falls to baseline (10) | `test_unknown_type_falls_back_to_baseline` |
| Manual seed missing file -> empty | `TestManualSeedSource::test_missing_file_returns_empty` |
| Manual seed malformed -> empty | `test_malformed_json_returns_empty` |
| Manual seed unknown type skipped | `test_unknown_type_skipped` |
| Orchestrator dedupes by source+title | `TestOrchestrator::test_dedupes_by_source_and_title` |
| Orchestrator caps at top_n by score desc | `test_caps_at_top_n_by_score` |
| Source explosion does NOT propagate | `test_failing_source_does_not_propagate` |
| Empty registry returns zero | `test_empty_registry_returns_zero` |
| Module exposes no send/submit/post/pay | `TestNoForbiddenSurface::test_orchestrator_module_no_send_submit_post_pay` |
| Scorer has NO LLM import | `test_no_llm_import_in_scorer` |

## Hard rules audit

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied |
| No generic send_email | applied -- module surface bans it |
| No bulk sending | applied -- this PR has no send path at all |
| No LinkedIn automation | applied |
| No form/application submit | applied |
| No social post | applied |
| No payment | applied |
| No unauthorized scan | applied |
| No browser automation on external websites | applied |
| No trust graduation for send/apply/commit | unchanged from Sprint-18 |
| No scheduler auto-execute for external actions | unchanged from Sprint-18 |
| No scraping behind login | applied -- discoverer is read-only file/registry, no HTTP |
| No contact spam | applied -- top-N cap |

## Tests

```
backend/tests/test_business_pipeline.py    15 tests
```

15/15 pass.

## Files

```
new:        backend/app/models/business.py
new:        backend/app/services/business_pipeline/__init__.py
new:        backend/app/services/business_pipeline/discoverer.py
new:        backend/app/services/business_pipeline/scorer.py
new:        backend/app/services/business_pipeline/orchestrator.py
new:        backend/tests/test_business_pipeline.py
modified:   backend/app/models/__init__.py
modified:   backend/.gitignore
new:        docs/Ultraview/PR_BUSINESS_PIPELINE_ORCHESTRATOR_REPORT.md
```

## Next: PR-2 -- Lead and Opportunity Inbox UI
