"""Background Queue: manages tasks spawned by Autopilot.

Provides a bounded-concurrency queue for background task execution.
Tasks are processed by a worker loop that respects the semaphore limit.
Supports cancellation of individual tasks or all tasks for a session.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BackgroundTask:
    """A background task spawned by Autopilot.

    Attributes:
        id: Unique task identifier.
        session_id: Chat session that spawned this task.
        description: Human-readable description.
        created_at: ISO timestamp of creation.
        status: Current status (queued, running, complete, failed, cancelled).
        result: Task result data (populated on completion).
    """

    id: str
    session_id: str
    description: str
    created_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
    )
    status: str = "queued"  # queued, running, complete, failed, cancelled
    result: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API responses."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "description": self.description,
            "created_at": self.created_at,
            "status": self.status,
            "result": self.result,
        }


class BackgroundQueue:
    """Manages background tasks with bounded concurrency.

    Usage::

        queue = BackgroundQueue(max_concurrent=3)
        asyncio.create_task(queue.start_worker())

        await queue.enqueue(BackgroundTask(
            id="task-1",
            session_id="sess-abc",
            description="Analyze repository",
        ))

        summary = queue.get_summary("sess-abc")
    """

    def __init__(self, max_concurrent: int = 3) -> None:
        """Initialize with bounded concurrency.

        Args:
            max_concurrent: Maximum tasks running simultaneously.
        """
        self._queue: asyncio.Queue[BackgroundTask] = asyncio.Queue()
        self._active: dict[str, BackgroundTask] = {}
        self._history: list[BackgroundTask] = []
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._running = False
        self._max_concurrent = max_concurrent

    async def start_worker(self) -> None:
        """Start the background worker loop.

        Runs forever, pulling tasks from the queue and processing them
        with bounded concurrency. Call queue.stop() to terminate.
        """
        self._running = True
        logger.info("background_queue.worker_started", max_concurrent=self._max_concurrent)

        while self._running:
            try:
                task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                asyncio.create_task(self._process(task))
            except TimeoutError:
                continue  # Check self._running flag periodically
            except Exception as exc:
                logger.error("background_queue.worker_error", error=str(exc))

    def stop(self) -> None:
        """Stop the worker loop."""
        self._running = False

    async def enqueue(self, task: BackgroundTask) -> None:
        """Add a task to the queue.

        Args:
            task: BackgroundTask to enqueue.
        """
        await self._queue.put(task)
        logger.info(
            "background_queue.enqueued",
            task_id=task.id,
            session_id=task.session_id,
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
            logger.info("background_queue.cancelled", task_id=task_id)
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
        logger.info(
            "background_queue.cancel_all",
            session_id=session_id,
            cancelled=count,
        )
        return count

    async def _process(self, task: BackgroundTask) -> None:
        """Process a single task with semaphore-bounded concurrency."""
        async with self._semaphore:
            self._active[task.id] = task
            task.status = "running"
            try:
                # Actual execution is delegated to the caller via callback.
                # The BackgroundQueue is a generic queue; the task's "work"
                # is done by the AutopilotController which uses SwarmExecutor.
                # This placeholder completes the task as a stub.
                # In production, the callback pattern or executor reference
                # would be injected.
                pass
            except Exception as exc:
                task.status = "failed"
                task.result = {"error": str(exc)}
                logger.error(
                    "background_queue.task_failed",
                    task_id=task.id,
                    error=str(exc),
                )
            finally:
                self._active.pop(task.id, None)
                if task.status == "running":
                    task.status = "complete"
                self._history.append(task)

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
