"""Inter-department messaging service.

Session C. Three core operations:

* ``send()`` -- Marketing asks Legal "review these claims"
* ``list_inbox()`` -- Legal's agent (or the UI) fetches pending messages
* ``answer()`` -- Legal writes the response; sender can consume it

Plus housekeeping:

* ``acknowledge()`` -- auto-called on first list_inbox fetch so the
  sender sees status=ACKNOWLEDGED ("seen but not answered")
* ``expire_overdue()`` -- background sweeper flips SENT messages past
  their ``expires_at`` to EXPIRED. Called by the heartbeat daemon.
* ``wait_for_answer()`` -- helper for DepartmentAgent.ask_department;
  polls for an answer with a timeout, cancellation-safe.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.department_message import (
    MESSAGE_STATUS_VALUES,
    DepartmentMessage,
)

logger = get_logger(__name__)

# Default message TTL when the caller does not specify one. 1 hour is
# long enough to survive async queueing but short enough that an
# unanswered message does not accumulate forever.
DEFAULT_TTL_SECONDS = 3600


class DepartmentMessageService:
    """CRUD + polling helpers for inter-department messages."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Send ────────────────────────────────────────────────────

    async def send(
        self,
        *,
        tenant_id: UUID,
        from_department: str,
        to_department: str,
        subject: str,
        body: str,
        context_ref: str | None = None,
        ttl_seconds: int | None = DEFAULT_TTL_SECONDS,
    ) -> DepartmentMessage:
        """Marketing -> Legal etc. Returns the persisted message so the
        sender can poll ``wait_for_answer`` on its id."""
        if from_department == to_department:
            raise ValueError(
                "from_department and to_department must differ "
                "(use a loop internal to the department instead)",
            )
        expires_at: datetime | None = None
        if ttl_seconds is not None and ttl_seconds > 0:
            expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)

        msg = DepartmentMessage(
            tenant_id=tenant_id,
            from_department=from_department,
            to_department=to_department,
            subject=subject[:200],
            body=body[:4000],
            context_ref=context_ref,
            status="SENT",
            expires_at=expires_at,
        )
        self._db.add(msg)
        await self._db.flush()
        logger.info(
            "dept_message.sent",
            id=str(msg.id),
            from_dept=from_department,
            to_dept=to_department,
            subject=subject[:80],
        )
        return msg

    # ── Inbox / outbox listing ─────────────────────────────────

    async def list_inbox(
        self,
        *,
        tenant_id: UUID,
        department: str,
        include_closed: bool = False,
        auto_acknowledge: bool = True,
    ) -> list[DepartmentMessage]:
        """Return messages addressed TO this department.

        ``auto_acknowledge=True`` flips every SENT message the caller
        sees into ACKNOWLEDGED so the sender knows it was seen. This
        matches "mark as read" semantics in a standard inbox.
        """
        conditions = [
            DepartmentMessage.tenant_id == tenant_id,
            DepartmentMessage.to_department == department,
        ]
        if not include_closed:
            conditions.append(DepartmentMessage.status.in_(("SENT", "ACKNOWLEDGED")))
        stmt = select(DepartmentMessage).where(*conditions).order_by(
            DepartmentMessage.created_at.asc(),
        )
        result = await self._db.execute(stmt)
        messages = list(result.scalars().all())

        if auto_acknowledge:
            now = datetime.now(UTC)
            dirty = False
            for m in messages:
                if m.status == "SENT":
                    m.status = "ACKNOWLEDGED"
                    m.acknowledged_at = now
                    dirty = True
            if dirty:
                await self._db.flush()

        return messages

    async def list_outbox(
        self,
        *,
        tenant_id: UUID,
        department: str,
        include_closed: bool = False,
    ) -> list[DepartmentMessage]:
        """Return messages THIS department sent. Useful for the sender's
        "did Legal answer my copy-review request yet?" poll."""
        conditions = [
            DepartmentMessage.tenant_id == tenant_id,
            DepartmentMessage.from_department == department,
        ]
        if not include_closed:
            conditions.append(DepartmentMessage.status.in_(("SENT", "ACKNOWLEDGED")))
        stmt = select(DepartmentMessage).where(*conditions).order_by(
            DepartmentMessage.created_at.desc(),
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    # ── Answer ─────────────────────────────────────────────────

    async def answer(
        self,
        *,
        message_id: UUID,
        body: str,
    ) -> DepartmentMessage:
        """Reviewer department writes a response. Idempotent in the
        sense that answering an already-ANSWERED message is a no-op
        error (reviewer cannot retcon)."""
        stmt = select(DepartmentMessage).where(DepartmentMessage.id == message_id)
        result = await self._db.execute(stmt)
        msg = result.scalar_one_or_none()
        if msg is None:
            raise ValueError(f"Message {message_id} not found")
        if msg.status in ("ANSWERED", "EXPIRED"):
            raise ValueError(
                f"Message {message_id} is already in terminal state {msg.status!r}; "
                "cannot overwrite answer",
            )
        msg.answer = body[:4000]
        msg.status = "ANSWERED"
        msg.answered_at = datetime.now(UTC)
        # If the reviewer answered without explicitly acknowledging,
        # backfill acknowledged_at so analytics reflect reality.
        if msg.acknowledged_at is None:
            msg.acknowledged_at = msg.answered_at
        await self._db.flush()
        logger.info(
            "dept_message.answered",
            id=str(msg.id),
            from_dept=msg.from_department,
            to_dept=msg.to_department,
        )
        return msg

    # ── Housekeeping ───────────────────────────────────────────

    async def expire_overdue(
        self,
        *,
        tenant_id: UUID | None = None,
    ) -> int:
        """Flip SENT + ACKNOWLEDGED messages past ``expires_at`` to
        EXPIRED. Returns count affected. Safe to call repeatedly."""
        now = datetime.now(UTC)
        conditions = [
            DepartmentMessage.status.in_(("SENT", "ACKNOWLEDGED")),
            DepartmentMessage.expires_at.is_not(None),
            DepartmentMessage.expires_at < now,
        ]
        if tenant_id is not None:
            conditions.append(DepartmentMessage.tenant_id == tenant_id)
        stmt = select(DepartmentMessage).where(*conditions)
        result = await self._db.execute(stmt)
        overdue = list(result.scalars().all())
        for m in overdue:
            m.status = "EXPIRED"
        if overdue:
            await self._db.flush()
        logger.info("dept_message.expired_count", count=len(overdue))
        return len(overdue)

    # ── Polling helper for DepartmentAgent.ask_department ──────

    async def wait_for_answer(
        self,
        *,
        message_id: UUID,
        timeout_seconds: int = 60,
        poll_interval_seconds: float = 1.0,
    ) -> DepartmentMessage | None:
        """Block until the message is ANSWERED / EXPIRED or timeout.

        Returns the final state of the message, or ``None`` on timeout.
        Cancellation-safe: if the caller is cancelled, the pending DB
        query is cancelled too.
        """
        deadline = datetime.now(UTC) + timedelta(seconds=timeout_seconds)
        while datetime.now(UTC) < deadline:
            stmt = select(DepartmentMessage).where(
                DepartmentMessage.id == message_id,
            )
            result = await self._db.execute(stmt)
            msg = result.scalar_one_or_none()
            if msg is None:
                return None
            if msg.status in ("ANSWERED", "EXPIRED"):
                return msg
            await asyncio.sleep(poll_interval_seconds)
        return None
