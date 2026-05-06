# PR-2 — Frontend / backend sync hardening

**Sprint:** DAENA-MORNING-READY-VP-BETA-OVERNIGHT
**PR:** 2 of 7
**Date:** 2026-05-06
**Author:** Mythos (Daena, via Claude Code)

## Goal

Make every backend draft + workstream + readiness endpoint reachable
from the frontend with no dead buttons. The backend ships the
endpoints; PR-2 connects them to the WorkstreamsPage Drafts lane.

## What was already wired (Sprint-11 / 12 / 12A)

| Capability | Frontend | Status |
|---|---|---|
| `/research/drafts` list | WorkstreamsPage.DraftsLane career + content tabs | ✅ |
| `/form-drafts` list | WorkstreamsPage.DraftsLane forms tab | ✅ |
| `/workstreams` list + detail | WorkstreamsPage main board | ✅ |
| `/workstreams/{id}/stream` SSE | WorkstreamsPage detail panel | ✅ |
| `/workstreams/{id}/redirect` / `/archive` | WorkstreamsPage actions | ✅ |
| `/system/runtime-readiness` + `/router-readiness` + `/qe-readiness` + `/router-policy` | BrainReadinessPanel (settings → Models & Runtimes) | ✅ |
| `/vp-commands` chat preflight | chatStore + VPCommandCard (PR-1) | ✅ |

## What PR-2 adds

The four Sprint-12 draft action endpoints had no UI before today.
They are now wired:

| Endpoint | UI button | Status badge after run |
|---|---|---|
| `POST /research/drafts/{id}/enrich` | "Enrich" (Brain icon) | green (done), red (refused) |
| `POST /research/drafts/{id}/qe-review` | "Council" (Users icon) | green (done with mode), red (unavailable) |
| `POST /workstreams/from-draft` (research) | "Create Workstream" (ArrowRight icon) | green (id 8-char), red (failed) |
| `POST /form-drafts/{id}/enrich` | "Enrich" on FormDraft row | green / red |
| `POST /form-drafts/{id}/qe-review` | "Council" on FormDraft row | green / red |
| `POST /workstreams/from-draft` (form) | "Create Workstream" on FormDraft row | green / red |

Each button:

* Is **disabled while running** (Loader2 spinner replaces icon).
* Surfaces refusal `next_action` from the backend verbatim (toast + inline amber note).
* Calls `onRefresh()` to reload the lane on success.
* Stops event propagation (so clicking inside the expanded row doesn't collapse it).

## Honest blocked-state behaviour

When a backend endpoint returns a refusal payload (e.g. enrichment
without a ready main brain returns `{refusal_code: "no_ready_main_brain", next_action: "Start the local llama-server / Ollama. ..."}`),
the button:

1. Flips to red "refused" tone.
2. Shows the toast: `Enrich refused: no_ready_main_brain`.
3. Renders the verbatim `next_action` text below the action row in
   amber.

The operator never has to guess what's missing.

## Files

```
modified:   frontend/src/pages/WorkstreamsPage.tsx                   (+177 lines: DraftActions component + threading)
new:        backend/tests/test_morning_route_contract.py             (88 lines, 13 tests)
new:        docs/Ultraview/PR_FRONTEND_BACKEND_SYNC_HARDENING_REPORT.md
```

## Tests

**Backend:** 116 / 116 pass on the Sprint-12 + PR-1 + PR-2 subset.

```
tests/test_morning_route_contract.py        13 (NEW)
tests/test_chat_vp_preflight_contract.py     5 (PR-1)
tests/test_vp_work_commands.py              25
tests/test_draft_enrichment.py              24
tests/test_draft_qe_review.py               10
tests/test_workstream_from_draft.py         11
tests/test_sprint12_full_smoke.py           28
                                          ────
                                           116
```

The new contract test pins the eight POST endpoints + four GET
readiness endpoints the frontend depends on. If any path drifts the
test fails before the buttons silently 404 in production.

It also asserts no banned-verb route exists under `/workstreams`,
`/research/drafts`, or `/form-drafts` (no `/send /submit /apply
/publish /dispatch` paths).

**Frontend:** `npx tsc --noEmit` exit 0.

## Hard-rule audit

| Rule | Status |
|---|---|
| No deploy | ✅ |
| No push (until sprint complete + explicit approval) | ✅ — only PR-0 push happened |
| No secrets read/printed/committed | ✅ |
| No dead buttons | ✅ — every button maps to an existing backend endpoint with refusal handling |
| Unavailable feature shows honest blocked state | ✅ — refusal `next_action` rendered verbatim |
| No external action | ✅ — all six action buttons stay inside the local pipeline |
| No /submit /send /apply /publish endpoint | ✅ — covered by `test_no_banned_verbs_on_*` |
| No duplicate ResearchDraft or Workstream pages | ✅ — extended existing WorkstreamsPage |

## Next: PR-3 — Morning workspace UI polish

Add status badges (deterministic / enriched / QE-reviewed / workstream-
created) and a "Start here tomorrow" card on top of the Drafts lane.
