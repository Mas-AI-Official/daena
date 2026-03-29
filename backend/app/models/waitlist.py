"""Waitlist model for early access signups.

Stores email addresses from the landing page and app waitlist form.
No tenant scoping needed since these are pre-registration signups.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class WaitlistEntry(Base, TimestampMixin):
    """An early-access waitlist signup."""

    __tablename__ = "waitlist_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    source: Mapped[str] = mapped_column(
        String(50), default="landing", nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    notified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "email": self.email,
            "source": self.source,
            "position": self.position,
            "notified": self.notified,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
