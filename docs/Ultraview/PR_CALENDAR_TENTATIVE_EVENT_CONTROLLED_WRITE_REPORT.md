# PR-3 -- Calendar Tentative Event Without Invites

**Sprint:** DAENA-PHASE3-CONTROLLED-WRITES-SPRINT-14
**PR:** 3 of 7
**Date:** 2026-05-06

## Goal

Allow Daena to create a Google Calendar event WITHOUT sending any
invite. The event is a personal hold on the operator's primary
calendar; participants are invited later by the operator manually.

## What ships

`backend/app/services/controlled_execution_handlers/calendar_tentative_event.py`
(new). Side-effect-registers
`calendar.create_tentative_event_without_invites -> handle_calendar_tentative_event`.

### The locked invariant

`CalendarClient.create_event` is called with `attendees=None`
ALWAYS. The contract test pins this:

```python
fake_client.create_event.await_args.kwargs["attendees"] is None
```

That's the wall. No invite emails fire from Google because no
attendees are passed.

### Refusal codes

| Code | Trigger |
|---|---|
| `owner_email_required` | request.owner_email missing |
| `payload_field_missing:summary/start/end` | required field absent |
| `attendees_not_allowed_in_tentative_tool` | payload contains attendees list -- the smuggling vector this tool was named to block |
| `oauth_not_connected:google` | no Google Calendar ConnectorInstance |

### Result shape

```ts
{
  event_id: string,
  summary: string,
  start: string,
  end: string,
  html_link: string,
  status: "tentative_no_invites",
  tool_id: "calendar.create_tentative_event_without_invites",
  owner_email: string,
  rollback_or_undo_instruction: string
}
```

## Tests

`backend/tests/test_calendar_tentative_event_handler.py` -- 8 tests:

```
TestRegistered::test_handler_in_registry_after_import
TestOwnerEmailRequired::test_missing_owner_email_refused
TestPayloadValidation::test_required_field_missing[summary]
TestPayloadValidation::test_required_field_missing[start]
TestPayloadValidation::test_required_field_missing[end]
TestAttendeesRefused::test_attendees_in_payload_refused
TestOAuthNotConnected::test_no_calendar_instance_refused
TestSuccessPath::test_create_event_called_without_attendees
```

Combined Sprint-14 fast subset: 32/32 pass.

## Hard rules audit

| Rule | Status |
|---|---|
| No invite emails fire | enforced -- attendees=None always; payload attendees refused |
| owner_email required | enforced + tested |
| Audit every run | dispatcher logger.info structured rows |
| Rollback instruction | always populated |
| OAuth refusal explicit | enforced + tested before any HTTP call |

## Files

```
new:        backend/app/services/controlled_execution_handlers/calendar_tentative_event.py  (170 lines)
modified:   backend/app/services/controlled_execution_handlers/__init__.py                  (+1 line: import)
new:        backend/tests/test_calendar_tentative_event_handler.py                          (210 lines, 8 tests)
new:        docs/Ultraview/PR_CALENDAR_TENTATIVE_EVENT_CONTROLLED_WRITE_REPORT.md
```

## Next: PR-4 -- File Change Proposal (Diff, Not Direct Write)
