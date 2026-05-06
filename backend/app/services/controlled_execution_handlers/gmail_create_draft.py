"""gmail.create_draft handler -- Sprint-14 PR-2 (2026-05-06).

The first concrete write tool. Creates a Gmail DRAFT only; never
sends, never replies, never attaches. The handler runs only after
the dispatcher's six gates have passed (see
``controlled_execution_dispatch``).

Refusal codes (in addition to the dispatcher's gates):

::

    oauth_not_connected:google
        ConnectorInstance row for the operator's owner_email is
        missing. The operator must complete the OAuth dance via
        /settings/connections before any Gmail write fires.

    payload_field_missing:<field>
        The payload dict lacks one of the required Gmail fields
        (to / subject / body).

    owner_email_required
        The request did not include owner_email; for Gmail this
        is a hard requirement (the access_token belongs to one
        Google account, and the audit chain pins it).

The handler returns a structured result with the draft_id and
status. The Google access_token is NEVER included in the response.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from app.core.logging import get_logger
from app.models.connections import Connector, ConnectorInstance
from app.services.controlled_execution_dispatch import (
    ControlledExecutionRefused,
    HandlerContext,
    register_tool_handler,
)
from app.services.integrations.gmail_client import GmailClient

logger = get_logger(__name__)


_TOOL_ID = "gmail.create_draft"
_REQUIRED_PAYLOAD_FIELDS: tuple[str, ...] = ("to", "subject", "body")


async def _load_gmail_credentials(
    ctx: HandlerContext, *, owner_email: str,
) -> dict[str, str]:
    """Look up the operator's Gmail ConnectorInstance, scoped to
    tenant + user_id + owner_email.

    Refuses with ``oauth_not_connected:google`` if missing.
    """
    db = ctx.db

    # Find Connector row by canonical name.
    conn_row = (await db.execute(
        select(Connector).where(Connector.name == "Gmail"),
    )).scalar_one_or_none()
    if conn_row is None:
        # Catalog is out of sync; surface a clear refusal.
        raise ControlledExecutionRefused(
            "oauth_not_connected:google",
            "Gmail connector not found in catalog; "
            "Connect Google account first via /settings/connections.",
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
            f"No connected Gmail instance for owner_email "
            f"{owner_email!r}. Connect this account via "
            f"/settings/connections before retrying.",
        )

    creds = matched.credentials or {}
    if not creds.get("access_token"):
        raise ControlledExecutionRefused(
            "oauth_not_connected:google",
            f"Gmail credentials missing access_token for owner_email "
            f"{owner_email!r}. Re-run the OAuth flow.",
        )
    return creds


async def handle_gmail_create_draft(ctx: HandlerContext) -> dict[str, Any]:
    """Run the Gmail draft create. Tested separately by mocking
    the Gmail client; the handler itself does not retry, does not
    send, does not attach files.
    """

    # owner_email is REQUIRED for Gmail (one access_token <-> one
    # Google account; the audit chain must pin which account).
    if not ctx.request.owner_email:
        raise ControlledExecutionRefused(
            "owner_email_required",
            "gmail.create_draft requires owner_email in the dispatch "
            "request so the audit chain pins which Google account "
            "the draft was created in.",
        )

    # Validate payload fields.
    for field in _REQUIRED_PAYLOAD_FIELDS:
        value = ctx.payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ControlledExecutionRefused(
                f"payload_field_missing:{field}",
                f"gmail.create_draft payload must carry non-empty "
                f"{field!r} (to / subject / body are all required).",
            )

    creds = await _load_gmail_credentials(
        ctx, owner_email=ctx.request.owner_email,
    )

    client = _build_client(creds)
    result = await client.create_draft(
        to=ctx.payload["to"],
        subject=ctx.payload["subject"],
        body=ctx.payload["body"],
        html=bool(ctx.payload.get("html", False)),
    )

    # Strip anything secret-shaped from the result before returning.
    # GmailClient.create_draft returns {draft_id, message_id, status}
    # which carries no token, but we are paranoid by contract.
    safe = {
        "draft_id": result.get("draft_id"),
        "message_id": result.get("message_id"),
        "status": result.get("status"),
        "tool_id": _TOOL_ID,
        "owner_email": ctx.request.owner_email,
        "rollback_or_undo_instruction": (
            ctx.request.rollback_or_undo_instruction
            or "Delete the draft from the Gmail Drafts folder, or via a "
               "future controlled-execution gmail.delete_draft tool."
        ),
    }
    logger.info(
        "controlled_execution.gmail.draft_created",
        owner_email=ctx.request.owner_email,
        draft_id=safe["draft_id"],
        approval_id=ctx.request.approval_id,
    )
    return safe


def _build_client(credentials: dict[str, str]) -> GmailClient:
    """Indirection so tests can monkeypatch the client."""
    return GmailClient(credentials)


# Side-effect register on import. The handlers package's __init__
# imports this module so the dispatcher sees the handler at startup.
register_tool_handler(_TOOL_ID, handle_gmail_create_draft)
