# PR-2 -- Gmail Send Existing Draft Controlled Tool

**Sprint:** DAENA-SPRINT-15-GOOGLE-LIVE-AND-FIRST-SEND-UNLOCK
**PR:** 2 of 6
**Date:** 2026-05-06

## Goal

Land the FIRST controlled external send. Daena moves from "draft
only" to "send a specific draft after a second approval, only if
the draft's From: matches the approving owner_email."

## What ships

`backend/app/services/controlled_execution_design.py`:

`WriteToolId` Literal grows from 3 to 4 entries. `WRITE_TOOLS`
adds `gmail.send_existing_draft`.

```python
WRITE_TOOLS: Final[frozenset[str]] = frozenset({
    "gmail.create_draft",
    "gmail.send_existing_draft",                            # NEW
    "calendar.create_tentative_event_without_invites",
    "local.file_change_proposal",
})
```

The Sprint-14 contract test `test_write_tools_is_sprint14_set` was
renamed `test_write_tools_is_sprint15_set` and updated -- the
deliberate operator-visible signal that Phase 3 is widening.

`test_no_send_tool_in_allowlist` was REWRITTEN as
`test_no_broad_send_or_submit_or_apply_in_allowlist`. The new rule
is sharper:

* No tool may END with `.send` / `.submit` / `.post` / `.apply` /
  `.pay` (those are the broad verbs).
* No tool may contain `.send_email` (would be a generic-recipient
  mailer).
* Any tool whose name CONTAINS `.send` must be on the explicit
  narrow allowlist `{"gmail.send_existing_draft"}`. Anything else
  fails the test.

This is the load-bearing pin. A future PR adding `gmail.send_email`
or `linkedin.post` would fail this test loudly, forcing the operator
to update it on purpose.

`backend/app/services/integrations/gmail_client.py`:

Two new methods:

* `get_draft(draft_id)` -- fetches Gmail draft metadata
  (`format=metadata`). Used by the handler to assert the From:
  header matches `owner_email` and to capture the To/Subject for
  the audit row.
* `send_existing_draft(draft_id)` -- POSTs to Gmail's
  `/drafts/send` endpoint with body `{"id": draft_id}`. Gmail
  resolves draft contents server-side; nothing flows from Daena
  except the id and the bearer token.

The existing broad `send_email(to, subject, body, ...)` method is
**unchanged** but it is NOT registered as a controlled-execution
handler and never will be (the Sprint-14 contract test forbids it).

`backend/app/services/controlled_execution_handlers/gmail_send_existing_draft.py` (new):

The handler. Six refusal codes in load-bearing order:

```
owner_email_required             - request omitted owner_email
payload_field_missing:draft_id   - payload omitted draft_id
oauth_not_connected:google       - no ConnectorInstance + access_token
draft_not_found                  - Gmail 404 / fetch raised
draft_owner_email_mismatch       - draft's From: != owner_email
(success path)                   - send fires, safe result returned
```

The success result carries `message_id`, `status="sent"`, `tool_id`,
`owner_email`, AND `audit_to` + `audit_subject` extracted from the
fetched draft headers (so the audit row records what was actually
sent without needing a second Gmail read after delivery). The
result is paranoidly walked to assert no `access_token` /
`refresh_token` / draft body leaks.

The handler is registered via side-effect import in
`controlled_execution_handlers/__init__.py`.

## Locked invariants

| Invariant | Where |
|---|---|
| Send payload bound to `{draft_id, owner_email}` only | handler reads only `payload["draft_id"]` |
| No arbitrary to / subject / body accepted | handler ignores any other payload fields |
| Hash format unchanged from Sprint-14 | `compute_payload_hash(payload)` already in dispatch |
| OAuth refusal BEFORE any Google HTTP call | `_load_gmail_credentials` runs first |
| Draft owner verified BEFORE send | `get_draft` -> From: assertion -> `send_existing_draft` |
| Generic send_email tool absent from allowlist | `test_no_broad_send_or_submit_or_apply_in_allowlist` |
| No bulk: send_existing_draft accepts ONE draft_id | function signature |
| No reply-chain: get_draft / send_existing_draft don't accept thread context | API surface |
| No attachments: send_existing_draft accepts only id | function signature |
| Sprint-14 contract test renamed deliberately | `test_write_tools_is_sprint15_set` |

## Tests

```
backend/tests/test_gmail_send_existing_draft_handler.py     14 tests
backend/tests/test_controlled_execution_design_lock.py       7 tests
backend/tests/test_gmail_create_draft_handler.py             7 tests (regression)
```

Combined: 28 / 28 pass.

Test classes:
- `TestRegistered` (2): handler registered after package import,
  WRITE_TOOLS contains the new tool_id
- `TestOwnerEmailRequired` (1)
- `TestPayloadValidation` (5 parametrized): missing / empty /
  whitespace / None / wrong-type draft_id
- `TestOAuthNotConnected` (1): refused before any HTTP call
- `TestDraftNotFound` (2): 404 + arbitrary exception
- `TestDraftOwnerEmailMismatch` (2): other-account, empty From:
- `TestSuccessPath` (1): full happy path with paranoid no-secret
  walk + audit_to / audit_subject extraction + verifies
  send_email was NEVER called

## Hard rules audit

| Rule | Status |
|---|---|
| No deploy | applied |
| No force push | applied |
| No secrets read / printed / committed | applied -- handler scrubs result |
| No generic send_email | enforced -- broad-verb test fails on `.send_email` |
| No submit / apply / post / pay | enforced -- same test |
| No LinkedIn messages | applied -- not in WRITE_TOOLS |
| No external browser automation | applied |
| No unauthorized scan | applied |
| No attachments | enforced -- send_existing_draft signature |
| No bulk sending | enforced -- handler accepts one draft_id |
| No send without approved Gmail draft row | enforced -- gate 4 in dispatch |
| No send if draft payload hash changed | enforced -- gate 3 in dispatch |
| No send if owner_email mismatch | enforced -- handler refuses `draft_owner_email_mismatch` |
| No send if Asset Shield fails | enforced -- design contract gate 2 |
| No send if approval / consent missing or stale | enforced -- gate 4 (approval), design contract (consent_grant_id) |
| No trust auto-escalation | unchanged -- trust_ladder is record-only |

## Files

```
modified:   backend/app/services/controlled_execution_design.py
modified:   backend/app/services/integrations/gmail_client.py
new:        backend/app/services/controlled_execution_handlers/gmail_send_existing_draft.py
modified:   backend/app/services/controlled_execution_handlers/__init__.py
modified:   backend/tests/test_controlled_execution_design_lock.py
new:        backend/tests/test_gmail_send_existing_draft_handler.py
new:        docs/Ultraview/PR_GMAIL_SEND_EXISTING_DRAFT_CONTROLLED_TOOL_REPORT.md
```

## Next: PR-3 -- Second Approval Wall for Send
