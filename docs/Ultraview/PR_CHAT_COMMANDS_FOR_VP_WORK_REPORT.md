# Sprint-12 PR-5 — Chat commands for VP work

**Sprint:** DAENA-FULL-POTENTIAL-ACCELERATION-SPRINT-12
**PR:** 5 of 6
**Date:** 2026-05-05
**Author:** Mythos (Daena, via Claude Code)

## Goal

Let the operator drive the entire draft + workstream pipeline from
natural English in chat -- without ever opening the API surface
manually. Deterministic backend state, no hallucination, runtime-not-
ready refusals surface verbatim.

## Files

```
new:        backend/app/services/vp_work_commands.py
new:        backend/app/api/v1/vp_commands.py
modified:   backend/app/api/v1/__init__.py     (mount /vp-commands)
new:        backend/tests/test_vp_work_commands.py
new:        docs/Ultraview/PR_CHAT_COMMANDS_FOR_VP_WORK_REPORT.md
```

## Endpoint

```
POST /api/v1/vp-commands
Body: {
  "text":               "Run council on draft 11111111-...",
  "allow_metered":      false,
  "allow_web_grounding": false
}
Auth: FOUNDER role required.
```

Response (always 200; refusals + needs_disambiguation come back
structured, never raise 500 for a recognizable input):

```json
{
  "success": true,
  "intent": "qe_review_draft",
  "summary": "Council ran in mode=full with 3 distinct runtime(s). Next: operator_review_required.",
  "needs_disambiguation": false,
  "next_action": null,
  "data": { ... }
}
```

## Recognized intents

The parser is regex-only (deterministic, never calls an LLM to
interpret the command itself). Brief examples → intent:

| Operator says | Intent | Need draft id? |
|---|---|---|
| "Daena, review this opportunity" / "show my drafts" | `review_drafts` | no |
| "What should I do next?" / "what's next" | `next_steps` | no |
| "Enrich this draft" / "enrich draft \<id>" | `enrich_draft` | yes (else needs_disambiguation) |
| "Run council on this draft" / "council \<id>" / "qe review \<id>" | `qe_review_draft` | yes |
| "Create a work plan from this" / "Promote this draft to a workstream" | `create_workstream_from_draft` | yes |
| "Which department should handle this \<id>?" | `which_department` | yes |
| anything else | `unrecognized` | — |

The parser accepts FULL UUIDs and 8+-char hex prefixes so the
operator can paste short ids from the UI. The runner re-validates
with a tenant + user-scoped DB query.

## Runner behaviour

| Intent | Reads | Writes |
|---|---|---|
| `review_drafts` | recent ResearchDraft + FormDraft rows (10 each) | audit row only |
| `next_steps` | open Workstreams (RUNNING / BLOCKED / WAITING_APPROVAL) | audit row only |
| `enrich_draft` | draft -> calls `enrich_research_draft` / `enrich_form_draft` | LLM via routed runtime + audit row |
| `qe_review_draft` | draft -> calls `run_draft_qe_review` | LLM via routed runtimes + audit row |
| `create_workstream_from_draft` | draft -> calls `post_from_draft` | Workstream row + audit row |
| `which_department` | draft + `_DRAFT_KIND_TO_DEPARTMENT_NAME` + `_looks_legal()` | audit row only (deterministic answer) |

## Hard rules — encoded + tested

| Rule | Status |
|---|---|
| Deterministic backend state (no LLM for parsing) | ✅ — regex only in `parse_command` |
| No hallucinated draft status | ✅ — runner returns `needs_disambiguation` instead of guessing |
| Tenant + user-scoped | ✅ — every DB query filters on `tenant_id == user.tenant_id AND user_id == user.id` |
| Runtime not ready -> exact missing string | ✅ — refusal `next_action` flows through enrichment / QE -> CommandResult.next_action |
| No external action | ✅ — runner only calls existing services that are already external-action-free |
| Audit per call | ✅ — `vp_command.<intent>` row written every time |
| No /submit /send /apply /post /publish endpoint | ✅ — endpoint is `/vp-commands` |

## Tests

**25/25 pass** in `test_vp_work_commands.py`:

| Class | Asserts |
|---|---|
| `TestParser` | 12 phrases map to expected intent; UUID + UUID-prefix extraction |
| `TestListRunners` | review_drafts returns counts + writes audit; next_steps returns open list |
| `TestDisambiguation` | enrich + council without draft id → needs_disambiguation=True |
| `TestWhichDepartment` | career → Sales; legal token → Legal & Compliance |
| `TestEnrichRun` | enrich runs against FakeRegistry; no-main-brain refusal surfaces next_action verbatim |
| `TestQERun` | council runs in mode=full with 3 distinct runtimes |
| `TestCreateWorkstream` | promote-to-workstream returns workstream id + source_type=draft |

**Combined Sprint-11 + Sprint-12A + Sprint-12 PR-1..PR-5 regression:
192/192 pass.** frontend tsc unchanged (no UI in PR-5).

## What this PR does NOT do

* No deep integration into `chat_orchestrator.py`. The orchestrator
  is intentionally a separate module; this PR adds a sibling
  endpoint the chat surface can call alongside (or before) the
  full LLM path. Wiring "if vp_command.success → render structured
  response else → fall through to LLM" is a small frontend follow-up.
* No streaming -- vp-commands is request/response. Council reviews
  can take several seconds; that's fine for the chat surface
  rendering a single structured response card.
* No locale handling -- parser is English-only. i18n is a future PR.

## Hard-rule audit

| Rule | Status |
|---|---|
| No deploy | ✅ |
| No push | ✅ |
| No secrets printed/read/committed | ✅ |
| Phase 3 writes blocked | ✅ |
| Audit per call | ✅ |
| Deterministic parsing | ✅ — regex only |
| No hallucinated status | ✅ — needs_disambiguation when ambiguous |

## Next: PR-6 Sprint-12 full smoke

End-to-end verification: backend boots, runtime readiness returns
honest answers, draft enrichment + QE refuse honestly when the
runtime is missing, workstream creation succeeds, vp-commands
route correctly, no banned routes exist.
