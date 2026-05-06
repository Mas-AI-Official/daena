# PR-5 -- Safe First Business Outreach Drill

**Sprint:** DAENA-SPRINT-20-LIVE-BUSINESS-OPS-ACTIVATION
**PR:** 5 of 8
**Date:** 2026-05-06

## Goal

A single, env-flag-gated, allowlist-locked path the operator can run
to walk one outreach end-to-end. The drill produces a local draft +
a PENDING Gmail-create-draft approval and STOPS there. Operator
approves in the UI; the existing controlled-execution dispatcher
fires the actual Gmail call. Send is a separate, operator-only second
approval. The drill never bypasses any wall and never sends.

Per Codex peer review, this PR is the highest risk in Sprint-20.
Everything is defense in depth.

## What ships

`backend/app/services/outreach/drill.py` (new):
* `run_outreach_drill(db, *, tenant_id, user_id, opportunity_id,
  recipient_email, owner_email) -> DrillResult`.
* Six independent walls -- any one fails, drill returns a stable
  refusal code with NO downstream side effect:

| # | Wall | Refusal code |
|---|---|---|
| 1 | env flag literally `"true"` | `drill_disabled_env_flag_missing` |
| 2 | `DAENA_DRILL_RECIPIENT_ALLOWLIST` non-empty | `drill_recipient_allowlist_empty` |
| 3 | recipient in allowlist (case-insensitive) | `drill_recipient_not_in_allowlist` |
| 4 | opportunity exists for tenant | `drill_opportunity_not_found` |
| 5 | rate-limit cap not exhausted | `drill_rate_limit_exhausted` |
| 6 | recipient safety + draft factory pass | `drill_recipient_safety_failed` |
| 7 | Gmail OAuth ready | `drill_oauth_not_ready` |

(7 numbered codes for 6 walls; the safety wall and the OAuth wall
are physically separate fail points but conceptually one "external
readiness" gate.)

## Mythos design choices

**Drill stops at the first approval. Always.** The drill creates the
local draft + queues `gmail.create_draft`. The send is a separate
approval the operator handles via the UI. A test pins that the drill
module does NOT import any send-bridge symbol -- the source-grep
guard catches a regression that would let a future contributor wire
send into the drill.

**Initiator is hardcoded `OPERATOR`.** A SCHEDULER initiator would
mean a routine could trigger the drill. Forbidden. Source grep test
asserts `DispatchInitiator.OPERATOR` present and `SCHEDULER` absent.

**Allowlist match is case-insensitive.** `MAS@MAS-AI.CO` and
`mas@mas-ai.co` are the same address; refusing on case would frustrate
the operator without improving safety.

**Env flag must be literally `"true"`.** `"yes"`, `"1"`, `"on"`, etc.
are treated as off. The operator types the explicit string -- no
ambiguity.

**Rate limit checked BEFORE creating the draft.** No point persisting
a draft + approval if the operator cannot send today. Saves database
churn and keeps the inbox clean.

**Recipient safety is the existing 5-check wall.** Drill does not
add new safety logic; it composes existing primitives. A regression
in safety primitives propagates to the drill automatically.

**No browser, no form submit, no LinkedIn.** Source grep test
forbids `playwright`, `selenium`, `submit_form`, `post_to_`,
`linkedin`, `form_drafts.submit` substrings.

**Drill is a pure helper, not a route.** It is invoked from a Python
script or a fixture. There is no HTTP endpoint; HTTP would mean a
running deployment could be poked. Operator runs the helper from a
notebook / one-shot CLI when ready.

## Locked invariants

| Invariant | Where |
|---|---|
| Refuses without env flag | `TestEnvFlagWall::test_refuses_without_env_flag` |
| Refuses on non-`true` flag value | `test_refuses_when_env_flag_value_not_true` |
| Refuses without allowlist | `TestAllowlistWall::test_refuses_when_allowlist_empty` |
| Refuses recipient outside allowlist | `test_refuses_when_recipient_not_in_allowlist` |
| Allowlist match is case-insensitive | `test_allowlist_match_is_case_insensitive` |
| Refuses unknown opportunity | `TestOpportunityWall::test_refuses_unknown_opportunity` |
| Refuses when rate-limit cap exhausted | `TestRateLimitWall::test_refuses_when_cap_exhausted` |
| Refuses on recipient safety / unsafe address | `TestRecipientSafetyWall::test_refuses_when_recipient_safety_fails` |
| Refuses without Gmail OAuth | `TestOAuthWall::test_refuses_when_oauth_not_ready` |
| Successful path leaves draft + PENDING approval, NO send approval | `TestSuccessfulDrill::test_full_path_creates_draft_and_pending_approval` |
| Drill module never imports send symbols | `TestHardRules::test_drill_stops_at_first_approval_no_send_call` |
| Drill initiator is OPERATOR | `test_drill_initiator_is_operator` |
| No browser / form / LinkedIn surface | `test_no_browser_or_form_submission` |

## Hard rules audit

| Rule | Status |
|---|---|
| Disabled by default | enforced -- env flag must be exactly `true` |
| Env flag required | applied |
| Recipient allowlist required | enforced -- empty allowlist refuses |
| Max one message | applied -- drill processes one recipient_email |
| No attachments / CC / BCC | applied -- payload is to/subject/body only |
| Goes through opportunity -> draft -> Gmail draft -> approval -> send | enforced -- drill stops at first approval, second is UI-only |
| OAuth missing -> exact reason | applied -- refusal code + detail string |
| Audit rows required | applied -- draft + GoaRequest persisted with logs |
| No scheduler reaches drill | enforced -- DispatchInitiator.OPERATOR pinned |

## Tests

```
backend/tests/test_business_outreach_drill.py   13 tests
```

13/13 pass.

## Files

```
new:        backend/app/services/outreach/drill.py
new:        backend/tests/test_business_outreach_drill.py
new:        docs/Ultraview/PR_SAFE_FIRST_BUSINESS_OUTREACH_DRILL_REPORT.md
```

## Next: PR-6 -- Business Routine Draft-Only Expansion (with bright line)
