# PR-5 -- Controlled Send Bridge with Rate Limit

**Sprint:** DAENA-SPRINT-19-BUSINESS-EXECUTION-LOOPS
**PR:** 5 of 8
**Date:** 2026-05-06

## Goal

The second-approval wall for outreach. After Gmail draft is
created (PR-4), operator can queue SEND. This PR ships the
rate limit + the bridge that produces the `gmail.send_existing_draft`
approval row. Send NEVER auto-approves (Sprint-18 Wall #1 +
defensive sanity check).

## What ships

`backend/app/services/outreach/send_rate_limit.py` (new):

* Persistent JSON counter at `backend/.send_rate_limit.json`
  (gitignored), keyed by `(tenant_id, YYYY-MM-DD UTC)`.
* `get_cap_per_day()` reads `DAENA_SEND_RATE_LIMIT_PER_DAY` env
  var; default 3.
* `check_and_increment(tenant_id) -> RateLimitDecision`:
    - if `used >= cap` -> `allowed=False`, counter NOT incremented
    - if allowed -> counter incremented, file written, `allowed=True`
* `get_usage(tenant_id, day=None) -> int` for inspection.
* NEVER raises.

`backend/app/services/outreach/send_bridge.py` (new):

* `queue_gmail_send(db, *, outreach_draft_id, owner_email,
  tenant_id, user_id, initiator) -> SendBridgeResult`.
* Step order is load-bearing:
    1. Load outreach draft (refuse if missing)
    2. Status precondition: `gmail_draft_created`
    3. Linkage check: `gmail_draft_id` non-empty
    4. **Rate limit check + increment** (independent gate)
    5. Build payload + payload_hash
    6. Create `GoaRequest` for `gmail.send_existing_draft`
    7. Run `maybe_apply_trust_auto_approval` (audit only --
       send is forbidden from graduation by Sprint-18 wall #1)
    8. Defensive sanity: log error if auto_approve somehow True
    9. Stamp draft with `send_approval_id` + status
       `queued_send`
* NEVER raises.

## Mythos design choices

**Rate limit BEFORE approval row creation.** The brief says
"max 3 sends/day until founder changes policy." Putting the rate
limit INSIDE the dispatch path would mean the operator can stack
up many approval rows; one of them eventually fires; rate limit
catches it at dispatch but the queue is now bloated with
zombie-pending approvals. Better: refuse before queueing. Draft
gets `status='rate_limited'` so operator sees what was attempted.

**Counter increments on attempt, not on success.** Failed sends
still count. Otherwise an attacker who knows about the
gmail.send_existing_draft handler could trigger many failures
to silently bypass the cap. Wall: "sends attempted today" beats
"sends successful today" for safety, even if it sometimes wastes
a quota slot.

**Send NEVER auto-approves; defensive sanity check fires error.**
`gmail.send_existing_draft` is in `TRUST_FORBIDDEN_TOOLS` (Sprint-18
wall #1). The bridge still calls `maybe_apply_trust_auto_approval`
so the audit trail records the decision reason, but if it ever
returned `auto_approve=True` we log
`outreach.send_bridge.unexpected_auto_approve` at ERROR -- a
canary for future regressions.

**Defense in depth: the rate limit is INDEPENDENT.** Even if
all 6 trust walls passed AND the operator manually approved the
second time AND the dispatcher's 6 gates passed, the rate limit
can still refuse. Each gate checks a DIFFERENT invariant.

**Env-only cap mutation.** `DAENA_SEND_RATE_LIMIT_PER_DAY` is
operator-set at the OS level. Daena's runtime cannot change it
through any API. This mirrors the trust-tier-raise pattern:
significant changes require operator action outside the runtime.

## Locked invariants

| Invariant | Where |
|---|---|
| Default cap is 3 | `TestRateLimit::test_default_cap_is_three` |
| Env var override works | `test_env_override` |
| Three then refuse | `test_three_then_refuse` |
| Per-tenant isolation | `test_per_tenant_isolation` |
| Unknown draft refuses | `TestSendBridgeRefusals::test_unknown_outreach_draft` |
| Wrong status refuses | `test_wrong_status_refused` |
| Missing gmail_draft_id refuses | `test_missing_gmail_draft_id` |
| Successful queue links + advances status | `TestSendBridgeSuccess::test_queue_advances_status_and_links` |
| Send NEVER auto-approves | `test_send_never_auto_approves_even_with_forced_trust` |
| Rate limit refuses 4th send | `TestRateLimitWiredIntoBridge::test_fourth_call_refused_with_rate_limit` |
| Rate-limited draft stamped with status | same test |

## Hard rules audit

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied |
| Second approval required | enforced -- bridge creates a SECOND `GoaRequest`; the dispatcher gate 4 still requires the operator to approve it before send fires |
| Draft snapshot integrity check | enforced at HANDLER level (Sprint-16) -- this PR doesn't bypass it |
| Recipient safety check | enforced at PR-3 factory; cannot regress here |
| One recipient only | enforced at PR-3 |
| No attachments | applied -- payload only carries draft_id; the create-draft handler from PR-4 already locks no-attachments |
| No bulk | applied -- one draft per call |
| No generic send_email | applied -- tool_id locked to `gmail.send_existing_draft` |
| Rate limit max 3 sends/day | enforced + tested; configurable only via founder env var |
| Audit row required | enforced -- approval row + structured logs |
| Send graduation forever forbidden | enforced -- Sprint-18 wall #1 + defensive check |

## Tests

```
backend/tests/test_outreach_send_bridge.py    10 tests
```

10/10 pass.

## Files

```
new:        backend/app/services/outreach/send_rate_limit.py
new:        backend/app/services/outreach/send_bridge.py
new:        backend/tests/test_outreach_send_bridge.py
new:        docs/Ultraview/PR_CONTROLLED_SEND_BRIDGE_REPORT.md
```

## Next: PR-6 -- Business Routine Run-Once
