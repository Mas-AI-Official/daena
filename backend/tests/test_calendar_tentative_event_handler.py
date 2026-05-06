"""Sprint-14 PR-3 -- calendar tentative event handler contract.

Pins:
  1. Handler registered after package import.
  2. owner_email REQUIRED.
  3. Required payload fields: summary, start, end.
  4. attendees in payload is REFUSED (the smuggling vector).
  5. OAuth-not-connected refuses BEFORE any Calendar API call.
  6. Success path returns html_link + event_id + status="tentative_no_invites".
  7. CalendarClient.create_event is called with attendees=None
     (the lock that prevents invite emails).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


pytestmark = pytest.mark.asyncio


def _make_request(**overrides):
    from app.services.controlled_execution_design import ControlledExecutionRequest

    base = dict(
        approval_id="00000000-0000-0000-0000-000000000000",
        consent_grant_id="grant-x",
        payload_hash="0" * 64,
        tool_id="calendar.create_tentative_event_without_invites",
        owner_email="founder@example.com",
        asset_shield_pass=True,
        policy_allowlist_pass=True,
        audit_preflight_row_id="audit-pre",
        audit_result_row_id=None,
        rollback_or_undo_instruction=None,
    )
    base.update(overrides)
    return ControlledExecutionRequest(**base)


def _make_ctx(*, request, payload):
    import uuid

    from app.services.controlled_execution_dispatch import HandlerContext

    return HandlerContext(
        request=request,
        approval=MagicMock(),
        payload=payload,
        tenant_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        db=MagicMock(),
    )


class TestRegistered:
    async def test_handler_in_registry_after_import(self):
        import app.services.controlled_execution_handlers  # noqa: F401
        from app.services.controlled_execution_dispatch import registered_tool_ids

        assert (
            "calendar.create_tentative_event_without_invites"
            in registered_tool_ids()
        )


class TestOwnerEmailRequired:
    async def test_missing_owner_email_refused(self):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers.calendar_tentative_event import (
            handle_calendar_tentative_event,
        )

        req = _make_request(owner_email=None)
        ctx = _make_ctx(
            request=req,
            payload={
                "summary": "Team sync",
                "start": "2026-05-07T10:00:00",
                "end": "2026-05-07T10:30:00",
            },
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await handle_calendar_tentative_event(ctx)
        assert ei.value.code == "owner_email_required"


class TestPayloadValidation:
    @pytest.mark.parametrize("missing", ["summary", "start", "end"])
    async def test_required_field_missing(self, missing):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers.calendar_tentative_event import (
            handle_calendar_tentative_event,
        )

        payload = {
            "summary": "Team sync",
            "start": "2026-05-07T10:00:00",
            "end": "2026-05-07T10:30:00",
        }
        del payload[missing]
        req = _make_request()
        ctx = _make_ctx(request=req, payload=payload)
        with pytest.raises(ControlledExecutionRefused) as ei:
            await handle_calendar_tentative_event(ctx)
        assert ei.value.code == f"payload_field_missing:{missing}"


class TestAttendeesRefused:
    async def test_attendees_in_payload_refused(self):
        """The smuggling vector this tool was created to block."""
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers.calendar_tentative_event import (
            handle_calendar_tentative_event,
        )

        req = _make_request()
        ctx = _make_ctx(
            request=req,
            payload={
                "summary": "Team sync",
                "start": "2026-05-07T10:00:00",
                "end": "2026-05-07T10:30:00",
                "attendees": ["dev@example.com"],
            },
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await handle_calendar_tentative_event(ctx)
        assert ei.value.code == "attendees_not_allowed_in_tentative_tool"


class TestOAuthNotConnected:
    async def test_no_calendar_instance_refused(self, monkeypatch):
        from app.services.controlled_execution_dispatch import (
            ControlledExecutionRefused,
        )
        from app.services.controlled_execution_handlers import calendar_tentative_event as mod

        async def _fake_load(ctx, *, owner_email):
            raise ControlledExecutionRefused(
                "oauth_not_connected:google",
                f"no instance for {owner_email}",
            )

        monkeypatch.setattr(mod, "_load_calendar_credentials", _fake_load)

        req = _make_request()
        ctx = _make_ctx(
            request=req,
            payload={
                "summary": "Team sync",
                "start": "2026-05-07T10:00:00",
                "end": "2026-05-07T10:30:00",
            },
        )
        with pytest.raises(ControlledExecutionRefused) as ei:
            await mod.handle_calendar_tentative_event(ctx)
        assert ei.value.code == "oauth_not_connected:google"


class TestSuccessPath:
    async def test_create_event_called_without_attendees(self, monkeypatch):
        """Pin the lock: the handler ALWAYS passes attendees=None
        to CalendarClient.create_event, regardless of payload."""
        from app.services.controlled_execution_handlers import calendar_tentative_event as mod

        async def _fake_load(ctx, *, owner_email):
            return {"access_token": "SECRET-NEVER-LEAK"}

        fake_client = MagicMock()
        fake_client.create_event = AsyncMock(return_value={
            "id": "ev-abc123",
            "summary": "Team sync",
            "start": "2026-05-07T10:00:00",
            "end": "2026-05-07T10:30:00",
            "html_link": "https://calendar.google.com/calendar/event?eid=abc",
            "status": "created",
        })

        monkeypatch.setattr(mod, "_load_calendar_credentials", _fake_load)
        monkeypatch.setattr(mod, "_build_client", lambda creds: fake_client)

        req = _make_request()
        ctx = _make_ctx(
            request=req,
            payload={
                "summary": "Team sync",
                "start": "2026-05-07T10:00:00",
                "end": "2026-05-07T10:30:00",
                "description": "internal review",
            },
        )
        result = await mod.handle_calendar_tentative_event(ctx)

        # The locked invariant: attendees=None passed to create_event.
        call = fake_client.create_event.await_args
        assert call.kwargs["attendees"] is None, (
            "tentative event handler MUST pass attendees=None to "
            "CalendarClient.create_event -- otherwise invite emails "
            "could fire."
        )

        # Result shape
        assert result["event_id"] == "ev-abc123"
        assert result["status"] == "tentative_no_invites"
        assert result["tool_id"] == "calendar.create_tentative_event_without_invites"
        assert result["html_link"]
        assert isinstance(result["rollback_or_undo_instruction"], str)
        assert len(result["rollback_or_undo_instruction"]) > 0

        # No-secret walk
        def _walk(o):
            if isinstance(o, dict):
                for k, v in o.items():
                    assert "access_token" not in str(k).lower()
                    assert "refresh_token" not in str(k).lower()
                    _walk(v)
            elif isinstance(o, list):
                for x in o:
                    _walk(x)
            elif isinstance(o, str):
                assert "SECRET-NEVER-LEAK" not in o

        _walk(result)
