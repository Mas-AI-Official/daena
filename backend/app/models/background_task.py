"""BackgroundTask ORM model: persistent storage for the autopilot queue.

Why this exists (2026-04-29 audit):
    The in-process ``BackgroundQueue`` previously held all task state in
    ``_active: dict`` and ``_history: list``. A backend restart wiped both
    structures. Queued tasks vanished silently and tasks that were running
    at restart became orphans (the worker disappeared, the row never moved
    out of ``running``).

    This model provides crash-safe persistence so:
      * Queued tasks survive a restart (re-enqueued by ``restore_queue_from_db``).
      * Running tasks at restart are explicitly marked
        ``failed_due_to_restart`` per CLAUDE.md Hard Law #1
        ("never auto-retry destructive operations") so the operator can
        decide whether to re-run them.
      * Historical task rows are queryable by tenant / session for audit
        and the existing ``get_summary`` API.

    The ``id`` mirrors the in-memory dataclass id so the queue and the DB
    stay in sync without an extra mapping layer.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import (
    GUID,
    Base,
    JSONBCompat,
    TenantMixin,
    TimestampMixin,
)


class BackgroundTask(Base, TenantMixin, TimestampMixin):
    """Persistent record of a background-queue task.

    Lifecycle (status field, indexed):

        queued -> running -> complete
                          \\-> failed
                          \\-> cancelled
        running -> failed_due_to_restart  (set on startup recovery)

    The id matches the in-memory dataclass id so callers can pass either
    the dataclass or the db row id interchangeably.
    """

    __tablename__ = "background_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )

    session_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True,
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)

    # queued / running / complete / failed / cancelled / failed_due_to_restart
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="queued",
        server_default="queued",
        index=True,
    )

    # P0_CRITICAL / P1_HIGH / P2_NORMAL / P3_LOW
    priority: Mapped[str] = mapped_column(
        String(5),
        nullable=False,
        default="P2",
        server_default="P2",
    )

    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.utcnow(),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    result: Mapped[dict | None] = mapped_column(JSONBCompat, nullable=True)
    error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    runtime: Mapped[str | None] = mapped_column(String(50), nullable=True)
    cost_usd: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        server_default="0.0",
    )

    # Optional link to the chat request that spawned this task.
    parent_request_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"<BackgroundTask id={self.id} status={self.status} "
            f"session={self.session_id} priority={self.priority}>"
        )
