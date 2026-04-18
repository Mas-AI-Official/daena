"""Department state service -- the source of truth for dept availability.

Session A of the "Daena as a Living Company" plan. This service is
consulted by:

* ``SwarmExecutor.execute_single`` -- writes state as subtasks start/end
* ``DaenaVP.route`` (future, Session B) -- reads snapshot to pick
  departments that aren't OVERLOADED
* Company Dashboard UI -- polls ``snapshot()`` every 5s for live view

The 10 canonical department names match ``organization.Department``
seeding. If a new department is added, ``_CANONICAL_DEPARTMENTS``
should be extended so the dashboard always shows a full company.
"""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.department_state import (
    DEFAULT_OVERLOAD_THRESHOLD,
    DEPARTMENT_STATUS_VALUES,
    DepartmentState,
)

logger = get_logger(__name__)


# The 10 departments Daena seeds for every tenant. Keeping this as a
# module-level tuple rather than hitting the Department table on every
# snapshot -- the set is stable and does not churn per tenant.
_CANONICAL_DEPARTMENTS: tuple[str, ...] = (
    "Engineering",
    "Product",
    "Marketing",
    "Sales",
    "Finance",
    "Operations",
    "Research",
    "Legal & Compliance",
    "Skill Governance",
    "Security Operations",
)


class DepartmentStateService:
    """CRUD + transitions for the department state registry."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    # ── Fetch / upsert ─────────────────────────────────────────

    async def _get_or_create(
        self,
        *,
        tenant_id: UUID,
        department: str,
    ) -> DepartmentState:
        """Lazy creation: on first read for a (tenant, dept) pair, insert
        a default IDLE row. Keeps seeding out of migrations and lets
        tenants that never call a department save a row."""
        stmt = select(DepartmentState).where(
            DepartmentState.tenant_id == tenant_id,
            DepartmentState.department_name == department,
        )
        result = await self._db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing

        row = DepartmentState(
            tenant_id=tenant_id,
            department_name=department,
            status="IDLE",
            queue_depth=0,
        )
        self._db.add(row)
        await self._db.flush()
        return row

    # ── Transitions ────────────────────────────────────────────

    async def mark_working(
        self,
        *,
        tenant_id: UUID,
        department: str,
        task_id: str | None = None,
        task_summary: str | None = None,
        overload_threshold: int = DEFAULT_OVERLOAD_THRESHOLD,
    ) -> DepartmentState:
        """Called by SwarmExecutor before a subtask runs. Increments the
        queue depth; flips status to OVERLOADED when the threshold is
        reached."""
        row = await self._get_or_create(tenant_id=tenant_id, department=department)
        row.queue_depth = row.queue_depth + 1
        row.current_task_id = task_id
        row.current_task_summary = (task_summary or "")[:500] or None
        row.last_activity_at = datetime.now(UTC)
        row.status = "OVERLOADED" if row.queue_depth >= overload_threshold else "WORKING"
        await self._db.flush()
        logger.info(
            "department_state.mark_working",
            department=department, queue_depth=row.queue_depth, status=row.status,
        )
        return row

    async def mark_idle(
        self,
        *,
        tenant_id: UUID,
        department: str,
        overload_threshold: int = DEFAULT_OVERLOAD_THRESHOLD,
    ) -> DepartmentState:
        """Called by SwarmExecutor after a subtask completes (success OR
        failure). Decrements queue_depth; flips to IDLE when it reaches
        zero."""
        row = await self._get_or_create(tenant_id=tenant_id, department=department)
        if row.queue_depth > 0:
            row.queue_depth = row.queue_depth - 1
        row.last_activity_at = datetime.now(UTC)
        if row.queue_depth == 0:
            row.status = "IDLE"
            row.current_task_id = None
            row.current_task_summary = None
        elif row.queue_depth >= overload_threshold:
            row.status = "OVERLOADED"
        else:
            row.status = "WORKING"
        await self._db.flush()
        logger.info(
            "department_state.mark_idle",
            department=department, queue_depth=row.queue_depth, status=row.status,
        )
        return row

    async def set_offline(
        self,
        *,
        tenant_id: UUID,
        department: str,
    ) -> DepartmentState:
        """Emergency: kill-switch or health probe failed. Queue is
        preserved so recovering doesn't lose in-flight counts."""
        row = await self._get_or_create(tenant_id=tenant_id, department=department)
        row.status = "OFFLINE"
        row.last_activity_at = datetime.now(UTC)
        await self._db.flush()
        return row

    # ── Read ──────────────────────────────────────────────────

    async def snapshot(self, *, tenant_id: UUID) -> list[dict]:
        """Return a dict per canonical department. Missing rows are
        materialized as IDLE defaults so the Company Dashboard always
        renders all 10 cards even for a brand-new tenant.

        Output shape (stable, read by the frontend hook):
          [
            {department_name, status, current_task_id,
             current_task_summary, queue_depth, last_activity_at},
            ...
          ]
        """
        stmt = select(DepartmentState).where(
            DepartmentState.tenant_id == tenant_id,
        )
        result = await self._db.execute(stmt)
        rows = {r.department_name: r for r in result.scalars().all()}

        out: list[dict] = []
        for name in _CANONICAL_DEPARTMENTS:
            r = rows.get(name)
            if r is None:
                out.append({
                    "department_name": name,
                    "status": "IDLE",
                    "current_task_id": None,
                    "current_task_summary": None,
                    "queue_depth": 0,
                    "last_activity_at": None,
                })
            else:
                out.append({
                    "department_name": r.department_name,
                    "status": r.status,
                    "current_task_id": r.current_task_id,
                    "current_task_summary": r.current_task_summary,
                    "queue_depth": r.queue_depth,
                    "last_activity_at": (
                        r.last_activity_at.isoformat() if r.last_activity_at else None
                    ),
                })
        return out

    async def list_available(
        self,
        *,
        tenant_id: UUID,
        overload_threshold: int = DEFAULT_OVERLOAD_THRESHOLD,
    ) -> list[str]:
        """Return department names that are NOT overloaded/offline.

        Used by DaenaVP.route (Session B) to pick from the available
        pool; if everything is overloaded, returns the full canonical
        list so routing doesn't deadlock on a saturated company.
        """
        snap = await self.snapshot(tenant_id=tenant_id)
        available = [
            s["department_name"] for s in snap
            if s["status"] in ("IDLE", "WORKING")
            and s["queue_depth"] < overload_threshold
        ]
        if not available:
            return list(_CANONICAL_DEPARTMENTS)
        return available
