"""ErrorEvent model -- durable, safe runtime-error trail (DEP-007).

A minimal sink so 5xx / unhandled / streaming-fallback failures are
reviewable after the fact by the founder/operator, complementing the
structured logs (which scroll away) and the in-memory frontend
errorStore (which dies on reload).

Design choices
--------------
* Separate table (not goa_audit_events): audit events are immutable +
  hash-chained governance metadata; error events are mutable-free
  operational telemetry with different lifetime + query patterns.
* tenant_id / user_id are NULLABLE and carry NO ForeignKey. An error
  can occur before auth resolves (no tenant/user), and -- critically --
  recording a failure must never itself fail on an FK violation. The
  sink is best-effort: a bad/synthetic id must still write a row.
* SAFE FIELDS ONLY. Never store secrets, tokens, decrypted credentials,
  request bodies, or raw stack traces (the full traceback stays in the
  server log, correlated by request_id). safe_message is the same
  generic text shown to the user.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, JSONBCompat, TimestampMixin


class ErrorEvent(Base, TimestampMixin):
    """One recorded runtime error, safe for founder/operator review."""

    __tablename__ = "error_events"
    __table_args__ = (
        Index("ix_error_events_created_at", "created_at"),
        Index("ix_error_events_request_id", "request_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    # info | warning | error | critical
    severity: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="error",
    )
    # Emitter: "exception_handler" | "sse_stream" | "<subsystem>"
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    route: Mapped[str | None] = mapped_column(String(256), nullable=True)
    method: Mapped[str | None] = mapped_column(String(8), nullable=True)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Exception class name only (e.g. "ValueError") -- safe, not the message.
    error_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # The generic, user-safe message. NEVER raw exc text with internals.
    safe_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Nullable + NO FK on purpose (see module docstring).
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Redacted structured context only (no secrets/bodies).
    metadata_json: Mapped[dict | None] = mapped_column(JSONBCompat(), nullable=True)
