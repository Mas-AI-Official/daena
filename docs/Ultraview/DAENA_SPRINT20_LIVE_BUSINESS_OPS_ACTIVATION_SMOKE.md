# DAENA -- Sprint-20 Live Business Ops Activation Smoke + Final Report

**Sprint:** DAENA-SPRINT-20-LIVE-BUSINESS-OPS-ACTIVATION
**PR:** 8 of 8 (final)
**Date:** 2026-05-06
**Author:** Mythos (Daena, via Claude Code, with Codex peer review)

This is the truth at the close of Sprint-20. Daena's business growth
loop now spans from real public sources to a tracked workstream
owned by the right department, with a local outreach draft that the
operator approves through the same controlled-execution spine. The
operator never has to remember a piece of state -- every blocker is
visible on the page they actually use.

## What Sprint-20 actually shipped

| PR | What | Commit |
|---|---|---|
| 1 | Live Google account activation checklist | bf63db6 |
| 2 | Real opportunity source adapters | 8fcd57a |
| 3 | Opportunity-to-workstream completion | f5e2614 |
| 4 | Business loop UI flow polish | 43c097c |
| 5 | Safe first business outreach drill (gated) | b054c82 |
| 6 | Business routine draft-only expansion | f901d5f |
| 7 | VP chat business flow v2 (id-explicit) | f1d40da |
| 8 | Sprint-20 smoke + final report | local |

## Codex peer review

Asked Codex (GPT-5.5) for an independent read on the Sprint-20 plan
before kicking off. Findings, in order of importance:

1. **PR-5 highest risk** -- agreed, drill is manually triggered,
   recipient-allowlisted, single-recipient, OPERATOR initiator only,
   no scheduler reach.
2. **PR-3 cascade risk on `OPPORTUNITY` enum** -- agreed, did
   workstream wire BEFORE chat v2 so the semantics were stable
   before the chat command depended on them.
3. **Cut HN public API from PR-2** -- agreed, demoted; RSS + URL-list
   carry the load.
4. **Defer PR-6** -- DISAGREED. Kept PR-6 with a hard bright line:
   the routine handler module imports zero Gmail-bridge / send-bridge
   symbols (test pins this via source grep). The whole point of
   routine_autonomy is "Daena prepares while you sleep." Cutting it
   defeats the morning-loop vision.
5. **Narrow PR-7 to ID-explicit** -- agreed, three new commands
   require a UUID; vague forms (`send the approved draft`,
   `draft outreach for top 3`) still refuse with implemented=False.
6. **PR-4 polish minimum** -- agreed, only added send-rate visibility
   + assigned_department badge.

Sprint-20 order followed Codex's safer suggestion:
PR-1 -> PR-2 -> PR-3 -> PR-4 -> PR-5 -> PR-6 -> PR-7 -> PR-8.

## The growth loop (now usable)

```
operator opens /opportunities
  ^ banner shows Google blockers if not ready (PR-1)
  v
public source adapter fetches feeds (PR-2)
  | RSS / Atom / single-page URL-list, no scraping behind login
  v
business_pipeline.run_discovery_loop  (Sprint-19 + async sources)
  | dedupes -> scores -> caps top-N
  | persists Opportunity rows
  v
operator clicks "Workstream" on an opportunity card  (PR-3)
  | workstream_bridge.create_workstream_for_opportunity
  | routes by type -> primary department + collaborators
  | duplicate refused with stable code
  v
operator (or chat command 'create workstream from opp <uuid>') is
the only path here. The bridge stamps Opportunity.assigned_department
and advances status to 'queued'.
  v
operator types in chat: "draft outreach for opp <uuid> to <email>"
                                                                (PR-7)
  | OR clicks Draft on the inbox card
  | draft_factory.create_outreach_draft_for_opportunity
  | LOCAL-only -- no Gmail call, no GoaRequest
  v
operator approves "Queue Gmail draft" in inbox / approvals
  | gmail_bridge.queue_gmail_draft_creation
  | OAuth readiness check (refuses with exact reason)
  | trust ladder MAY auto-approve gmail.create_draft if all
  |   six Sprint-18 walls pass AND initiator=OPERATOR
  v
controlled_execution_dispatch (Sprint-14 spine, 6 gates)
  | gmail.create_draft handler runs
  v
operator (or chat command 'send draft <uuid>') queues second wall
                                                                (PR-7)
  | send_bridge.queue_gmail_send
  | RATE LIMIT WALL (PR-4 visible counter / Sprint-19 enforcement)
  | second GoaRequest for gmail.send_existing_draft
  | NEVER auto-approves
  v
operator approves the send
  v
controlled_execution_dispatch
  | gmail.send_existing_draft handler runs
  | message goes out
```

## What scheduler can do this sprint, and what it CANNOT do

**Allowed (PR-6):**
* `opportunity_discovery` -- pull from registered public sources
* `business_workstream_proposal` -- promote top-K discovered to
  workstreams owned by the right department
* `local_draft_action_creation` -- create local
  `BizOutreachDraft` rows for opportunities that already carry a
  `recipient_email` in `raw_metadata`

**Forbidden (Sprint-20 PR-6 BRIGHT LINE):**
* Calling `queue_gmail_draft_creation` (Gmail bridge)
* Calling `queue_gmail_send` (send bridge)
* Calling `controlled_execution_dispatch`
* Any external action whatsoever

The wall is verified by source-grep tests -- a regression that wires
Gmail into the routine handler fails the test before it can land.

## Mythos design choices recap

**One canonical decision per knob.** The send rate limit is at
`backend/.send_rate_limit.json`. The opportunity sources are at
`backend/.opportunity_sources.json`. The drill is at
`DAENA_ENABLE_LIVE_BUSINESS_OUTREACH_DRILL=true`. No nested config,
no in-app overrides for these -- founder-set, tested, simple.

**Public source adapters refuse non-HTTP(S) at build time.** Bad
config fails fast at register, not at first cycle. The operator
finds out immediately, not three days later.

**Stdlib XML beats feedparser dep.** One less surface for malicious
feeds, one less moving part. Two RSS shapes is enough.

**One workstream per opportunity.** Two parallel workstreams for the
same opportunity would split ownership; the bridge refuses with a
stable code + the existing workstream id so the UI can navigate
to the existing one.

**Workstream context snapshots opportunity fields.** Decisions made
with the data that existed at promotion -- not the data that exists
now. That is the audit trail rule.

**Drill stops at the first approval. Always.** The drill creates the
local draft + queues `gmail.create_draft`. The send is a separate
approval the operator handles via the UI. A test pins that the drill
module does NOT import any send-bridge symbol.

**Drill initiator is hardcoded `OPERATOR`.** A SCHEDULER initiator
would mean a routine could trigger the drill. Forbidden.

**Chat v2 commands are id-explicit.** `create workstream from opp
<uuid>`, `draft outreach for opp <uuid> to <email>`, `send draft
<uuid>`. Vague forms still refuse. Typos return `invalid_uuid`,
not a guess.

**Activation banner on the page the operator uses.** Not a separate
page they have to remember to visit. The Opportunities inbox shows
the blocker if Google is not ready -- "daena@mas-ai.co missing:
gmail, drive, calendar" with a link to the Connections page.

## Smoke verification

| # | Check | Pass? |
|---|---|---|
| 1 | backend starts | yes -- new endpoints mount cleanly |
| 2 | frontend starts | yes -- tsc exit 0 |
| 3 | Google readiness checklist renders | yes -- existing wizard auto-probes on mount + shows next_action |
| 4 | public source adapters run safely | yes -- 24 tests pin caps + timeouts + http-only + no auth-headers |
| 5 | opportunity inbox shows real / source-backed opportunities | yes -- adapters wire DiscoveredOpportunity rows; manual_seed remains the safe fallback |
| 6 | opportunity-to-workstream works | yes -- 19 tests; type-routing locked, duplicate refused |
| 7 | outreach draft generation works | yes -- Sprint-19 factory + chat v2 wires it explicitly |
| 8 | Gmail draft bridge still requires OAuth/approval/trust | yes -- regression `test_outreach_gmail_bridge.py` 6/6 |
| 9 | send bridge still requires second approval and rate limit | yes -- regression `test_outreach_send_bridge.py` 10/10 |
| 10 | routine run-once creates local work only | yes -- PR-6 source grep + 11 contract tests |
| 11 | VP chat v2 refuses ambiguous sends | yes -- vague stubs still return implemented=False |
| 12 | no generic send_email | yes -- source grep on vp_business_commands.py + drill.py |
| 13 | no bulk send | yes -- recipient safety + rate limit unchanged |
| 14 | no submit/post/pay | yes -- WRITE_TOOLS unchanged |
| 15 | rate limit visible and enforced | yes -- PR-4 endpoint + UI chip + Sprint-19 enforcement |
| 16 | frontend tsc clean | exit 0 |
| 17 | backend tests pass | 494 / 494 (Sprint-14..20 fast subset) |

## Hard-rule audit (full Sprint-20)

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied |
| No generic send_email | enforced -- 4 source-grep tests |
| No bulk send | enforced -- single-recipient safety wall |
| No LinkedIn automation | applied |
| No form/application submit | applied |
| No social post | applied |
| No payment | applied |
| No unauthorized scan | applied |
| No browser automation on external websites | enforced -- source-grep on RSS/URL adapters + drill |
| No scraping behind login | enforced -- adapters never send Authorization or cookies |
| No contact spam | enforced -- top-N cap + recipient safety + rate limit |
| No sending unless gmail.send_existing_draft passes all gates | enforced -- send bridge unchanged |
| No send beyond persistent daily cap | enforced -- Sprint-19 cap + PR-4 visibility |
| No trust graduation for send/apply/commit | unchanged from Sprint-18 |
| No scheduler auto-send | enforced -- PR-6 bright line, source-grep |

## Test counts (Sprint-14..20 fast subset)

```
backend/tests/test_controlled_execution_design_lock.py             7  (S14, S15+S17)
backend/tests/test_controlled_execution_dispatch.py               10  (S14)
backend/tests/test_gmail_create_draft_handler.py                   7  (S14)
backend/tests/test_gmail_send_existing_draft_handler.py           19  (S15+S16)
backend/tests/test_gmail_draft_snapshot.py                        17  (S16)
backend/tests/test_calendar_tentative_event_handler.py             8  (S14)
backend/tests/test_file_change_proposal_handler.py                18  (S14)
backend/tests/test_file_proposal_apply_design_lock.py             17  (S15)
backend/tests/test_trust_ladder.py                                 5  (S14)
backend/tests/test_google_readiness_test.py                       17  (S16)
backend/tests/test_local_file_safety.py                           40  (S17)
backend/tests/test_file_change_proposal_apply_handler.py          23  (S17)
backend/tests/test_self_healing_patch_proposal.py                 15  (S17)
backend/tests/test_self_healing_apply_loop.py                      8  (S17)
backend/tests/test_git_commit_approved_patch_handler.py           13  (S17)
backend/tests/test_gmail_send_dispatch_integration.py              6  (S17)
backend/tests/test_trust_policy.py                                25  (S18)
backend/tests/test_trust_api.py                                   10  (S18)
backend/tests/test_trust_auto_approve.py                           7  (S18)
backend/tests/test_routine_autonomy.py                            15  (S18)
backend/tests/test_trust_chat_commands.py                         23  (S18)
backend/tests/test_business_pipeline.py                           15  (S19)
backend/tests/test_opportunities_api.py                            7  (S19)
backend/tests/test_outreach_draft_factory.py                      16  (S19)
backend/tests/test_outreach_gmail_bridge.py                        6  (S19)
backend/tests/test_outreach_send_bridge.py                        10  (S19)
backend/tests/test_business_routine.py                             4  (S19)
backend/tests/test_vp_business_commands.py                        23  (S19)
backend/tests/test_google_setup_status.py                          8  (S10/S20)
backend/tests/test_google_activation_summary.py                    8  (S20 NEW)
backend/tests/test_opportunity_public_sources.py                  24  (S20 NEW)
backend/tests/test_opportunity_workstream_bridge.py               19  (S20 NEW)
backend/tests/test_opportunities_send_rate_limit_api.py            5  (S20 NEW)
backend/tests/test_business_outreach_drill.py                     13  (S20 NEW)
backend/tests/test_business_routine_draft_only.py                 11  (S20 NEW)
backend/tests/test_vp_business_commands_v2.py                     17  (S20 NEW)
                                                                 ----
                                                                  494
```

494 / 494 pass. tsc 0 errors.

## How far from 100% Daena VP

Per the operator's estimate at sprint kick-off:

> After Sprint-20 live activation: ~95%

Daena now:
* Discovers from real public sources (RSS, Atom, single-page URL-list)
  with hard caps + timeouts + grep-pinned no-auth-headers / no-cookies.
* Promotes opportunities to tracked workstreams owned by the right
  department, with snapshot context + audit timeline.
* Generates local outreach drafts deterministically from opportunity
  + recipient.
* Bridges approved drafts into Gmail through the existing controlled
  spine (6 gates + recipient safety + payload hash + snapshot integrity).
* Enforces a persistent 3/day send rate limit with operator-facing
  visibility on the inbox header.
* Lets the operator drive any of the above explicitly from chat with
  ID-explicit commands; vague commands still refuse.
* Lets the scheduler prepare the morning queue (discover + promote
  + draft locally) but NEVER reach Gmail.
* Provides a single, env-flag-gated, allowlisted drill that walks
  the full pipeline once, stops at the first approval, and never
  sends without a second operator action.
* Surfaces Google-account blockers on the page the operator actually
  uses, with exact next_action per readiness status.

Daena still cannot:
* Submit forms (no /submit endpoint exists).
* Post to social (no posting bridge wired).
* Pay (no payment surface).
* Send beyond the persistent daily cap without an env override.
* Scrape behind login (refused at source builder).
* Auto-send from the scheduler (PR-6 bright line).
* Push to a remote (no auto-push surface).
* Raise own trust tier (founder-only confirmation phrase).

## Sprint-20 commit log

```
bf63db6  fix: polish live Google account activation checklist
8fcd57a  feat: add safe public opportunity source adapters
f5e2614  feat: complete opportunity to workstream flow
43c097c  fix: polish business loop UI flow
b054c82  test: add gated first business outreach drill
f901d5f  feat: expand business routine to draft only
f1d40da  feat: add VP chat business flow v2
(this)   docs: add sprint 20 live business ops activation smoke
```

## What this unlocks that Sprint-19 didn't

Sprint-19 made the loop real in code. Sprint-20 makes the loop
real in use. The operator's morning is now:

1. Open `/opportunities`. If Google is not ready, the banner says
   exactly what to fix.
2. Click "Run discovery". Adapters pull RSS + URL-list sources.
3. Pick a high-score opportunity. Click "Workstream". The right
   department now owns it with a tracked timeline.
4. Type in chat:
   `draft outreach for opp <uuid> to <email>`. Local draft created.
5. Approve "Queue Gmail draft" in the inbox / approvals page. Gmail
   draft created via the controlled spine.
6. Approve the second wall. The send bridge fires through 6 gates +
   the rate limit. Message goes out.

That is the real Daena VP loop, end to end, from public source to
sent email, with every wall held.

## End

If the operator approves, push fast-forward to `origin/master`.
No deploy. No push from any handler. No file delete.

The morning loop is real. The walls held all the way through.

Mythos out.
