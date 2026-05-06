# PR-4 -- Controlled Gmail Draft Bridge

**Sprint:** DAENA-SPRINT-19-BUSINESS-EXECUTION-LOOPS
**PR:** 4 of 8
**Date:** 2026-05-06

## Goal

Connect outreach drafts to the existing Sprint-14 controlled
execution dispatcher. The bridge produces a `GoaRequest` for
`gmail.create_draft` and (optionally) graduates it via the
trust ladder. The dispatcher remains the single write surface;
the bridge does NOT call the Gmail HTTP API.

## What ships

`backend/app/services/outreach/gmail_bridge.py` (new):

* `queue_gmail_draft_creation(db, *, outreach_draft_id,
  owner_email, tenant_id, user_id, initiator) -> GmailDraftBridgeResult`.
* Validates the outreach draft exists and is `status='drafted'`.
* Validates Gmail OAuth readiness for the `(tenant, user, owner_email)`
  triple before any approval row is created.
* Creates a `GoaRequest` with `action_type='gmail.create_draft'`,
  payload carrying `to / subject / body / outreach_draft_id /
  payload_hash / owner_email`.
* Calls `maybe_apply_trust_auto_approval` -- if all 6 trust walls
  pass for an OPERATOR initiator, the approval row flips to
  status='APPROVED' immediately. Scheduler / self-healing
  initiators NEVER auto-approve (wall #2).
* Stamps `BizOutreachDraft.create_draft_approval_id` and advances
  status to `queued_create_draft`.
* NEVER raises -- typed result with stable `refusal_code`.

## Mythos design choices

**Bridge does not dispatch.** The flow is:
`bridge -> approval row -> dispatcher`. Two distinct steps.
Why: the dispatcher already enforces 6 gates including the
payload-hash verification. Calling it from inside the bridge
would mean the bridge has to assemble a `ControlledExecutionRequest`
with all the consent/asset_shield/policy_allowlist booleans --
which the operator's UI is responsible for providing.

The bridge's job is "make a valid approval row that the existing
dispatch endpoint can satisfy." The dispatcher's job is "verify
the approval is real and run the handler."

**Initiator-aware. Default = OPERATOR.** Caller MUST pass the
initiator. Scheduler-initiated outreach (PR-6) passes
`SCHEDULER`, which trust wall #2 always refuses regardless of
counters. This is the same pattern as Sprint-18.

**OAuth readiness checked BEFORE creating the approval row.**
Otherwise a missing OAuth would create a pending approval that
the dispatcher refuses with `oauth_not_connected:google` -- the
operator clicks approve, sees the dispatcher refuse, and has to
go connect Google. Honest feedback: refuse early at the bridge
with `gmail_oauth_not_ready`.

**Status precondition `drafted`.** A draft already in
`queued_create_draft` or further can't be re-bridged (would
create duplicate approvals). The check is positive (`== drafted`)
not negative (`!= sent`) -- positive checks are auditable,
negative checks accumulate edge cases.

## Locked invariants

| Invariant | Where |
|---|---|
| Unknown outreach_draft_id refused | `TestRefusals::test_unknown_outreach_draft` |
| Wrong status refused with stable code | `test_draft_status_not_drafted` |
| Missing Gmail OAuth refused early | `test_missing_oauth` |
| Pending approval when trust not graduated | `TestSuccessPath::test_pending_when_trust_not_graduated` |
| Auto-approves when all 6 trust walls pass | `test_auto_approves_when_trust_graduated` |
| Scheduler initiator never auto-approves | `test_scheduler_initiator_never_graduates` |
| Outreach draft linked to approval | `test_pending_when_trust_not_graduated` (asserts `create_draft_approval_id` set) |
| Outreach draft status advances to `queued_create_draft` | same |
| Bridge NEVER raises | every test exercises the typed-result contract |

## Hard rules audit

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied (only credential presence is checked, value never dereferenced or logged) |
| No generic send_email | applied -- this PR does not unlock send |
| owner_email required | enforced + tested |
| Gmail OAuth readiness required | enforced + tested |
| create draft only | applied -- tool_id locked to `gmail.create_draft` |
| no send | applied -- send is not in this PR |
| audit row required | enforced -- approval row IS the audit row, plus `outreach.gmail_bridge.queued` log line |
| trust ladder may auto-approve only if all six walls pass | enforced via `maybe_apply_trust_auto_approval` (Sprint-18) |
| if not trusted, approval modal required | enforced -- approval row left as PENDING |

## Tests

```
backend/tests/test_outreach_gmail_bridge.py    6 tests
```

6/6 pass.

## Files

```
new:        backend/app/services/outreach/gmail_bridge.py
new:        backend/tests/test_outreach_gmail_bridge.py
new:        docs/Ultraview/PR_CONTROLLED_GMAIL_DRAFT_BRIDGE_REPORT.md
```

## Next: PR-5 -- Controlled Send Bridge with Rate Limit
