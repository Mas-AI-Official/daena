# DAENA -- Sprint-18 Trust Ladder + Routine Autonomy Smoke + Final Report

**Sprint:** DAENA-SPRINT-18-TRUST-LADDER-AND-ROUTINE-AUTONOMY
**PR:** 6 of 6 (final)
**Date:** 2026-05-06
**Author:** Mythos (Daena, via Claude Code)

This is the truth at the close of Sprint-18. After Sprint-17,
Daena could repair her own codebase under approval. Sprint-18 takes
the next step: Daena now has a real **trust ladder** -- explicit
policy-backed graduation for low-risk repeated work -- AND a
routine autonomy scheduler skeleton. But this sprint is also the
sprint of **walls about walls**: every new graduation surface comes
with a hard initiator-aware refusal so Daena cannot self-promote
or auto-execute scheduler-initiated work.

## What Sprint-18 actually shipped

| PR | What | Commit |
|---|---|---|
| 1 | Trust Ladder Policy Engine | 88b3170 |
| 2 | Trust Graduation UI | 642ee4f |
| 3 | Auto-approve low-risk draft actions | 2357389 |
| 4 | Routine Autonomy Scheduler skeleton | bf0e7f3 |
| 5 | Trust-aware VP chat | 4df3734 |
| 6 | this report | local |

## The six walls of `should_auto_approve`

```
1. tool_id NOT in TRUST_FORBIDDEN_TOOLS
   (send / file apply / git commit cannot graduate, ever)
2. initiator == OPERATOR
   (scheduler / self-healing / delegated never graduate)
3. tool_id in TRUST_ELIGIBLE_TOOLS
   (only the three low-risk draft tools are eligible)
4. policy.max_auto_tier == AUTO_APPROVE_LOW_RISK
   (founder must explicitly grant; default NONE)
5. trust_ladder.rejection_count == 0
   (any rejection wipes graduation, even with tier still set)
6. trust_ladder.approvals_count >= 5
   (default; configurable)
```

Auto-approval fires ONLY if all six pass. First refusal wins;
reason code is stable.

## TRUST_ELIGIBLE_TOOLS (locked Sprint-18)

```python
TRUST_ELIGIBLE_TOOLS = frozenset({
    "gmail.create_draft",
    "calendar.create_tentative_event_without_invites",
    "local.file_change_proposal",
})
```

## TRUST_FORBIDDEN_TOOLS (locked, FOREVER)

```python
TRUST_FORBIDDEN_TOOLS = frozenset({
    "gmail.send_existing_draft",
    "local.file_change_proposal.apply",
    "local.git_commit_approved_patch",
})
```

These three tools CANNOT graduate. Operator must approve manually
every single time. The list is enforced in:

* `trust_policy.set_max_auto_tier` (refuses raise on these tools)
* `trust_policy.should_auto_approve` (wall #1)
* `routine_autonomy` module surface (kind set excludes anything that
  could reach these tools)
* Six dispatch gates in `controlled_execution_dispatch.py` (Sprint-14)

## Routine kinds (locked Sprint-18 set of 6)

```
opportunity_discovery
business_workstream_proposal
local_draft_action_creation
self_diagnostic
readiness_check
repair_workstream_proposal
```

No SEND, SUBMIT, POST, PAY, APPLY, COMMIT kinds. Tested by
walking the module surface and asserting these strings are absent.

## Mythos design choices this sprint

**Initiator-aware trust.** Wall #2 of `should_auto_approve` is the
load-bearing one. Sprint-18 is only safe because graduation fires
exclusively for OPERATOR-initiated dispatches. Scheduler /
self-healing / delegated dispatches always pay full approval
freight, regardless of tier. This mirrors Asset Shield's
initiator-aware tier collapse from v3.7.0.

**Founder-only tier raise via static confirmation phrase.** Daena
CANNOT raise her own tier. The phrase is computed from
`(tool_id, tier)` -- not LLM-generated. Frontend displays it,
operator types it, backend recomputes and string-matches. Prompt
injection cannot bypass.

**Auto-approval does NOT inflate the ladder.** The ladder records
GENUINE operator decisions only. If we re-recorded on auto-approve,
counters would compound and "5 approvals = graduate" would degrade
into noise. `trust_auto_approve.maybe_apply_trust_auto_approval`
mutates the GoaRequest in place but NEVER calls
`trust_ladder.record_decision`.

**Skeleton-only scheduler, not full cron.** A real cron daemon
spawning routine runs in the background is exactly the surface
where bugs amplify: a buggy handler runs every minute for 6 hours
before anyone notices. Sprint-18 ships pause/resume/run-once + state
persistence; activation is Sprint-19+. The contract is forward-
compatible.

**Trust-aware VP chat is deterministic, no LLM.** Six regex
patterns + six deterministic Python runners that read backend
state. No hallucinated permissions. No "I think I can also...".
The summary string is a one-liner with no exclamation marks, no
hedging, no LLM tells.

## Smoke verification

| # | Check | Pass? |
|---|---|---|
| 1 | backend starts | yes -- 5 new routers mount cleanly |
| 2 | frontend starts | yes -- tsc exit 0 |
| 3 | trust policy visible | yes -- `/api/v1/trust/policies` + `GovernanceTrustPage.tsx` |
| 4 | dangerous tools cannot graduate | yes -- `set_max_auto_tier` raises ValueError; tested for all 3 forbidden tools |
| 5 | `gmail.send_existing_draft` cannot auto-approve | yes -- in TRUST_FORBIDDEN_TOOLS; `TestForbiddenToolNeverAutoApproves` parametric over the 3 |
| 6 | `local.file_change_proposal.apply` cannot auto-approve | yes -- same |
| 7 | `local.git_commit_approved_patch` cannot auto-approve | yes -- same |
| 8 | low-risk draft actions can auto-approve only after threshold | yes -- `TestHappyPath::test_all_walls_pass_mutates_approval` requires 5 approvals + tier grant |
| 9 | rejection resets trust | yes -- `test_rejection_arriving_after_tier_grant_blocks_graduation` (reader-side wall) + `test_rejections_force_none` (writer-side wall) |
| 10 | routine scheduler creates local drafts/workstreams only | yes -- routine kinds locked to the 6 allowed set; module surface bans send/submit/post/pay/apply/commit |
| 11 | scheduler-initiated never auto-approves | yes -- `TestNonOperatorInitiatorNeverAutoApproves::test_scheduler_blocked_even_when_policy_open` (set ALL six walls + then proves SCHEDULER initiator still refuses) |
| 12 | pause autonomy stops routines | yes -- `TestRunOnce::test_global_paused_blocks` |
| 13 | VP chat reports real trust state, no LLM | yes -- 23 chat tests, deterministic summaries asserted |
| 14 | submit / post / pay still absent | yes -- `WRITE_TOOLS` unchanged from Sprint-17 (still 6); no new tool added |
| 15 | no push from any new code path | yes -- routine_autonomy module surface bans `push`; trust modules never invoke git |
| 16 | Frontend tsc clean | exit 0 |
| 17 | Backend Sprint-14..18 fast subset | 310 / 310 |

## Hard-rule audit (full Sprint-18)

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied |
| No submit / post / pay | applied -- not added to WRITE_TOOLS |
| No file delete | applied |
| No file create on disk | applied |
| No multi-file apply | applied |
| No remote push | applied |
| No trust graduation for `send_existing_draft` | enforced -- TRUST_FORBIDDEN_TOOLS + tests |
| No trust graduation for `file_change_proposal.apply` | enforced -- same |
| No trust graduation for `git_commit_approved_patch` | enforced -- same |
| No trust graduation for any high-risk tool | enforced -- only 3 eligible tools, all draft-class |
| No auto-escalation without explicit trust policy | enforced -- `set_max_auto_tier` is sole mutator, founder-only, confirmation-phrase-walled |
| Daena cannot raise her own trust tier | enforced -- `is_founder` is set by `require_role("FOUNDER")` API dependency; tool dispatches NEVER reach this endpoint |
| Auto-approval invalid if `rejection_count > 0` | enforced -- wall #5 of `should_auto_approve` + tested |
| Auto-approval requires payload-derived `template_class` match | enforced -- `compute_template_class` deterministic per tool_id; trust grants per (tool, template_class) tuple |
| Routine-initiated dispatches cannot auto-execute | enforced -- `DispatchInitiator.SCHEDULER` always refused by wall #2 |

## Test counts (Sprint-14..18 fast subset)

```
backend/tests/test_controlled_execution_design_lock.py             7  (S14, renamed S15+S17)
backend/tests/test_controlled_execution_dispatch.py               10  (S14)
backend/tests/test_gmail_create_draft_handler.py                   7  (S14)
backend/tests/test_gmail_send_existing_draft_handler.py           19  (S15+S16)
backend/tests/test_gmail_draft_snapshot.py                        17  (S16)
backend/tests/test_calendar_tentative_event_handler.py             8  (S14)
backend/tests/test_file_change_proposal_handler.py                18  (S14)
backend/tests/test_file_proposal_apply_design_lock.py             17  (S15, flipped S17)
backend/tests/test_trust_ladder.py                                 5  (S14)
backend/tests/test_google_readiness_test.py                       17  (S16)
backend/tests/test_local_file_safety.py                           40  (S17)
backend/tests/test_file_change_proposal_apply_handler.py          23  (S17)
backend/tests/test_self_healing_patch_proposal.py                 15  (S17)
backend/tests/test_self_healing_apply_loop.py                      8  (S17)
backend/tests/test_git_commit_approved_patch_handler.py           13  (S17)
backend/tests/test_gmail_send_dispatch_integration.py              6  (S17)
backend/tests/test_trust_policy.py                                25  (S18 NEW)
backend/tests/test_trust_api.py                                   10  (S18 NEW)
backend/tests/test_trust_auto_approve.py                           7  (S18 NEW)
backend/tests/test_routine_autonomy.py                            15  (S18 NEW)
backend/tests/test_trust_chat_commands.py                         23  (S18 NEW)
                                                                 ----
                                                                  310
```

310 / 310 pass. tsc 0 errors.

## How far from 100% Daena VP

Per the operator's estimate at sprint kick-off:

> After Sprint-18 trust ladder + routine autonomy: ~91-92%

Daena now:
- has the SIX-tool Phase 3 surface (unchanged from Sprint-17)
- has a REAL trust ladder with explicit policy semantics (NEW)
- has founder-only tier raise via confirmation phrase (NEW)
- has initiator-aware auto-approval that fires for OPERATOR only (NEW)
- has a routine autonomy scheduler skeleton with pause/resume (NEW)
- has 6 deterministic VP chat commands answering trust questions (NEW)
- still cannot submit / post / pay
- still cannot delete / create files
- still cannot multi-file apply
- still cannot raise her own trust tier
- still cannot push to a remote
- still cannot bypass any gate
- still cannot auto-execute scheduler-initiated work

## The autonomy spine (now layered)

```
operator-initiated dispatch
  | initiator = OPERATOR
  v
trust_policy.should_auto_approve(tool, payload, OPERATOR)
  | walls 1..6
  v
  pass? -> mutate GoaRequest to APPROVED
            decision_reason = "trust_graduated:<class>"
  fail? -> leave PENDING; operator approves manually
  |
  v
controlled_execution_dispatch (Sprint-14 spine, six gates)
  | gate 4 sees status=APPROVED
  v
handler runs (Sprint-15..17)
```

```
scheduler-initiated dispatch
  | initiator = SCHEDULER
  v
trust_policy.should_auto_approve(tool, payload, SCHEDULER)
  | wall #2 ALWAYS refuses
  v
  pass? -> never reachable
  fail? -> leave PENDING; operator approves manually
```

```
self-healing-initiated dispatch
  | initiator = SELF_HEALING
  v
trust_policy.should_auto_approve(tool, payload, SELF_HEALING)
  | wall #2 ALWAYS refuses
  v
  pass? -> never reachable
  fail? -> leave PENDING; operator approves manually
```

## Sprint-18 commit log

```
88b3170  feat: add trust ladder policy engine
642ee4f  feat: add trust ladder UI
2357389  feat: auto approve trusted low-risk draft actions
bf0e7f3  feat: add routine autonomy scheduler
4df3734  feat: add trust-aware VP chat commands
(this)   docs: add sprint 18 trust ladder smoke
```

## End

If the operator approves, push fast-forward to `origin/master`.
No deploy. No push from any handler. No file delete. No broader
external action expansion.

The trust ladder is real. Walls about walls held all the way through.

Mythos out.
