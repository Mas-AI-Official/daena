"""gmail.send_existing_draft handler -- Sprint-15 PR-2 (2026-05-06).

The FIRST controlled external send. Sends an existing Gmail draft
by id. The handler runs only after the dispatcher's six gates have
passed AND a SECOND approval has been raised separately for the
send action (the Sprint-14 create-draft approval does NOT authorize
send -- they have distinct ``action_type`` values, so the
dispatcher's gate 4 enforces this naturally).

Why this is the safest possible first send:

  * Payload is bound to ``{draft_id, owner_email}`` ONLY. There is
    no arbitrary ``to``, ``subject``, ``body``, ``cc``, ``bcc``, or
    attachment. The draft contents live with Gmail; Daena does not
    re-supply them at send time.
  * The handler fetches the draft from Gmail BEFORE sending so the
    audit row records what is actually about to leave Gmail. If
    the draft's ``From`` header does not match ``owner_email``, the
    send refuses with ``draft_owner_email_mismatch``.
  * The handler refuses ``oauth_not_connected:google`` BEFORE any
    HTTP call to Gmail.
  * Generic ``gmail.send_email`` is NOT in WRITE_TOOLS and never
    will be. The contract test
    ``test_no_broad_send_or_submit_or_apply_in_allowlist`` pins it.

Refusal codes (in addition to the dispatcher's gates):

::

    oauth_not_connected:google
        ConnectorInstance row for owner_email is missing or has
        no access_token. Operator must (re)connect via
        /settings/connections.

    payload_field_missing:draft_id
        Send payload lacks ``draft_id``.

    owner_email_required
        Send payload lacks ``owner_email``.

    draft_not_found
        Gmail returned 404 for the draft_id, or the draft fetch
        raised. The most common cause: the draft was deleted from
        Gmail's drafts folder between approval and send.

    draft_owner_email_mismatch
        The fetched draft's ``From`` header is a different account
        than the request's ``owner_email``. This is the lock that
        prevents draft-substitution from another account on the
        same connector.
"""

from __future__ import annotations

from typing import Any

import httpx
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

_TOOL_ID = "gmail.send_existing_draft"


async def _load_gmail_credentials(
    ctx: HandlerContext, *, owner_email: str,
) -> dict[str, str]:
    """Identical lookup pattern to gmail.create_draft. Refuses with
    ``oauth_not_connected:google`` BEFORE any HTTP call."""
    db = ctx.db

    conn_row = (await db.execute(
        select(Connector).where(Connector.name == "Gmail"),
    )).scalar_one_or_none()
    if conn_row is None:
        raise ControlledExecutionRefused(
            "oauth_not_connected:google",
            "Gmail connector not in catalog; connect via "
            "/settings/connections first.",
        )

    target_email = owner_email.strip().lower()
    rows = (await db.execute(
        select(ConnectorInstance)
        .where(ConnectorInstance.tenant_id == ctx.tenant_id)
        .where(ConnectorInstance.user_id == ctx.user_id)
        .where(ConnectorInstance.connector_id == conn_row.id),
    )).scalars().all()
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
            f"{owner_email!r}. Re-run OAuth via /settings/connections.",
        )
    creds = matched.credentials or {}
    if not creds.get("access_token"):
        raise ControlledExecutionRefused(
            "oauth_not_connected:google",
            f"Gmail credentials missing access_token for "
            f"{owner_email!r}. Re-run the OAuth flow.",
        )
    return creds


def _extract_from_header(draft_meta: dict[str, Any]) -> str:
    """Pull the ``From:`` header value from a Gmail draft metadata
    payload. Empty string when absent."""
    headers = (
        draft_meta.get("message", {})
        .get("payload", {})
        .get("headers", [])
    )
    for h in headers:
        if (h.get("name") or "").lower() == "from":
            return h.get("value") or ""
    return ""


async def handle_gmail_send_existing_draft(
    ctx: HandlerContext,
) -> dict[str, Any]:
    """Send an existing Gmail draft.

    Six refusal codes in order:
      1. owner_email_required
      2. payload_field_missing:draft_id
      3. oauth_not_connected:google
      4. draft_not_found
      5. draft_owner_email_mismatch
      6. (handler success path)
    """
    if not ctx.request.owner_email:
        raise ControlledExecutionRefused(
            "owner_email_required",
            "gmail.send_existing_draft requires owner_email so the "
            "audit chain pins which Google account performed the "
            "send.",
        )

    draft_id = ctx.payload.get("draft_id")
    if not isinstance(draft_id, str) or not draft_id.strip():
        raise ControlledExecutionRefused(
            "payload_field_missing:draft_id",
            "gmail.send_existing_draft payload must carry a "
            "non-empty draft_id (the draft created by an earlier "
            "approved gmail.create_draft).",
        )

    creds = await _load_gmail_credentials(
        ctx, owner_email=ctx.request.owner_email,
    )
    client = _build_client(creds)

    # Fetch draft metadata before send. This serves three purposes:
    #   1. Verifies the draft still exists (refuse draft_not_found).
    #   2. Lets the handler assert From: matches owner_email
    #      (refuse draft_owner_email_mismatch).
    #   3. Captures recipient + subject so the audit row records
    #      what was sent without re-running the read after delivery.
    try:
        draft_meta = await client.get_draft(draft_id)
    except httpx.HTTPStatusError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            raise ControlledExecutionRefused(
                "draft_not_found",
                f"Gmail returned 404 for draft_id={draft_id!r}. "
                f"The draft may have been deleted between approval "
                f"and send.",
            ) from exc
        raise ControlledExecutionRefused(
            "draft_not_found",
            f"Gmail draft fetch failed for draft_id={draft_id!r}: "
            f"{exc.response.status_code if exc.response else 'no response'}.",
        ) from exc
    except Exception as exc:
        raise ControlledExecutionRefused(
            "draft_not_found",
            f"Gmail draft fetch raised for draft_id={draft_id!r}: "
            f"{type(exc).__name__}.",
        ) from exc

    from_value = _extract_from_header(draft_meta).lower()
    target = ctx.request.owner_email.strip().lower()
    # Gmail's From: header is typically "Display Name <email@host>"
    # so we substring-check rather than exact-match. Empty
    # from_value also fails the assertion.
    if not from_value or target not in from_value:
        raise ControlledExecutionRefused(
            "draft_owner_email_mismatch",
            f"Draft's From: header does not contain owner_email "
            f"{ctx.request.owner_email!r}. Refusing send to prevent "
            f"draft-substitution from another connected account.",
        )

    result = await client.send_existing_draft(draft_id)

    # Build a SAFE result. Never include the access_token, never
    # include the draft body. Subject + recipient are extracted
    # from the fetched draft headers for the audit row only.
    headers = (
        draft_meta.get("message", {})
        .get("payload", {})
        .get("headers", [])
    )
    header_map = {
        (h.get("name") or "").lower(): (h.get("value") or "")
        for h in headers
    }
    safe = {
        "draft_id": draft_id,
        "message_id": result.get("message_id"),
        "thread_id": result.get("thread_id"),
        "status": result.get("status") or "sent",
        "tool_id": _TOOL_ID,
        "owner_email": ctx.request.owner_email,
        # Audit-only metadata; truncated by the audit viewer (PR-4).
        "audit_to": header_map.get("to", ""),
        "audit_subject": header_map.get("subject", ""),
        "rollback_or_undo_instruction": (
            ctx.request.rollback_or_undo_instruction
            or "Email cannot be unsent after delivery. Send a "
               "follow-up correction or recall via Google Workspace "
               "admin if available."
        ),
    }
    logger.info(
        "controlled_execution.gmail.draft_sent",
        owner_email=ctx.request.owner_email,
        draft_id=draft_id,
        message_id=safe["message_id"],
        approval_id=ctx.request.approval_id,
    )
    return safe


def _build_client(credentials: dict[str, str]) -> GmailClient:
    """Indirection so tests can monkeypatch the client."""
    return GmailClient(credentials)


# Side-effect register on import.
register_tool_handler(_TOOL_ID, handle_gmail_send_existing_draft)
