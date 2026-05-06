# PR-7 -- VP Chat Business Flow v2 (narrow, ID-explicit)

**Sprint:** DAENA-SPRINT-20-LIVE-BUSINESS-OPS-ACTIVATION
**PR:** 7 of 8
**Date:** 2026-05-06

## Goal

Make chat useful for the business loop without ever guessing
recipients, opportunity ids, or approval rows. Three new commands,
each requiring an explicit UUID. Vague Sprint-19 stubs ("send the
approved draft", "draft outreach for top 3") still refuse with
implemented=False -- the v2 commands are the path the operator types
when they want action.

Per Codex peer review: narrow surface, ID-explicit only. Anything
conversational beyond that increases accidental-action risk.

## What ships

`backend/app/services/vp_business_commands.py`:
* Three new patterns + runners:
    1. `create_workstream_from_opp_by_id`
       Pattern: `create workstream (from|for) opp <uuid>`.
       Runner: calls `workstream_bridge.create_workstream_for_opportunity`.
    2. `draft_outreach_for_opp_to`
       Pattern: `draft outreach for opp <uuid> to <email>`.
       Runner: calls `draft_factory.create_outreach_draft_for_opportunity`.
       LOCAL-ONLY -- does NOT queue Gmail draft (operator runs that
       step from the inbox / approvals page).
    3. `send_approved_draft_by_id`
       Pattern: `send (approved) draft <uuid>`.
       Runner: calls `send_bridge.queue_gmail_send` with explicit
       draft id. NEVER auto-approves (Sprint-18 wall #1 + Sprint-19
       send_bridge defensive check). NEVER bypasses rate limit.
* Vague Sprint-19 stubs preserved exactly. Tests pin both shapes.
* `parse_and_run(text, db, tenant_id, user_id)` -- user_id new param,
  required for the three id-explicit commands. Vague commands work
  without it (read-only).

`backend/app/api/v1/business_chat.py`:
* Endpoint passes `user.id` through.
* Commits the DB session ONLY when one of the three id-explicit
  commands matches. Vague reads stay rollback-safe.

## Mythos design choices

**Order matters in the pattern table.** Sprint-20 explicit-id
patterns are placed BEFORE the corresponding Sprint-19 vague stubs
so a precise input like `send draft <uuid>` routes to the
implementation. The vague forms stay last so `send the approved
draft` (no id) still hits the implemented=False stub.

**`draft_outreach_for_opp_to` is local-only.** The chat runner does
NOT call the Gmail bridge. Why: chat-driven Gmail-bridge invocation
plus an existing trust-graduated tier could produce auto-created
Gmail drafts the operator did not visually approve. The wall: chat
makes the LOCAL draft, operator approves Gmail-create-draft via the
inbox (which calls the bridge with explicit operator-initiator).

**`send_approved_draft_by_id` is the operator's express path.** The
operator typed the exact draft UUID -- no guessing. The send_bridge
already enforces all six dispatch gates + rate-limit + the Sprint-18
TRUST_FORBIDDEN_TOOLS wall. Chat adds nothing new; it just queues
the second-wall approval row.

**No fuzzy resolution.** If the operator typo'd a UUID, the response
is `invalid_uuid` -- not a "did you mean..." picker that could route
to the wrong opportunity. Stable refusal codes the UI can render.

**`user_id_required` for explicit-id commands.** A future test/CLI
caller that forgot to plumb user_id gets a clean refusal, not a
NoneType-on-FK crash. The error code is operator-friendly.

**Source grep guard.** The vp_business_commands.py module must not
contain `gmail.googleapis.com`, `smtp.gmail.com`, `send_email(`,
`googleapiclient`. The only sanctioned send symbol is
`queue_gmail_send` (the bridge). A regression that adds a direct
Gmail call fails the test.

## Locked invariants

| Invariant | Where |
|---|---|
| 7 patterns recognized (3 new + 4 vague) | `TestPatternRecognition::test_phrase_routes_to_expected_command` |
| Create workstream succeeds for known opp | `TestCreateWorkstreamRunner::test_creates_workstream_for_existing_opp` |
| Create workstream returns not_found code for unknown opp | `test_unknown_opp_returns_not_found` |
| Duplicate returns existing workstream id | `test_duplicate_returns_existing_id` |
| Explicit-id commands require user_id | `test_requires_user_id` |
| Draft-outreach creates local draft, no GoaRequest | `TestDraftOutreachRunner::test_creates_local_draft` |
| Draft-outreach returns not_found for unknown opp | `test_unknown_opp_returns_not_found` |
| Vague 'send the approved draft' still refuses | `TestVagueStubsRefuse::test_send_the_approved_draft_no_id_still_refuses` |
| Vague 'draft outreach for top N' still refuses | `test_draft_outreach_for_top_no_id_still_refuses` |
| No direct Gmail HTTP / generic send_email | `TestHardRules::test_module_does_not_call_gmail_http_directly` |
| Send path routes through queue_gmail_send | `test_send_path_routes_through_send_bridge_only` |

## Hard rules audit

| Rule | Status |
|---|---|
| No guessing recipient | enforced -- recipient required as explicit arg |
| No guessing approval row | enforced -- send-by-id refuses without UUID |
| No generic send | enforced -- only queue_gmail_send (the bridge) |
| No bulk | enforced -- one opp + one recipient + one draft id per call |
| Deterministic backend state | applied -- DB queries only, no LLM in path |
| Ambiguous returns options not action | enforced -- vague stubs return implemented=False |

## Tests

```
backend/tests/test_vp_business_commands_v2.py    17 tests
backend/tests/test_vp_business_commands.py       23 tests (regression)
```

40 / 40 pass.

## Files

```
modified:   backend/app/services/vp_business_commands.py
modified:   backend/app/api/v1/business_chat.py
new:        backend/tests/test_vp_business_commands_v2.py
new:        docs/Ultraview/PR_VP_CHAT_BUSINESS_FLOW_V2_REPORT.md
```

## Next: PR-8 -- Sprint-20 Live Business Ops Smoke + Final Report
