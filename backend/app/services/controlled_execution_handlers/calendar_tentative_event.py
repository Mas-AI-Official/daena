"""calendar.create_tentative_event_without_invites handler -- Sprint-14 PR-3.

Creates a Google Calendar event WITHOUT attendees so no invite
emails fire from Google. The event lives on the operator's primary
calendar as a personal hold; the operator can manually invite
participants later via the Calendar UI.

Refusal codes:

::

    oauth_not_connected:google
        ConnectorInstance row missing for owner_email.

    payload_field_missing:<field>
        summary / start / end are required.

    owner_email_required
        audit chain pins which Google account.

    attendees_not_allowed_in_tentative_tool
        Operator passed an attendees list. The whole point of this
        tool is to NOT send invites; pass through send variant later
        sprint, not by smuggling attendees into the tentative tool.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock  # type: ignore  # only for type hint clarity

from sqlalchemy import select

from app.core.logging import get_logger
from app.models.connections import Connector, ConnectorInstance
from app.services.controlled_execution_dispatch import (
    ControlledExecutionRefused,
    HandlerContext,
    register_tool_handler,
)
from app.services.integrations.calendar_client import CalendarClient

logger = get_logger(__name__)


_TOOL_ID = "calendar.create_tentative_event_without_invites"
_REQUIRED_PAYLOAD_FIELDS: tuple[str, ...] = ("summary", "start", "end")


async def _load_calendar_credentials(
    ctx: HandlerContext, *, owner_email: str,
) -> dict[str, str]:
    """Lookup Google Calendar ConnectorInstance for the operator.

    Same pattern as gmail handler. Refuses with
    ``oauth_not_connected:google`` if missing.
    """
    db = ctx.db

    conn_row = (await db.execute(
        select(Connector).where(Connector.name == "Google Calendar"),
    )).scalar_one_or_none()
    if conn_row is None:
        raise ControlledExecutionRefused(
            "oauth_not_connected:google",
            "Google Calendar connector not in catalog; "
            "Connect Google account via /settings/connections.",
        )

    target_email = owner_email.strip().lower()
    stmt = (
        select(ConnectorInstance)
        .where(ConnectorInstance.tenant_id == ctx.tenant_id)
        .where(ConnectorInstance.user_id == ctx.user_id)
        .where(ConnectorInstance.connector_id == conn_row.id)
    )
    rows = (await db.execute(stmt)).scalars().all()
    matched = next(
        (
            i for i in rows
            if (i.owner_email or "").strip().lower() == target_email
        ),
        None,
    )
    if matched is None:
        raise ControlledExecutionRefused(
            "oauth_not_connected:google",
            f"No connected Google Calendar instance for owner_email "
            f"{owner_email!r}.",
        )

    creds = matched.credentials or {}
    if not creds.get("access_token"):
        raise ControlledExecutionRefused(
            "oauth_not_connected:google",
            f"Calendar credentials missing access_token for "
            f"owner_email {owner_email!r}.",
        )
    return creds


async def handle_calendar_tentative_event(ctx: HandlerContext) -> dict[str, Any]:
    """Create a calendar event without attendees -> no invites fire.

    The handler refuses any payload that carries an attendees list;
    that smuggling vector is what the tool name forbids.
    """

    if not ctx.request.owner_email:
        raise ControlledExecutionRefused(
            "owner_email_required",
            f"{_TOOL_ID} requires owner_email so the audit chain "
            "pins which Google account hosts the event.",
        )

    for field in _REQUIRED_PAYLOAD_FIELDS:
        value = ctx.payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ControlledExecutionRefused(
                f"payload_field_missing:{field}",
                f"{_TOOL_ID} payload must carry non-empty {field!r}.",
            )

    # The tool name says "without_invites". An attendees list in
    # the payload is the smuggling vector that turns this into
    # an invite-send. Refuse explicitly.
    attendees = ctx.payload.get("attendees")
    if attendees:
        raise ControlledExecutionRefused(
            "attendees_not_allowed_in_tentative_tool",
            "calendar.create_tentative_event_without_invites refuses "
            "any non-empty attendees list. Use a future calendar.send_invite "
            "tool (Sprint-15+) for that flow.",
        )

    creds = await _load_calendar_credentials(
        ctx, owner_email=ctx.request.owner_email,
    )
    client = _build_client(creds)
    result = await client.create_event(
        summary=ctx.payload["summary"],
        start=ctx.payload["start"],
        end=ctx.payload["end"],
        description=str(ctx.payload.get("description", "")),
        location=str(ctx.payload.get("location", "")),
        attendees=None,                     # LOCKED -- never invites
        calendar_id="primary",
        timezone_str=str(
            ctx.payload.get("timezone", "America/Toronto"),
        ),
    )

    safe = {
        "event_id": result.get("id"),
        "summary": result.get("summary"),
        "start": result.get("start"),
        "end": result.get("end"),
        "html_link": result.get("html_link"),
        "status": "tentative_no_invites",
        "tool_id": _TOOL_ID,
        "owner_email": ctx.request.owner_email,
        "rollback_or_undo_instruction": (
            ctx.request.rollback_or_undo_instruction
            or "Open the event on calendar.google.com and delete it, "
               "or use a future controlled-execution calendar.delete_event tool."
        ),
    }
    logger.info(
        "controlled_execution.calendar.tentative_event_created",
        owner_email=ctx.request.owner_email,
        event_id=safe["event_id"],
        approval_id=ctx.request.approval_id,
    )
    return safe


def _build_client(credentials: dict[str, str]) -> CalendarClient:
    """Indirection so tests can monkeypatch the client."""
    return CalendarClient(credentials)


# Side-effect register on import.
register_tool_handler(_TOOL_ID, handle_calendar_tentative_event)
