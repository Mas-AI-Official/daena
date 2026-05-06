# PR-6 -- Business Routine Draft-Only Expansion

**Sprint:** DAENA-SPRINT-20-LIVE-BUSINESS-OPS-ACTIVATION
**PR:** 6 of 8
**Date:** 2026-05-06

## Goal

Let the routine_autonomy scheduler prepare the morning queue
(promote opportunities to workstreams, draft outreach for
opportunities that already carry a recipient email) so the founder
wakes up to a ready-to-review batch. The hard wall: routines NEVER
invoke the Gmail bridge or send bridge -- the operator still has to
approve before anything reaches Gmail.

Codex peer review flagged this for deferral. I kept it in scope with
a single bright line enforced at the source level: the routine handler
module imports zero send / Gmail-bridge symbols (test pins this via
source grep).

## What ships

`backend/app/services/business_pipeline/routine_handler.py`:
* New `business_workstream_proposal_handler` -- pulls top-K
  discovered opportunities, calls the workstream bridge for each,
  returns `workstream:<id>` artifacts. Skips already-promoted via
  `DuplicateWorkstream`. Logs and counts unknown-type / missing-
  department refusals.
* New `local_draft_action_creation_handler` -- pulls opportunities
  whose `raw_metadata.recipient_email` is set, calls the draft
  factory, returns `draft:<id>` artifacts. Opportunities WITHOUT a
  recipient_email are skipped (the source adapters in PR-2 don't
  capture recipients; the operator can backfill via raw_metadata or
  a future sprint can add a recipient discovery layer).
* Both handlers registered alongside the existing
  `opportunity_discovery` handler. Idempotent re-registration.

## Mythos design choices

**Bright line: no Gmail bridge from scheduler.** Source grep test
pins zero references to `queue_gmail_draft_creation`,
`queue_gmail_send`, `gmail_bridge`, `send_bridge`, or
`controlled_execution_dispatch`. A regression that wires Gmail
into a routine fails the test before it can land.

**Local draft factory only.** The factory produces local
`BizOutreachDraft` rows with no GoaRequest side effect; tested.
Approval queueing is a separate, operator-driven step. The morning
queue contains drafts the operator reviews and either approves
(triggering Gmail bridge as OPERATOR initiator) or rejects.

**Top-K cap on the proposal handler.** Same approval-fatigue defense
as PR-1 / PR-3. Default 3 promotions per routine run. Bounded at 20
hard so a misconfigured routine cannot mass-promote.

**Skip-without-recipient is honest, not a bug.** A routine that runs
and skips 5 opportunities silently is misleading. The detail string
returns explicit counts (`drafted=N skipped_no_recipient=M
blocked=K`) so the operator sees what happened.

**Already-promoted skip doesn't fail the routine.** `DuplicateWorkstream`
is caught + counted, not raised. A routine that bumps into 3 already-
promoted opportunities and 2 new ones reports
`promoted=2 skipped=3 failed=0` and stays OK -- the operator's
next-morning behavior is the routine continuing to do useful work
even when most opportunities already have workstreams.

**No DispatchInitiator.OPERATOR override path.** The handlers do not
take an initiator parameter. They use the local factory + bridge,
neither of which produces a GoaRequest, so initiator is moot --
there is no controlled-execution dispatch happening here.

## Locked invariants

| Invariant | Where |
|---|---|
| All three business handlers registered | `TestHandlerRegistration::test_handlers_registered` |
| Workstream proposal promotes top-K | `TestWorkstreamProposalHandler::test_promotes_top_k_discovered_opportunities` |
| Workstream proposal creates NO GoaRequest | `test_no_goa_request_created` |
| Local-draft handler skips opps without recipient | `TestLocalDraftHandler::test_drafts_only_for_opps_with_recipient` |
| Local-draft handler creates NO GoaRequest | `test_local_draft_handler_creates_no_goa_request` |
| Routine handler imports no Gmail/send bridge | `TestBrightLineHardRule::test_routine_handler_does_not_import_gmail_bridge` |
| Routine handler has no external-action symbols | `test_routine_handler_has_no_external_action_strings` |

## Hard rules audit

| Rule | Status |
|---|---|
| Allowed: discovery / scoring / opportunity persistence | enforced -- existing PR-1 handler |
| Allowed: workstream creation | enforced -- new handler local-only |
| Allowed: local outreach draft creation | enforced -- new handler local-only |
| Blocked: Gmail draft bridge | enforced -- source grep |
| Blocked: send bridge | enforced -- source grep |
| Blocked: file apply / git commit / scan / pay | enforced -- module never imports these |
| Initiator hardcoded SCHEDULER | applied -- existing run_discovery_loop call uses `initiator='scheduler'`; new handlers do not call any dispatch surface so initiator is N/A |
| No auto-approval | applied -- no GoaRequest is created at all |
| No external action | enforced -- bright line |
| pause / resume / global_paused work | regression -- 15 routine_autonomy tests still pass |

## Tests

```
backend/tests/test_business_routine_draft_only.py   11 tests
backend/tests/test_business_routine.py               4 tests (regression)
backend/tests/test_routine_autonomy.py              15 tests (regression)
```

26 / 26 pass.

## Files

```
modified:   backend/app/services/business_pipeline/routine_handler.py
new:        backend/tests/test_business_routine_draft_only.py
new:        docs/Ultraview/PR_BUSINESS_ROUTINE_DRAFT_ONLY_EXPANSION_REPORT.md
```

## Next: PR-7 -- VP Chat Business Flow v2 (narrow, ID-explicit)
