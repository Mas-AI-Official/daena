# PR-7 -- VP Business Execution Chat Commands

**Sprint:** DAENA-SPRINT-19-BUSINESS-EXECUTION-LOOPS
**PR:** 7 of 8
**Date:** 2026-05-06

## Goal

Eight deterministic chat commands the operator can use to drive
the business loop from text. NO LLM in the path. Authoritative
state from `Opportunity` + `GoaRequest` tables. Honest "not
implemented in v1" responses for the two commands that cannot
be safely auto-run from chat.

## What ships

`backend/app/services/vp_business_commands.py` (new):

* Eight regex patterns, order-sensitive:
    1. `find ways to make money today` -> top-10 opportunities
    2. `find grants for MAS-AI` -> grant-typed opps
    3. `find hackathons we can join` -> hackathon-typed opps
    4. `find (customer) leads` -> customer_lead-typed opps
    5. `draft outreach for top N` -> NOT implemented in v1
    6. `what (still) needs my approval` -> pending GoaRequests
    7. `send the approved draft` -> NOT implemented in v1
    8. `what did you do today` -> 24h decision summary
* `parse_and_run(text, db, tenant_id) -> BusinessChatResult`
  with `matched / command / summary / structured`.

`backend/app/api/v1/business_chat.py` (new): thin wrapper
endpoint `POST /api/v1/business/chat`.

`backend/app/api/v1/__init__.py` (modified): mount router.

## Mythos design choices

**Deterministic, no LLM.** Same pattern as Sprint-18 `trust_chat`.
Regex matches phrase, Python runner reads DB, response is
structured table the frontend renders. No hallucinated
permissions, no fabricated leads.

**`draft_outreach_for_top` and `send_approved_draft` honestly
return implemented=False in v1.** The brief lists them, but
chat-driven auto-draft requires recipient discovery (which v1
does not do automatically) and chat-driven send requires
guessing which approval row + Gmail draft (which is unsafe).
Operator routes through the Opportunities page or the Approvals
page for these. Honesty over fake convenience.

**`find_ways_to_make_money` does NOT trigger fresh discovery.**
Chat is read-only by default. Operator runs discovery via the
inbox button or via routine_autonomy. This avoids "Daena said
the magic phrase and now hits 5 sources" -- discovery is an
operation the operator should consciously trigger.

**`what did you do today` reads GoaRequest decisions in last 24h.**
Not the audit log, not any other table -- just decided approvals.
This is a deliberately narrow definition of "what you did" so
the response is always quick and accurate. Future sprints can
broaden the surface.

**`what needs my approval` is type-aware.** Returns total pending
+ separately counts approvals where action_type is in the
controlled-execution write tools set. Operator sees both
"how big is my queue" and "how much of it is real-world action."

## Locked invariants

| Invariant | Where |
|---|---|
| Eight phrases recognized | `TestPatternMatch::test_phrase_recognized` (13 parametric cases) |
| Unrelated text does not match | `test_unrelated_text` |
| find_grants returns only grants | `TestFindCommands::test_find_grants_filters_to_grants` |
| find_hackathons filters | `test_find_hackathons` |
| find_customer_leads filters | `test_find_customer_leads` |
| find_ways returns mixed types | `test_find_ways_to_make_money_returns_all_types` |
| draft_outreach NOT implemented in v1 | `TestNotImplementedCommands::test_draft_outreach_returns_not_implemented` |
| send NOT implemented in v1 | `test_send_returns_not_implemented` |
| approval queue counts pending + controlled | `TestApprovalQueueCommand::test_what_needs_approval_lists_pending` |
| No command output leaks sent_at / applied_at / commit_sha | `TestNoForbiddenSurfaceLeak` |
| Summary is deterministic (no hedging) | `TestDeterministicSummary` |

## Hard rules audit

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied |
| Commands use backend state | enforced -- runners only call DB queries |
| No hallucinated sends | enforced -- send command returns implemented=False |
| Send command only routes to controlled send bridge | enforced -- this PR explicitly does NOT call the bridge from chat |
| If Gmail/OAuth not ready, explain blocker | applied -- bridge tier exists for this; chat surfaces approval queue |

## Tests

```
backend/tests/test_vp_business_commands.py    23 tests
```

23/23 pass.

## Files

```
new:        backend/app/services/vp_business_commands.py
new:        backend/app/api/v1/business_chat.py
new:        backend/tests/test_vp_business_commands.py
modified:   backend/app/api/v1/__init__.py
new:        docs/Ultraview/PR_VP_BUSINESS_CHAT_COMMANDS_REPORT.md
```

## Next: PR-8 -- Sprint-19 Smoke + Final Report
