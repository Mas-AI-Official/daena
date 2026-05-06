# PR-3 -- Outreach Draft Factory

**Sprint:** DAENA-SPRINT-19-BUSINESS-EXECUTION-LOOPS
**PR:** 3 of 8
**Date:** 2026-05-06

## Goal

Turn `Opportunity` rows into local `BizOutreachDraft` rows. NO
external action; recipient safety wall enforced; payload hash
computed; templates deterministic Python (no LLM in v1).

## What ships

`backend/app/services/outreach/recipient_safety.py` (new):

* `RecipientSafetyResult(safe, recipient, reason)` -- structured
  result, NEVER raises.
* `check_recipient_safety` enforces 5 walls in order:
    1. non-empty
    2. no control chars (NUL / CR / LF / DEL etc)
    3. no commas / semicolons (single recipient only)
    4. matches conservative RFC-5322-ish regex
    5. not in suppression list (`backend/.recipient_suppression.json`)
    6. not in tenant's own `users` table
* Stable refusal codes: `empty_recipient` /
  `control_chars` / `multiple_recipients` / `invalid_email` /
  `in_suppression_list` / `recipient_is_internal_user`.

`backend/app/services/outreach/draft_factory.py` (new):

* `_OPPORTUNITY_TO_DRAFT_KIND` -- locked Sprint-19 mapping.
* `compute_payload_hash` -- canonical sha256 over JSON of
  `{to, subject, body}`. Stable across the bridge to Gmail.
* `_render_subject` / `_render_body` -- deterministic templates
  per draft kind. No LLM, no API calls, pure f-strings.
* `create_outreach_draft_for_opportunity` -- the entry point:
    - maps opportunity type -> draft kind (refuses unknown)
    - runs recipient safety; failure -> draft persisted with
      `status='blocked_recipient'` + `blocked_reason`
    - success -> draft persisted with `status='drafted'`,
      opportunity advances to `status='drafted'`
    - NEVER raises

`backend/app/services/outreach/__init__.py` (new): re-exports.

## Mythos design choices

**Blocked recipient still gets persisted.** Operator gets a row
with `status='blocked_recipient'` and a stable `blocked_reason`.
This is honest visibility -- "Daena tried this, here's what was
attempted, here's why it didn't proceed." Compare to silent drop
which leaves the operator wondering what happened.

**Templates are pure Python f-strings.** No LLM, no remote call.
A draft is reproducible: same opportunity + same recipient =
byte-identical body. Audit-friendly. Future sprints can layer
LLM-suggested copy ON TOP of the template, but the factory output
must always be auditable + diffable.

**Payload hash matches dispatcher's canonical format.** Same
sort_keys + separators as `compute_payload_hash` in
`controlled_execution_dispatch`. So when PR-4 dispatches the
Gmail-create-draft tool, the payload_hash produced here lines up
with the dispatcher's verification.

**Single-recipient enforcement at the safety wall, not at the
dispatch.** The brief locks "one recipient only in v1." Wall
refuses any string with comma or semicolon. This catches both
"a@b.com, c@d.com" and "alice <a@b.com>, bob <c@d.com>" patterns.

**Internal-user check uses tenant_id.** Cross-tenant emails are
fine (a tenant emailing another tenant's user is just normal
B2B contact). Same-tenant email is the wall. Prevents
"draft to yourself" footgun.

## Locked invariants

| Invariant | Where |
|---|---|
| Empty / control / multi / invalid recipients refused | `TestRecipientSafety::test_invalid_recipients_refused` (parametric over 8 cases) |
| Valid recipient passes | `test_valid_recipient_passes` |
| Suppression list blocks | `test_suppression_blocks` |
| Internal user blocked | `test_internal_user_blocked` |
| Grant -> grant_inquiry_email | `TestFactory::test_grant_maps_to_grant_inquiry` |
| Blocked recipient still persists draft | `test_blocked_recipient_persists_with_status` |
| Unknown opportunity type rejected | `test_unknown_type_rejected` |
| Success advances opportunity status | `test_successful_draft_marks_opportunity` |
| Module surface bans send/submit/post/pay | `TestNoForbiddenSurface` |

## Hard rules audit

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied |
| No generic send_email | applied -- factory does NOT send |
| No bulk sending | applied -- single-recipient wall |
| No LinkedIn automation | applied -- email only |
| No form/application submit | applied |
| No social post | applied |
| No payment | applied |
| No browser automation | applied |
| No contact spam | applied -- top-N cap upstream + recipient safety |
| Recipient safety enforced before persistence | enforced + tested |
| Payload hash computed | enforced + tested |

## Tests

```
backend/tests/test_outreach_draft_factory.py    16 tests
```

16/16 pass.

## Files

```
new:        backend/app/services/outreach/__init__.py
new:        backend/app/services/outreach/recipient_safety.py
new:        backend/app/services/outreach/draft_factory.py
new:        backend/tests/test_outreach_draft_factory.py
new:        docs/Ultraview/PR_OUTREACH_DRAFT_FACTORY_REPORT.md
```

## Next: PR-4 -- Controlled Gmail Draft Bridge
