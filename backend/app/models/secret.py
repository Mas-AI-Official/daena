"""Secret model: envelope-encrypted secret storage (Phase 4a-2).

One row per encrypted secret. The wire shape produced by
``app.core.vault_v2.encrypt_secret()`` maps directly onto these
columns:

    ciphertext       <- record["ciphertext"]      (base64 str -> BYTEA after decode)
    nonce            <- record["nonce"]
    tag              <- record["tag"]
    dek_version      <- record["dek_version"]
    kek_version      <- record["kek_version"]
    tenant_id        <- record["tenant_id"]
    secret_class     <- record["class"]
    bound_to         <- record["bound_to"]
    format_version   <- record["format_version"]

Per ADR-002 D-003: Phase 4a-2 lands the model + migration only.
Phase 4b is what actually starts INSERTing rows here (registry rewrite
threads vault_v2 into the OAuth/API-key paths). Until then, the table
exists empty and the legacy ConnectorInstance.credentials_encrypted
path stays the production source of truth.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TenantMixin, TimestampMixin


class Secret(Base, TenantMixin, TimestampMixin):
    """Envelope-encrypted secret blob.

    One row per (tenant_id, secret_class, bound_to). Tenant isolation
    is structural via TenantMixin + the ORM tenant_guard listener
    (per ADR-002 D-003). Ciphertext is opaque -- no column is queryable
    by content. Lookups are by (tenant_id, secret_class, bound_to).
    """

    __tablename__ = "secrets"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )

    # AAD-bound identity. (tenant_id, secret_class, bound_to) is unique.
    secret_class: Mapped[str] = mapped_column(String(64), nullable=False)
    bound_to: Mapped[str] = mapped_column(String(256), nullable=False)

    # Ciphertext + GCM nonce/tag.
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary(12), nullable=False)
    tag: Mapped[bytes] = mapped_column(LargeBinary(16), nullable=False)

    # Versioning for rotation + format evolution.
    dek_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    kek_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    format_version: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    # Wall-clock of last rotation (separate from updated_at which tracks
    # any UPDATE). NULL until the row is rotated.
    rotated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "secret_class", "bound_to",
            name="uq_secrets_tenant_class_bound",
        ),
        Index("ix_secrets_tenant_class", "tenant_id", "secret_class"),
    )

    def __repr__(self) -> str:  # pragma: no cover -- debug helper only
        return (
            f"<Secret tenant={self.tenant_id} class={self.secret_class} "
            f"bound_to={self.bound_to} dek_version={self.dek_version}>"
        )
