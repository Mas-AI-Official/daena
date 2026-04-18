"""Department state registry -- live view of what each department is doing.

Session A (Piece 1 of the "Daena as a Living Company" plan). The
Daena VP cannot route intelligently without knowing which
departments are idle, which are saturated, and what each is
currently working on. This model + service answers that.

Design
------
One row per ``(tenant_id, department_name)`` -- the Company Dashboard
shows the snapshot, the Daena VP consults it during routing.

Writers
-------
- ``SwarmExecutor.execute_single`` marks WORKING before running a
  subtask, IDLE after. This keeps the registry in sync without the
  departments having to self-report.
- Future: ``AutopilotController`` may set OFFLINE during kill-switch
  events.

Status lifecycle::

    IDLE        -- department has no current task
    WORKING     -- department currently executing a subtask
    OVERLOADED  -- queue_depth >= overload_threshold (for v1: 5)
    OFFLINE     -- kill-switch engaged or health probe failed

The ``queue_depth`` int is a logical counter, not a true capacity
measurement (per the operator's v1 decision). It increments on
every mark_working and decrements on every mark_idle.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import GUID, Base, TenantMixin, TimestampMixin

# Valid status strings. Keep in sync with the frontend badge colors.
DEPARTMENT_STATUS_VALUES = ("IDLE", "WORKING", "OVERLOADED", "OFFLINE")

# queue_depth >= this flips the status badge to OVERLOADED
DEFAULT_OVERLOAD_THRESHOLD = 5


class DepartmentState(Base, TenantMixin, TimestampMixin):
    """Live state of one department for one tenant.

    Rows are created lazily by DepartmentStateService.get_or_create.
    The Company Dashboard expects all 10 departments to exist after
    the first snapshot call, so new tenants get a bulk-init on first
    dashboard fetch.
    """

    __tablename__ = "department_states"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "department_name",
            name="uq_department_states_tenant_dept",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4,
    )
    department_name: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="IDLE",
    )
    # Task currently in flight (best-effort: WORKING without a task_id
    # can happen for prompt-driven work that isn't a formal subtask).
    current_task_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
    )
    current_task_summary: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
    )
    queue_depth: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0",
    )
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    def is_overloaded(self, threshold: int = DEFAULT_OVERLOAD_THRESHOLD) -> bool:
        """Whether this department should be skipped by load-balancing router."""
        return self.queue_depth >= threshold
