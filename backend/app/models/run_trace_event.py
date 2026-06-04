"""RunTraceEvent model -- local OpenAI-Agents-SDK-style run spans.

A queryable span per pipeline step on a SUCCESSFUL (or failing) chat run,
complementing ErrorEvent (which is the failure-only sink). Together they give
founder/operator run-visibility without an external telemetry SaaS.

Design choices (mirror error_event.py)
--------------------------------------
* Separate table from ErrorEvent: error events are failure-shaped telemetry;
  trace events are per-stage spans with different query patterns. Overloading
  one would muddy both.
* tenant_id / user_id / session_id are NULLABLE with NO ForeignKey. A span can
  be emitted before auth/session resolves, and -- critically -- recording a
  span must never itself fail on an FK violation. Best-effort, like the sink.
* SAFE FIELDS ONLY. Never store prompts, responses, system prompts, request
  bodies, decrypted credentials, API keys, or raw provider error text.
  safe_summary is a short, redacted, human description; metadata_json holds
  only redacted structured context. Long values are capped by the recorder.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, JSONBCompat, TimestampMixin


class RunTraceEvent(Base, TimestampMixin):
    """One safe span in a chat run, keyed by request_id/run_id."""

    __tablename__ = "run_trace_events"
    __table_args__ = (
        Index("ix_run_trace_events_request_id", "request_id"),
        Index("ix_run_trace_events_run_id", "run_id"),
        Index("ix_run_trace_events_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    # Correlation: request_id from the X-Request-ID spine; run_id from the
    # orchestrator. session_id ties spans of a session together.
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    # Nullable + NO FK on purpose (best-effort span, see module docstring).
    tenant_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), nullable=True)
    # event_type: chat.start | governance.effective_mode | provider.selected |
    # fallback.used | memory.persisted | stream.error | chat.end | <subsystem>.
    event_type: Mapped[str] = mapped_column(String(48), nullable=False)
    # stage: the pipeline stage label (e.g. "6_model_router", "9_persist").
    stage: Mapped[str | None] = mapped_column(String(48), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(96), nullable=True)
    governance_mode: Mapped[str | None] = mapped_column(String(24), nullable=True)
    # status: ok | error | fallback | skipped.
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="ok",
    )
    # Short redacted human summary (capped by the recorder). NEVER prompt text.
    safe_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Redacted structured context only (no secrets/bodies/prompts).
    metadata_json: Mapped[dict | None] = mapped_column(JSONBCompat(), nullable=True)
