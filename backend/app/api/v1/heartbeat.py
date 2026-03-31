"""Heartbeat daemon API endpoints.

Controls the heartbeat daemon: start/stop/pause/resume, configure,
view history, and manage cron jobs.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db

router = APIRouter()


def _get_daemon():
    from app.services.heartbeat.heartbeat_daemon import HeartbeatDaemon

    return HeartbeatDaemon.get_instance()


def _get_scheduler():
    from app.services.heartbeat.cron_scheduler import CronScheduler

    # Lazy singleton
    if not hasattr(_get_scheduler, "_instance"):
        _get_scheduler._instance = CronScheduler.with_defaults()
    return _get_scheduler._instance


@router.get("/status")
async def heartbeat_status(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Get current heartbeat daemon status."""
    daemon = _get_daemon()
    return {"success": True, "data": daemon.get_status()}


@router.post("/start")
async def heartbeat_start(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Start the heartbeat daemon."""
    daemon = _get_daemon()
    await daemon.start()
    return {"success": True, "data": daemon.get_status()}


@router.post("/pause")
async def heartbeat_pause(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Pause the heartbeat daemon."""
    daemon = _get_daemon()
    await daemon.pause()
    return {"success": True, "data": daemon.get_status()}


@router.post("/resume")
async def heartbeat_resume(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Resume a paused heartbeat daemon."""
    daemon = _get_daemon()
    await daemon.resume()
    return {"success": True, "data": daemon.get_status()}


@router.post("/stop")
async def heartbeat_stop(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Stop the heartbeat daemon."""
    daemon = _get_daemon()
    await daemon.stop()
    return {"success": True, "data": daemon.get_status()}


@router.post("/configure")
async def heartbeat_configure(
    updates: dict,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Update heartbeat configuration."""
    daemon = _get_daemon()
    daemon.configure(updates)
    return {"success": True, "data": daemon.config.to_dict()}


@router.get("/history")
async def heartbeat_history(
    limit: int = 20,
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Get heartbeat cycle history."""
    daemon = _get_daemon()
    return {"success": True, "data": daemon.get_history(limit)}


@router.post("/run-once")
async def heartbeat_run_once(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Manually trigger a single heartbeat cycle."""
    daemon = _get_daemon()
    cycle = await daemon.run_once()
    return {"success": True, "data": cycle.to_dict()}


@router.get("/config")
async def heartbeat_config(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Get current heartbeat configuration."""
    daemon = _get_daemon()
    return {"success": True, "data": daemon.config.to_dict()}


# ── Cron jobs ──

@router.get("/cron")
async def list_cron_jobs(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """List all registered cron jobs."""
    scheduler = _get_scheduler()
    return {"success": True, "data": scheduler.get_jobs()}


# ── Work Queue ──

def _get_queue():
    from app.services.heartbeat.work_queue import WorkQueue

    if not hasattr(_get_queue, "_instance"):
        _get_queue._instance = WorkQueue.overnight_default()
    return _get_queue._instance


@router.get("/queue")
async def list_queue(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """List all tasks in the work queue."""
    queue = _get_queue()
    return {"success": True, "data": queue.get_all()}


@router.get("/queue/summary")
async def queue_summary(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Get queue summary (counts by status, total cost)."""
    queue = _get_queue()
    return {"success": True, "data": queue.get_summary()}


@router.get("/queue/briefing")
async def queue_briefing(
    _user: CurrentUser = Depends(get_current_user),
) -> dict:
    """Generate morning briefing from queue results."""
    queue = _get_queue()
    return {"success": True, "data": {"briefing": queue.generate_briefing()}}


# ── Department Tasks ──

@router.get("/department-tasks")
async def list_department_tasks(
    department: str | None = None,
    _user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all scheduled department tasks."""
    from sqlalchemy import select
    from app.models.department_task import DepartmentTask

    stmt = select(DepartmentTask).where(DepartmentTask.tenant_id == _user.tenant_id)
    if department:
        stmt = stmt.where(DepartmentTask.department == department)
    stmt = stmt.order_by(DepartmentTask.department, DepartmentTask.name)

    result = await db.execute(stmt)
    tasks = result.scalars().all()

    return {
        "success": True,
        "data": [
            {
                "id": str(t.id),
                "workflow_id": t.workflow_id,
                "department": t.department,
                "name": t.name,
                "description": t.description,
                "cron_expression": t.cron_expression,
                "is_active": t.is_active,
                "status": t.status,
                "last_run_at": t.last_run_at.isoformat() if t.last_run_at else None,
                "next_run_at": t.next_run_at.isoformat() if t.next_run_at else None,
                "run_count": t.run_count,
                "last_error": t.last_error,
            }
            for t in tasks
        ],
    }


@router.post("/department-tasks/seed")
async def seed_department_tasks(
    _user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Seed default department tasks from workflow definitions.

    Creates DepartmentTask records for all workflows that have a cron schedule.
    Idempotent -- skips workflows that already have a task.
    """
    from datetime import timezone
    from sqlalchemy import select
    from app.models.department_task import DepartmentTask
    from app.services.department_workflows import DepartmentWorkflowEngine

    workflows = DepartmentWorkflowEngine.get_scheduled_workflows()
    created = []

    for wf in workflows:
        existing = await db.execute(
            select(DepartmentTask)
            .where(DepartmentTask.workflow_id == wf.id)
            .where(DepartmentTask.tenant_id == _user.tenant_id)
        )
        if existing.scalar_one_or_none() is not None:
            continue

        next_run = None
        if wf.schedule:
            try:
                from croniter import croniter
                cron = croniter(wf.schedule, datetime.now(timezone.utc))
                next_run = cron.get_next(datetime)
            except Exception:
                pass

        task = DepartmentTask(
            workflow_id=wf.id,
            department=wf.department,
            name=wf.name,
            description=wf.description,
            cron_expression=wf.schedule,
            is_active=True,
            status="SCHEDULED",
            next_run_at=next_run,
            user_id=_user.id,
            tenant_id=_user.tenant_id,
        )
        db.add(task)
        created.append(wf.id)

    if created:
        await db.commit()

    return {
        "success": True,
        "data": {
            "created": created,
            "total_workflows": len(workflows),
            "already_existed": len(workflows) - len(created),
        },
    }


@router.post("/department-tasks/{task_id}/toggle")
async def toggle_department_task(
    task_id: str,
    _user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Toggle a department task active/paused."""
    from uuid import UUID
    from sqlalchemy import select
    from app.models.department_task import DepartmentTask

    result = await db.execute(
        select(DepartmentTask)
        .where(DepartmentTask.id == UUID(task_id))
        .where(DepartmentTask.tenant_id == _user.tenant_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        return {"success": False, "error": "Task not found"}

    task.is_active = not task.is_active
    task.status = "SCHEDULED" if task.is_active else "PAUSED"
    await db.commit()

    return {
        "success": True,
        "data": {
            "id": str(task.id),
            "is_active": task.is_active,
            "status": task.status,
        },
    }


@router.post("/department-tasks/{task_id}/run-now")
async def run_department_task_now(
    task_id: str,
    _user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Manually trigger a department task immediately."""
    from uuid import UUID
    from datetime import timezone
    from sqlalchemy import select
    from app.models.department_task import DepartmentTask
    from app.services.department_workflows import DepartmentWorkflowEngine

    result = await db.execute(
        select(DepartmentTask)
        .where(DepartmentTask.id == UUID(task_id))
        .where(DepartmentTask.tenant_id == _user.tenant_id)
    )
    task = result.scalar_one_or_none()
    if task is None:
        return {"success": False, "error": "Task not found"}

    engine = DepartmentWorkflowEngine(db, _user.id, _user.tenant_id)
    wf_result = await engine.run(task.workflow_id)

    task.last_run_at = datetime.now(timezone.utc)
    task.run_count += 1
    task.last_result = wf_result.to_dict()
    task.last_error = wf_result.error
    task.status = "COMPLETED" if wf_result.status == "completed" else "FAILED"
    await db.commit()

    return {"success": wf_result.status == "completed", "data": wf_result.to_dict()}
