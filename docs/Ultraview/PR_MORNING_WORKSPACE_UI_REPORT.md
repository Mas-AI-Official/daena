# PR-3 — Morning workspace UI

**Sprint:** DAENA-MORNING-READY-VP-BETA-OVERNIGHT
**PR:** 3 of 7
**Date:** 2026-05-06
**Author:** Mythos (Daena, via Claude Code)

## Goal

Make the Drafts lane in WorkstreamsPage feel like the morning command
deck: at a glance, the operator sees what each draft is, what's been
done to it, and what to do next. No new pages — extend the existing
canonical surface.

## What's new

1. **Status badges** on every draft row.
   - `llm pending` (amber) — deterministic shape only, no enrichment yet.
   - `enriched` (sky) — LLM enrichment has run.
   - `QE: full` (emerald) — three-stage council ran with 2+ distinct runtimes.
   - `QE: degraded` (amber) — council ran with fewer reviewers than full mode.
   - `workstream` (violet) — promoted to a workstream (cross-referenced via `source_ref_id`).

2. **Backend stamp.** `run_draft_qe_review` now writes
   `_qe_mode` + `_qe_reviewed_at` to `draft.structured_payload` after a
   real run. Skipped on `unavailable` mode (no review actually happened).
   Best-effort: audit row remains the canonical record.

3. **"Start here tomorrow" card** on top of the lane:
   - 5-step suggested workflow (check brain → enrich → council → create
     workstream → ask the chat).
   - Compact totals row: total drafts, career / content / form counts,
     workstreams created from drafts.

4. **Workstream cross-ref.** DraftsLane now also pulls
   `/workstreams?limit=200` and builds a `Set<source_ref_id>` so each
   draft row knows whether a workstream already exists for it.

## Files

```
modified:   backend/app/services/draft_qe_review.py            (+15 lines: structured_payload stamp)
modified:   frontend/src/pages/WorkstreamsPage.tsx             (+131 lines: StartHereCard + StatusBadges + cross-ref)
modified:   backend/tests/test_draft_qe_review.py              (+6 lines: stamp assertion)
new:        docs/Ultraview/PR_MORNING_WORKSPACE_UI_REPORT.md
```

## Hard-rule audit

| Rule | Status |
|---|---|
| No deploy | ✅ |
| No push | ✅ |
| No secrets | ✅ |
| No duplicate Workstreams page | ✅ — extended in place |
| No external action / no send / no submit | ✅ — all badges + card are read-only |
| Honest mode reporting (no fake "QE complete" badge) | ✅ — stamp only fires for `final_mode in {full, degraded}` |
| Stamp survives DB restart | ✅ — written to `research_drafts.structured_payload` JSON column |
| QE service degrades gracefully if stamp fails | ✅ — wrapped in try/except, audit log is canonical |

## Tests

**Backend:** 116/116 pass on the Sprint-12 + PR-1..PR-3 fast subset.

The stamp assertion was added to
`test_draft_qe_review.py::test_two_distinct_runtimes_full` so the
contract is pinned: a successful full-mode run must populate
`payload._qe_mode == "full"` and `payload._qe_reviewed_at` (ISO 8601).

**Frontend:** `npx tsc --noEmit` exit 0.

## Visual change (Drafts lane, career tab)

Before:
```
┌─ Acme Corp                                   [llm pending]  acme.com  3h ago
│  ▸ Senior Backend Engineer
└─
```

After (this draft enriched + QE'd + promoted):
```
┌─ Acme Corp  [enriched] [QE: full] [workstream]   acme.com  3h ago
│  ▸ Senior Backend Engineer
│
│  [Brain] Enrich   [Users] Council   [Arrow] Create Workstream
└─
```

## What this PR does NOT do

* Does not split career / content / form drafts into separate pages.
  The single tabbed lane stays canonical.
* Does not stream council progress live. The action button waits for
  the QE response (~3-8s typical) before flipping the badge.
* Does not paginate the Drafts lane beyond 25 per kind. Operator can
  refresh manually if they need older drafts.

## Next: PR-4 — Safe MCP/CLI/provider setup import
