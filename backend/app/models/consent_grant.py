"""ConsentGrant: persistent storage for skill-execution consent grants.

PR-CONN-CONSENT-DB-PERSISTENCE (Sprint-6 PR-5, 2026-05-04).

Sprint-4 / Sprint-5 shipped the Asset Shield consent gate with an
in-memory ``ConsentStore`` that survives only the lifetime of a
single FastAPI process. That is fine for local dev + single-instance
laptop runs but breaks on multi-instance deploy (Cloud Run, k8s)
because a grant minted on replica A is invisible to replica B.

This model + its DB-backed store make grants survive across replicas
and process restarts. The schema is INTENTIONALLY MINIMAL: only
the metadata needed to enforce single-use, TTL, and tenant binding.
NEVER stores:

  * Token values (none exist; this is consent, not OAuth).
  * Operator input values.
  * Tool args, response previews, or any execution payload.
  * Anything that could leak a credential or PII.

Tenant isolation: every query filters on ``tenant_id`` as the
non-negotiable first clause. The grant is scoped to
``(tenant_id, plugin_id, skill_id, category)`` -- the exact same
matching contract as the in-memory store.

Single-use semantics: ``consumed_at`` is the consume marker. The
DB store sets it via an UPDATE ... WHERE consumed_at IS NULL with
a row-count check; concurrent consumes from two replicas resolve
deterministically (only one wins).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TenantMixin, TimestampMixin


class ConsentGrant(Base, TenantMixin, TimestampMixin):
    """One row per minted consent grant (single-use unless re-minted).

    Tenant scoping is enforced at the query layer (DBConsentStore
    always filters on tenant_id first). The TenantMixin gives us the
    indexed FK + cascade-on-tenant-delete semantics for free.
    """

    __tablename__ = "consent_grants"

    __table_args__ = (
        # Hot path is "find an unconsumed unexpired grant for
        # (tenant, plugin, skill, category)". This composite index
        # makes that selective on every dialect.
        Index(
            "ix_consent_grants_match_lookup",
            "tenant_id", "plugin_id", "skill_id", "category",
        ),
        Index("ix_consent_grants_expires_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    # The user who minted the grant. Optional for forward-compat:
    # the executor matches on tenant_id only (consent is a tenant-
    # scoped contract today). Captured for audit trail.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID(),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    plugin_id: Mapped[str] = mapped_column(String(120), nullable=False)
    skill_id: Mapped[str] = mapped_column(String(120), nullable=False)
    # Stored as the raw enum value (lowercase snake_case) so a future
    # category addition does not require a migration -- the application
    # layer validates against the SkillConsentCategory enum.
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    consumed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
