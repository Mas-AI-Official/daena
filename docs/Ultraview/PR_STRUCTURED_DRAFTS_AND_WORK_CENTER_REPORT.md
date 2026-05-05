# PR-2 — Structured ResearchDraft + Drafts lane in Workstreams

**Sprint:** DAENA-SUPERVISED-WORK-OPERATOR-SPRINT-11
**Date:** 2026-05-05
**Author:** Mythos (Daena, via Claude Code)

## Goal

Turn the Sprint-10 `ResearchDraft` (raw extract + summary) into a
**structured work artifact** that the operator can review, edit, and
hand to a downstream draft (apply / contact / publish) — without
spawning parallel `OpportunityDraft` / `ContentBrief` tables and
without spawning a parallel "Work Command Center" page.

This PR honors CLAUDE.md Rule 2 ("one canonical file per concern") by
keeping a single `ResearchDraft` table that carries both research
shapes via a JSONB `structured_payload` column.

## What changed

### 1. New column: `ResearchDraft.structured_payload`

```python
structured_payload: Mapped[dict | None] = mapped_column(
    JSONBCompat, nullable=True,
)
```

- Nullable so legacy rows survive.
- Single canonical entity. Per CLAUDE.md Rule 2, **no** parallel
  `OpportunityDraft` / `ContentBrief` tables exist. A test asserts
  the modules `app.models.opportunity_draft` and
  `app.models.content_brief` raise `ModuleNotFoundError` on import.

### 2. `build_structured_payload()` in `research_flow.py`

Two stable shapes, one function. Schema version pinned to
`STRUCTURED_PAYLOAD_VERSION = "2026-05-05.v1"`.

#### `kind="career"` → opportunity shape

```
{
  "_schema_version": "2026-05-05.v1",
  "_kind": "opportunity",
  "_llm_pending": true,
  "company": "<host-derived candidate>" | null,
  "role": null,                  # filled by LLM enrichment (future PR)
  "team": null,
  "location": null,
  "compensation": null,
  "requirements": [<bullet>...],
  "responsibilities": [],        # filled by LLM enrichment
  "fit_score": null,             # 0-100, LLM enrichment
  "fit_rationale": null,
  "missing_skills": [],
  "suggested_answers": [],       # [{question, answer, confidence}]
  "outreach_draft_local": null,  # local-only draft, never sent
  "next_tasks": [],
  "sources": [<urls>...],
  "goal_echo": "<operator goal>"
}
```

#### `kind="content"` → brief shape

```
{
  "_schema_version": "2026-05-05.v1",
  "_kind": "brief",
  "_llm_pending": true,
  "audience": null,
  "key_points": [<top-N bullets>],
  "angle": null,
  "outline": [<bullets>...],
  "captions": [],
  "hooks": [],
  "sources": [<urls>...],
  "risks_to_verify": [],
  "claims_to_verify": [],
  "goal_echo": "<operator goal>"
}
```

### 3. Honest `_llm_pending: true` flag

PR-2 is **deterministic only**. The structuring step uses regex
extraction (bullet lines, URLs, host-derived company candidate). It
does NOT call an LLM. Why:

- LLM calls in research_flow add latency, cost, and CI flakiness.
- The shape ships now; the LLM enrichment step is a tighter,
  reviewable follow-up PR (PR-2.5: "LLM enrichment for ResearchDraft").
- The UI already differentiates `_llm_pending=true` rows with an
  amber "llm pending" badge so the operator sees what's been filled
  vs what still needs enrichment. Honesty + visibility (CLAUDE.md
  rule 17) preserved.

The shape is **stable across enrichment passes** — same keys, just
better values once the LLM step lands. Consumers don't need to
branch on `_llm_pending`.

### 4. `create_research_draft()` wires structuring into the flow

```python
structured = build_structured_payload(
    kind=kind, goal=goal.strip(),
    raw_extract=outcome.result,
    source_url=url.strip(),
    source_host=_safe_host(url),
)
draft = ResearchDraft(..., structured_payload=structured)
```

No new audit row, no new external call. The same one scrape audit
row already produced by Sprint-10 still covers the read.

### 5. API response shape (`api/v1/research.py`)

`ResearchDraftOut` now exposes `structured_payload: dict | None`.
All four endpoints (`POST /research/career`, `POST /research/content`,
`GET /research/drafts`, `GET /research/drafts/{id}`) return the new
field automatically — they all serialize through `from_model`.

### 6. Drafts lane in `WorkstreamsPage.tsx`

A new `DraftsLane` component above the workstream filter row.

- Three tabs: **Career** | **Content** | **Forms (PR-3 placeholder)**.
- Each tab shows a count badge and the matching drafts.
- Click a draft row → expands the structured payload as JSON for
  inspection. (PR-2.5 will replace the JSON dump with a proper
  card layout.)
- "llm pending" amber badge on rows where `_llm_pending=true`.
- Honest empty states ("No career drafts yet. Run a research flow
  from chat or call POST /api/v1/research/career.").
- Honest error state (Failed to load drafts: <error>).

**Per CLAUDE.md rule 17 (Honesty + Persistence + Visibility):**
- The lane is read from `/research/drafts` API — persistent state.
- Empty states are honest, not silenced.
- Errors are surfaced inline, not swallowed.
- "llm pending" tells the operator what's deterministic vs what's
  awaiting LLM enrichment.

**Per CLAUDE.md Rule 2 (one canonical file per concern):**
- `WorkstreamsPage` is *the* command center. PR-2 extends it; it
  does NOT spawn a parallel page.

## Tests

`backend/tests/test_research_structured_payload.py` — 21 tests, all
passing.

| Group | Cases |
|---|---|
| `TestCareerStructuredPayload` | 7 (kind, all required keys, `_llm_pending` default, requirements from bullets, host strips ATS subdomain, sources include origin URL, schema version) |
| `TestContentStructuredPayload` | 4 (kind, all required keys, outline from bullets, sources extracted from text) |
| `TestExtractionHelpers` | 6 (bullets dash/star/dot, dedup, cap, URL extract, trailing punctuation strip, company candidate strips ATS prefix) |
| `TestNoDuplicateModels` | 3 (no `OpportunityDraft` module, no `ContentBrief` module, `structured_payload` column present) |
| `TestPersistence` | 1 (round-trip dict through SQLAlchemy + JSONB compat) |

Regression: existing `test_research_flow.py` (33 tests) all green.
Combined with PR-1 suites: **109 passing, 0 failing**.

Frontend: `npx tsc --noEmit` exit 0.

## Hard-rule audit

| Rule | Status |
|---|---|
| No deploy | ✅ |
| No push | ✅ (commit only; push deferred until sprint complete) |
| No secrets read/printed/committed | ✅ |
| No external messages | ✅ |
| No external action fired from drafts lane | ✅ |
| No Phase 3 writes | ✅ |
| No duplicate command center page | ✅ — `WorkstreamsPage` extended, not duplicated |
| No duplicate Opportunity / ContentBrief models | ✅ — Rule 2 explicitly tested |

## Files touched

```
modified:   backend/app/models/research.py
modified:   backend/app/services/research_flow.py
modified:   backend/app/api/v1/research.py
modified:   frontend/src/pages/WorkstreamsPage.tsx
new:        backend/tests/test_research_structured_payload.py
new:        docs/Ultraview/PR_STRUCTURED_DRAFTS_AND_WORK_CENTER_REPORT.md
```

## Migration note

The `structured_payload` column is **nullable**. Dev SQLite picks it
up on `create_all`. Production (PostgreSQL) will need an Alembic
migration before this lands; that ships in the production-deploy PR
which is out of scope here (no deploy hard-rule).

## What this PR does *not* do (deferred)

- LLM enrichment pass that fills the `null` fields and flips
  `_llm_pending` to false. Future PR.
- `FormDraft` (a separate model) — that's PR-3.
- Approval queue extension — that's PR-4.

## Next step

PR-3 — `FormDraft` Assistant. Net-new model + service + API + page.
The first genuinely new draft type. No `/submit` endpoint, no
autofill, no payment fields, no government / immigration submission
automation. Tests assert the absence of those routes.
