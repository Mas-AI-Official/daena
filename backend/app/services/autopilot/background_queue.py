"""Background Queue: manages tasks spawned by Autopilot.

Provides a bounded-concurrency queue for background task execution.
Tasks are processed by a worker loop that respects the semaphore limit.
Supports cancellation of individual tasks or all tasks for a session.

Persistence (2026-04-29 audit fix):
    The queue now mirrors task state into the ``background_tasks`` table
    when an ``async_session_factory`` is provided at construction time.
    Without the factory the queue stays in-memory only (used by unit
    tests that do not need DB integration).

    On startup, ``restore_queue_from_db`` re-enqueues tasks that were
    ``queued`` and marks ``running`` rows as ``failed_due_to_restart``
    (CLAUDE.md Hard Law #1: never auto-retry destructive operations,
    let the operator decide).

    The init/shutdown helpers at the bottom of this module give the
    FastAPI lifespan a single entry point that wires up restoration plus
    the worker task. ``main.py`` and ``models/__init__.py`` are not
    touched by this module per the audit ticket.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, update

from app.core.logging import get_logger
from app.models.background_task import BackgroundTask as BackgroundTaskRow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = get_logger(__name__)


# Type alias: callable returning an async session context manager.
# Mirrors ``async_session_factory`` from ``app.core.database``.
SessionFactory = Callable[..., Any]


@dataclass
class BackgroundTask:
    """A background task spawned by Autopilot.

    Attributes:
        id: Unique task identifier (UUID string).
        tenant_id: Owning tenant (required for DB persistence).
        session_id: Chat session that spawned this task.
        description: Human-readable description.
        priority: P0_CRITICAL / P1_HIGH / P2_NORMAL / P3_LOW.
        created_at: ISO timestamp of creation.
        status: Current status (queued, running, complete, failed,
            cancelled, failed_due_to_restart).
        result: Task result data (populated on completion).
        runtime: Optional runtime id used to execute the task.
        cost_usd: Aggregated cost charged to the session.
        parent_request_id: Optional chat request id that spawned this task.
    """

    id: str
    session_id: str
    description: str
    tenant_id: str | None = None
    priority: str = "P2"
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    status: str = "queued"
    result: dict[str, Any] | None = None
    runtime: str | None = None
    cost_usd: float = 0.0
    parent_request_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API responses."""
        return {
            "id": self.id,
            "tenant_id": self.tenant_id,
            "session_id": self.session_id,
            "description": self.description,
            "priority": self.priority,
            "created_at": self.created_at,
            "status": self.status,
            "result": self.result,
            "runtime": self.runtime,
            "cost_usd": self.cost_usd,
            "parent_request_id": self.parent_request_id,
        }


def _to_uuid(value: str | uuid.UUID | None) -> uuid.UUID | None:
    """Best-effort cast of a string/UUID to UUID; None passes through."""
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


class BackgroundQueue:
    """Manages background tasks with bounded concurrency.

    Usage::

        queue = BackgroundQueue(
            max_concurrent=3,
            db_session_factory=async_session_factory,
        )
        asyncio.create_task(queue.start_worker())

        await queue.enqueue(BackgroundTask(
            id="task-1",
            tenant_id="...",
            session_id="sess-abc",
            description="Analyze repository",
        ))

        summary = queue.get_summary("sess-abc")

    When ``db_session_factory`` is None, the queue stays in-memory only.
    """

    def __init__(
        self,
        max_concurrent: int = 3,
        db_session_factory: SessionFactory | None = None,
        executor: Callable[[BackgroundTask], Awaitable[dict[str, Any] | None]] | None = None,
    ) -> None:
        """Initialize with bounded concurrency.

        Args:
            max_concurrent: Maximum tasks running simultaneously.
            db_session_factory: Optional async session factory. When
                provided, every queue mutation is mirrored to the
                ``background_tasks`` table. When None, queue is purely
                in-memory (used by unit tests).
            executor: Optional async callable that performs the task's
                actual work. Receives the task and returns a result dict
                (or None). When None, ``_process`` no-ops the work step
                (legacy behaviour kept for backwards compatibility with
                the old in-memory tests).
        """
        self._queue: asyncio.Queue[BackgroundTask] = asyncio.Queue()
        self._active: dict[str, BackgroundTask] = {}
        self._history: list[BackgroundTask] = []
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._running = False
        self._max_concurrent = max_concurrent
        self._db_session_factory: SessionFactory | None = db_session_factory
        self._executor = executor

    # ── Worker lifecycle ──

    async def start_worker(self) -> None:
        """Start the background worker loop.

        Runs forever, pulling tasks from the queue and processing them
        with bounded concurrency. Call queue.stop() to terminate.
        """
        self._running = True
        logger.info(
            "background_queue.worker_started",
            max_concurrent=self._max_concurrent,
            persistent=self._db_session_factory is not None,
        )

        while self._running:
            try:
                task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                asyncio.create_task(self._process(task))
            except TimeoutError:
                continue
            except Exception as exc:
                logger.error("background_queue.worker_error", error=str(exc))

    def stop(self) -> None:
        """Stop the worker loop."""
        self._running = False

    # ── Enqueue / cancel ──

    async def enqueue(self, task: BackgroundTask) -> None:
        """Add a task to the queue and persist a row.

        Args:
            task: BackgroundTask to enqueue.
        """
        await self._queue.put(task)

        if self._db_session_factory is not None:
            try:
                await self._insert_row(task)
            except Exception as exc:
                logger.error(
                    "background_queue.enqueue_persist_failed",
                    task_id=task.id,
                    error=str(exc),
                )

        logger.info(
            "background_queue.enqueued",
            task_id=task.id,
            session_id=task.session_id,
            priority=task.priority,
        )
        await _emit_queue_event(
            "task.enqueued",
            {
                "task_id": task.id,
                "session_id": task.session_id,
                "tenant_id": task.tenant_id,
                "description": task.description,
                "priority": task.priority,
                "created_at": task.created_at,
            },
        )

    async def cancel(self, task_id: str) -> bool:
        """Cancel a running or queued task.

        Args:
            task_id: ID of the task to cancel.

        Returns:
            True if the task was found and cancelled.
        """
        if task_id in self._active:
            self._active[task_id].status = "cancelled"
            await self._update_row(
                task_id,
                status="cancelled",
                finished_at=datetime.now(UTC),
            )
            logger.info("background_queue.cancelled", task_id=task_id)
            await _emit_queue_event(
                "task.cancelled",
                {
                    "task_id": task_id,
                    "session_id": self._active[task_id].session_id,
                },
            )
            return True
        return False

    async def cancel_all(self, session_id: str) -> int:
        """Cancel all tasks for a session (kill switch support).

        Args:
            session_id: Session whose tasks should be cancelled.

        Returns:
            Number of tasks cancelled.
        """
        count = 0
        for task in self._active.values():
            if task.session_id == session_id:
                task.status = "cancelled"
                count += 1

        # Bulk update DB rows for the session.
        if self._db_session_factory is not None and count > 0:
            try:
                async with self._db_session_factory() as session:
                    await session.execute(
                        update(BackgroundTaskRow)
                        .where(
                            BackgroundTaskRow.session_id == session_id,
                            BackgroundTaskRow.status.in_(["queued", "running"]),
                        )
                        .values(
                            status="cancelled",
                            finished_at=datetime.now(UTC),
                        ),
                    )
                    await session.commit()
            except Exception as exc:
                logger.error(
                    "background_queue.cancel_all_persist_failed",
                    session_id=session_id,
                    error=str(exc),
                )

        logger.info(
            "background_queue.cancel_all",
            session_id=session_id,
            cancelled=count,
        )
        if count > 0:
            await _emit_queue_event(
                "task.cancel_all",
                {"session_id": session_id, "cancelled": count},
            )
        return count

    # ── Processing ──

    async def _process(self, task: BackgroundTask) -> None:
        """Process a single task with semaphore-bounded concurrency."""
        async with self._semaphore:
            self._active[task.id] = task
            task.status = "running"
            started_at = datetime.now(UTC)

            await self._update_row(
                task.id,
                status="running",
                started_at=started_at,
            )
            await _emit_queue_event(
                "task.started",
                {
                    "task_id": task.id,
                    "session_id": task.session_id,
                    "description": task.description,
                    "started_at": started_at.isoformat(),
                },
            )

            try:
                # When an executor callback is wired the queue runs real
                # work. Otherwise this is a no-op for compatibility with
                # the historical in-memory test surface.
                if self._executor is not None:
                    result = await self._executor(task)
                    if isinstance(result, dict):
                        task.result = result
            except Exception as exc:
                task.status = "failed"
                task.result = {"error": str(exc)}
                finished_at = datetime.now(UTC)
                logger.error(
                    "background_queue.task_failed",
                    task_id=task.id,
                    error=str(exc),
                )
                await self._update_row(
                    task.id,
                    status="failed",
                    finished_at=finished_at,
                    error=str(exc)[:1000],
                    result=task.result,
                )
                await _emit_queue_event(
                    "task.failed",
                    {
                        "task_id": task.id,
                        "session_id": task.session_id,
                        "error": str(exc)[:1000],
                        "finished_at": finished_at.isoformat(),
                    },
                )
                return
            finally:
                self._active.pop(task.id, None)

            # Cancel/fail handled above; if still "running" promote to complete.
            if task.status == "running":
                task.status = "complete"
                finished_at = datetime.now(UTC)
                await self._update_row(
                    task.id,
                    status="complete",
                    finished_at=finished_at,
                    result=task.result,
                )
                await _emit_queue_event(
                    "task.completed",
                    {
                        "task_id": task.id,
                        "session_id": task.session_id,
                        "result": task.result,
                        "finished_at": finished_at.isoformat(),
                    },
                )

            self._history.append(task)

    # ── Restart recovery ──

    async def restore_queue_from_db(
        self, db_session_factory: SessionFactory | None = None,
    ) -> dict[str, int]:
        """Recover queue state from the DB after a restart.

        Re-enqueues rows where ``status='queued'`` and marks
        ``status='running'`` rows as ``failed_due_to_restart`` per
        CLAUDE.md Hard Law #1 (never auto-retry destructive operations).

        Args:
            db_session_factory: Optional override; defaults to the one
                passed at construction time.

        Returns:
            ``{ "restored_queued": N, "marked_failed": M }``.
        """
        factory = db_session_factory or self._db_session_factory
        if factory is None:
            logger.info("background_queue.restore_skipped_no_db")
            return {"restored_queued": 0, "marked_failed": 0}

        restored_queued = 0
        marked_failed = 0
        now = datetime.now(UTC)

        async with factory() as session:
            stmt = select(BackgroundTaskRow).where(
                BackgroundTaskRow.status.in_(["queued", "running"]),
            )
            rows = (await session.execute(stmt)).scalars().all()

            for row in rows:
                if row.status == "queued":
                    task = BackgroundTask(
                        id=str(row.id),
                        tenant_id=str(row.tenant_id) if row.tenant_id else None,
                        session_id=row.session_id,
                        description=row.description,
                        priority=row.priority,
                        status="queued",
                        runtime=row.runtime,
                        cost_usd=row.cost_usd or 0.0,
                        parent_request_id=row.parent_request_id,
                    )
                    await self._queue.put(task)
                    restored_queued += 1
                elif row.status == "running":
                    row.status = "failed_due_to_restart"
                    row.error = "Marked failed: backend restarted while task was running."
                    row.finished_at = now
                    marked_failed += 1
                    logger.warning(
                        "background_queue.task_orphaned_marked_failed",
                        task_id=str(row.id),
                        session_id=row.session_id,
                        tenant_id=str(row.tenant_id) if row.tenant_id else None,
                        priority=row.priority,
                        reason="backend_restart",
                    )

            await session.commit()

        logger.info(
            "background_queue.restore_complete",
            restored_queued=restored_queued,
            marked_failed=marked_failed,
        )
        return {
            "restored_queued": restored_queued,
            "marked_failed": marked_failed,
        }

    # ── Reads ──

    def get_summary(self, session_id: str) -> dict[str, Any]:
        """Get summary of background work for a session.

        Args:
            session_id: Session to summarize.

        Returns:
            Dict with completed, failed, cancelled counts and task list.
        """
        session_tasks = [t for t in self._history if t.session_id == session_id]
        active_tasks = [t for t in self._active.values() if t.session_id == session_id]
        return {
            "completed": len([t for t in session_tasks if t.status == "complete"]),
            "failed": len([t for t in session_tasks if t.status == "failed"]),
            "cancelled": len([t for t in session_tasks if t.status == "cancelled"]),
            "active": len(active_tasks),
            "queued": self._queue.qsize(),
            "tasks": [t.to_dict() for t in session_tasks],
        }

    @property
    def is_running(self) -> bool:
        """Whether the worker loop is active."""
        return self._running

    @property
    def active_count(self) -> int:
        """Number of currently executing tasks."""
        return len(self._active)

    @property
    def queued_count(self) -> int:
        """Number of tasks waiting in queue."""
        return self._queue.qsize()

    @property
    def is_persistent(self) -> bool:
        """Whether queue state is mirrored to the background_tasks table."""
        return self._db_session_factory is not None

    # ── DB helpers ──

    async def _insert_row(self, task: BackgroundTask) -> None:
        """Insert a row matching the in-memory task. Best-effort."""
        if self._db_session_factory is None:
            return

        task_uuid = _to_uuid(task.id)
        if task_uuid is None:
            logger.warning(
                "background_queue.insert_skipped_invalid_id",
                task_id=task.id,
            )
            return

        tenant_uuid = _to_uuid(task.tenant_id)
        if tenant_uuid is None:
            logger.warning(
                "background_queue.insert_skipped_no_tenant",
                task_id=task.id,
            )
            return

        async with self._db_session_factory() as session:
            row = BackgroundTaskRow(
                id=task_uuid,
                tenant_id=tenant_uuid,
                session_id=task.session_id,
                description=task.description[:500],
                status=task.status,
                priority=task.priority,
                queued_at=datetime.now(UTC),
                runtime=task.runtime,
                cost_usd=task.cost_usd,
                parent_request_id=task.parent_request_id,
            )
            session.add(row)
            await session.commit()

    async def _update_row(
        self,
        task_id: str,
        *,
        status: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Update fields on a persistent row. Best-effort, never raises."""
        if self._db_session_factory is None:
            return

        task_uuid = _to_uuid(task_id)
        if task_uuid is None:
            return

        values: dict[str, Any] = {}
        if status is not None:
            values["status"] = status
        if started_at is not None:
            values["started_at"] = started_at
        if finished_at is not None:
            values["finished_at"] = finished_at
        if result is not None:
            values["result"] = result
        if error is not None:
            values["error"] = error[:1000]

        if not values:
            return

        try:
            async with self._db_session_factory() as session:
                await session.execute(
                    update(BackgroundTaskRow)
                    .where(BackgroundTaskRow.id == task_uuid)
                    .values(**values),
                )
                await session.commit()
        except Exception as exc:
            logger.error(
                "background_queue.update_row_failed",
                task_id=task_id,
                error=str(exc),
            )


# ─────────────────────────────────────────────────────────────────────
# Module-level singleton + lifespan helpers
# ─────────────────────────────────────────────────────────────────────

_queue_singleton: BackgroundQueue | None = None
_worker_task: asyncio.Task | None = None


def get_background_queue() -> BackgroundQueue:
    """Return (lazily creating) the process-wide queue singleton.

    The first caller to invoke this without a prior ``init_background_queue``
    gets an in-memory queue. The lifespan-wired init replaces the singleton
    with a DB-backed one.
    """
    global _queue_singleton
    if _queue_singleton is None:
        _queue_singleton = BackgroundQueue()
    return _queue_singleton


def set_background_queue(queue: BackgroundQueue) -> None:
    """Override the process-wide singleton (used by init/tests)."""
    global _queue_singleton
    _queue_singleton = queue


async def init_background_queue(app: Any) -> None:
    """Initialize the persistent background queue at FastAPI startup.

    Wires up:
        1. The DB-backed singleton.
        2. Restore-from-DB recovery.
        3. The worker loop as a long-running asyncio task.
        4. ``app.state.background_queue`` so routers can pull it.

    Safe to call once per process. Subsequent calls are no-ops.
    """
    global _worker_task

    from app.core.database import async_session_factory

    queue = BackgroundQueue(
        max_concurrent=3,
        db_session_factory=async_session_factory,
    )
    set_background_queue(queue)

    try:
        recovery = await queue.restore_queue_from_db(async_session_factory)
        logger.info(
            "background_queue.startup_recovery",
            restored_queued=recovery.get("restored_queued", 0),
            marked_failed=recovery.get("marked_failed", 0),
        )
    except Exception as exc:
        logger.error(
            "background_queue.startup_recovery_failed",
            error=str(exc),
        )

    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(queue.start_worker())

    if hasattr(app, "state"):
        app.state.background_queue = queue


async def shutdown_background_queue(app: Any) -> None:
    """Stop the worker loop and let in-flight tasks settle.

    Called by the FastAPI lifespan teardown. Idempotent.
    """
    global _worker_task

    queue = get_background_queue()
    queue.stop()

    if _worker_task is not None and not _worker_task.done():
        try:
            await asyncio.wait_for(_worker_task, timeout=2.0)
        except (TimeoutError, asyncio.CancelledError):
            _worker_task.cancel()
        except Exception as exc:
            logger.warning(
                "background_queue.shutdown_wait_failed",
                error=str(exc),
            )
        finally:
            _worker_task = None

    if hasattr(app, "state") and getattr(app.state, "background_queue", None) is queue:
        try:
            del app.state.background_queue
        except AttributeError:
            pass

    logger.info("background_queue.shutdown_complete")


async def _emit_queue_event(event_type: str, data: dict[str, Any]) -> None:
    """Publish a lifecycle event to the queue SSE channel.

    Best-effort: missing import path or publisher error never wedges
    the worker loop.
    """
    try:
        from app.core.sse_channels import queue_channel

        await queue_channel.publish(event_type, data)
    except Exception as exc:
        logger.debug(
            "background_queue.event_emit_failed",
            event_type=event_type,
            error=str(exc),
        )
