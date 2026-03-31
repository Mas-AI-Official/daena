"""DepartmentTask model for persistent scheduled department workflows.

Tracks scheduled workflow executions that survive browser close.
The heartbeat daemon queries this table to find workflows due for execution.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, JSONBCompat, TenantMixin, TimestampMixin


class DepartmentTask(Base, TenantMixin, TimestampMixin):
    """A scheduled department workflow execution.

    Links to workflows defined in department_workflows.py.
    The heartbeat daemon checks this table for due workflows.
    """

    __tablename__ = "department_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4,
    )
    workflow_id: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True,
    )
    department: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Schedule
    cron_expression: Mapped[str] = mapped_column(String(100), nullable=False, server_default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # Execution state
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="SCHEDULED",
    )  # SCHEDULED | RUNNING | COMPLETED | FAILED | PAUSED
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    run_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_result: Mapped[dict | None] = mapped_column(JSONBCompat, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # User context (needed for integration credentials)
    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), nullable=False)
