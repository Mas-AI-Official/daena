"""PushSubscription model -- one registered Web Push endpoint per device.

Phase 4 item 12 (G6, 2026-07-02): push/mobile founder alerts. Each row is
one browser/device Web Push registration (RFC 8030) belonging to one user.
``NotificationService`` mirrors push-worthy in-app notifications to every
ACTIVE (revoked_at IS NULL) subscription of the recipient through the
channel seam in ``app.services.notification_channels``.

Why soft-revoke (revoked_at) instead of DELETE:
* An endpoint that returns 404/410 is dead at the push service; keeping
  the row (revoked) preserves the audit trail of which device stopped
  receiving and when, and re-subscribing the same endpoint simply
  un-revokes it (idempotent upsert in the API layer).
* Rule 2: never delete -- archive/flag instead.

Why endpoint is globally unique:
* A push endpoint identifies exactly one (browser profile, origin)
  registration. If a different user logs in on the same device and
  subscribes, the device now belongs to that login -- the API reassigns
  the row rather than duplicating it (two rows would double-deliver).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class PushSubscription(Base, TimestampMixin):
    """A single Web Push registration for one user's device.

    Tenant-scoped (defense-in-depth, same rationale as Notification).
    Only FOUNDER-role users can create rows (enforced at the API layer),
    so delivery fan-out never needs its own role check.
    """

    __tablename__ = "push_subscriptions"
    __table_args__ = (
        # Fan-out hot-query: "active subscriptions for this user".
        Index(
            "ix_push_subscriptions_user_id_revoked_at",
            "user_id",
            "revoked_at",
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

    # Push-service URL (FCM/Mozilla autopush/etc.). Globally unique --
    # see module docstring for the reassignment semantic.
    endpoint: Mapped[str] = mapped_column(
        String(1024), nullable=False, unique=True,
    )

    # Client public key + auth secret from PushSubscription.getKey()
    # (base64url). These are the ENCRYPTION keys for this endpoint, not
    # credentials for our system -- storing them is how Web Push works.
    p256dh: Mapped[str] = mapped_column(String(200), nullable=False)
    auth: Mapped[str] = mapped_column(String(100), nullable=False)

    # Free-form device hint for the founder's own bookkeeping.
    user_agent: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # NULL = active. Set on explicit unsubscribe OR when the push service
    # reports the endpoint gone (404/410).
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # created_at / updated_at supplied by TimestampMixin.
