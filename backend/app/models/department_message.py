"""Inter-department messaging -- explicit ASK/ANSWER between agents.

Session C (Piece 3) of the "Daena as a Living Company" plan.

Motivation
----------
Before this session, departments could only coordinate via:
1. Shared NBMF memory (broadcast, eventually consistent, no reply loop)
2. ``DepartmentBudget`` + ``ExpenseProposal`` (expense-specific only)

That left a gap: Marketing needs a SYNCHRONOUS-ish answer from Legal
before shipping copy. NBMF broadcast does not guarantee Legal reads
it in time; budget proposals do not cover copy review. This model is
the general-purpose ASK/ANSWER channel.

Status lifecycle
----------------
::

    SENT          -- message created, Legal's inbox shows it
    ACKNOWLEDGED  -- Legal's agent has seen it (auto-set on first poll)
    ANSWERED      -- Legal wrote a response; from_dept can consume it
    EXPIRED       -- timeout (default 1h) without an answer; sender
                     must decide to wait, escalate, or proceed

The caller's ``context_ref`` is a freeform string pointer (usually a
proposal id, a chat session id, or a NBMF entry id) so consumers can
link back to WHY the message was sent without stuffing full context
into the message body.

Index strategy
--------------
Primary query is "inbox for department X" -- an index on
``(tenant_id, to_department, status)`` covers the ``list_inbox(dept)``
service call which is polled frequently by department agents.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TenantMixin, TimestampMixin

# Status lifecycle -- keep in sync with frontend DepartmentInbox badges.
MESSAGE_STATUS_VALUES = ("SENT", "ACKNOWLEDGED", "ANSWERED", "EXPIRED")


class DepartmentMessage(Base, TenantMixin, TimestampMixin):
    """One inter-department message. Bidirectional via ``answer`` field
    rather than a second row -- keeps the query simple ("fetch by id,
    look at status") and avoids thread-id bookkeeping.
    """

    __tablename__ = "department_messages"
    __table_args__ = (
        Index(
            "ix_department_messages_inbox",
            "tenant_id", "to_department", "status",
        ),
        Index(
            "ix_department_messages_outbox",
            "tenant_id", "from_department", "status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    from_department: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
    )
    to_department: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
    )
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(String(4000), nullable=False)
    # Pointer to the originating context (proposal id, session id, NBMF
    # entry id, etc.). Not an FK -- freeform string so producers can
    # use any naming scheme without coupling.
    context_ref: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="SENT",
    )
    # Reply body. Populated when status flips to ANSWERED. Empty when
    # the reviewer acknowledged but has not yet responded -- we keep
    # ACKNOWLEDGED as a distinct state so senders know their message
    # was SEEN vs just sitting in the inbox.
    answer: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    # Caller-supplied expiry so "urgent" messages can timeout in 5 min
    # while low-priority ones can sit for an hour. Nullable = no expiry.
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    def is_closed(self) -> bool:
        """Terminal state: reviewer can no longer act on this message."""
        return self.status in ("ANSWERED", "EXPIRED")

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "from_department": self.from_department,
            "to_department": self.to_department,
            "subject": self.subject,
            "body": self.body,
            "context_ref": self.context_ref,
            "status": self.status,
            "answer": self.answer,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "acknowledged_at": (
                self.acknowledged_at.isoformat() if self.acknowledged_at else None
            ),
            "answered_at": (
                self.answered_at.isoformat() if self.answered_at else None
            ),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
