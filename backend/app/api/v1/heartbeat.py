"""Heartbeat daemon API endpoints.

Controls the heartbeat daemon: start/stop/pause/resume, configure,
view history, and manage cron jobs.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, get_current_user

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
