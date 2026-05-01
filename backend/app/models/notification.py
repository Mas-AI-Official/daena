"""Notification model — minimal in-app notification row.

Phase 11 PR-S2 (2026-05-01): the privacy-enforcement PR-S1 closed the
DEAD-status memory gates from Phase 10b's settings audit; PR-S2 closes
the DEAD-status notification toggles by giving them a real backend
consumer.

Why a dedicated table (not goa_audit_events):
* Audit events are immutable + hash-chained; notifications need a
  mutable ``read_at`` field so the bell can render unread badges.
* ``risk_level`` (LOW/MEDIUM/HIGH/CRITICAL) and ``severity``
  (info/success/warning/error) have different semantics — overloading
  one column for both pollutes either ledger queries or the bell UI.
* Notifications are user-facing copy meant for the bell; audit events
  are governance metadata meant for the audit page. Different UX
  surfaces, different lifetimes.

Why minimal columns (no per-message dedup hash, no thread support, no
group keys):
* The brief is a "stub" — keep the schema small enough that a future
  PR can extend it (add columns) without a destructive migration.
* All eight required fields from the brief are present:
  id, user_id, tenant_id, type, title, message, severity, created_at,
  read_at, source.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class Notification(Base, TimestampMixin):
    """A single in-app notification destined for one user.

    Tenant-scoped so a user in tenant A never sees tenant B rows even
    if a stray query forgets the user filter (defense-in-depth on top
    of the API-layer user-id filter).
    """

    __tablename__ = "notifications"
    __table_args__ = (
        # Bell hot-query: "give me my recent notifications, newest first"
        Index(
            "ix_notifications_user_id_created_at",
            "user_id",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Event taxonomy. See app.services.notification_service._NOTIF_TYPES
    # for the canonical list and the mapping to users.settings.notif_*
    # flags. Stored as a string (not enum) so the catalog can grow
    # without a destructive migration.
    type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)

    # info | success | warning | error. Drives the colored dot in the
    # bell UI. Distinct from audit risk_level (LOW/MEDIUM/HIGH/CRITICAL).
    severity: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="info",
    )

    # Free-form attribution: which subsystem emitted (e.g. "heartbeat",
    # "cost_guard", "memory_service.privacy_block"). Helpful for grep +
    # for grouping in a future digest endpoint.
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # NULL = unread. Set when the user opens the bell or hits the
    # mark-read endpoint (future PR; PR-S2 only emits + lists).
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # created_at / updated_at supplied by TimestampMixin.
