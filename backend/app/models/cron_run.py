"""CronRun: per-execution audit row for the cron scheduler.

Replaces the prior fictional ``last_result = "executed"`` literal in
``cron_scheduler.check_and_run`` with a real database trail of every
attempted job. Each row captures the runtime that was used, when the
job started/finished, the duration, the actual output (truncated
summary plus full text), any error, and the cost / token counts so
the operator can audit cron-driven runtime burn.

This model is intentionally NOT tenant-scoped: cron jobs are system-
initiated background work that runs as ``tenant_id="system"`` from
the scheduler's point of view, and the GUID/string compatibility
layer in ``models.base`` handles dialect differences.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TimestampMixin


class CronRun(Base, TimestampMixin):
    """A single recorded execution of a cron job.

    One row is inserted per ``check_and_run`` invocation that fires a
    job. ``finished_at``, ``duration_ms``, ``summary``, ``full_text``,
    ``cost_usd``, ``tokens_in``, ``tokens_out``, and ``error`` are
    nullable until the runtime call completes (or errors).
    """

    __tablename__ = "cron_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    job_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    runtime: Mapped[str | None] = mapped_column(String(50), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    full_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    tokens_in: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
