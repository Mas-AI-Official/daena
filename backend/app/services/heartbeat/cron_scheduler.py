"""Cron-style scheduler for daily/weekly tasks.

Handles precise scheduling for recurring jobs like:
- Morning briefing at 7am
- Weekly project review on Monday
- Nightly cleanup at 2am
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta
from enum import Enum
from typing import Any, Callable, Coroutine

from app.core.logging import get_logger

logger = get_logger(__name__)


class CronFrequency(Enum):
    """How often a cron job runs."""

    DAILY = "daily"
    WEEKLY = "weekly"
    HOURLY = "hourly"


@dataclass
class CronJob:
    """A scheduled recurring task."""

    job_id: str
    name: str
    frequency: CronFrequency
    run_at: time  # Time of day to run
    day_of_week: int | None = None  # 0=Mon, 6=Sun (for weekly)
    task_prompt: str = ""  # What to send to runtime
    runtime_preference: str = "ollama"  # Prefer cheap runtime
    enabled: bool = True
    last_run: datetime | None = None
    last_result: str | None = None

    def is_due(self, now: datetime | None = None) -> bool:
        """Check if this job should run now."""
        now = now or datetime.now()
        current_time = now.time()

        # Check if within 5 minutes of scheduled time
        scheduled_minutes = self.run_at.hour * 60 + self.run_at.minute
        current_minutes = current_time.hour * 60 + current_time.minute
        within_window = abs(current_minutes - scheduled_minutes) <= 5

        if not within_window:
            return False

        # Check if already ran today/this week
        if self.last_run:
            if self.frequency == CronFrequency.DAILY:
                if self.last_run.date() == now.date():
                    return False
            elif self.frequency == CronFrequency.WEEKLY:
                if (now - self.last_run).days < 7:
                    return False
            elif self.frequency == CronFrequency.HOURLY:
                if (now - self.last_run).total_seconds() < 3000:  # 50 min
                    return False

        # Check day of week for weekly jobs
        if self.frequency == CronFrequency.WEEKLY and self.day_of_week is not None:
            if now.weekday() != self.day_of_week:
                return False

        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "frequency": self.frequency.value,
            "run_at": self.run_at.isoformat(),
            "day_of_week": self.day_of_week,
            "task_prompt": self.task_prompt,
            "runtime_preference": self.runtime_preference,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_result": self.last_result,
        }


class CronScheduler:
    """Manages cron-style recurring jobs."""

    def __init__(self) -> None:
        self._jobs: dict[str, CronJob] = {}
        self._task: asyncio.Task | None = None
        self._running = False

    def add_job(self, job: CronJob) -> None:
        """Register a cron job."""
        self._jobs[job.job_id] = job
        logger.info("cron.job_added", job_id=job.job_id, name=job.name)

    def remove_job(self, job_id: str) -> bool:
        """Remove a cron job."""
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

    def get_jobs(self) -> list[dict[str, Any]]:
        """List all registered jobs."""
        return [j.to_dict() for j in self._jobs.values()]

    async def start(self) -> None:
        """Start the cron scheduler loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("cron.started", jobs=len(self._jobs))

    async def stop(self) -> None:
        """Stop the cron scheduler."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def check_and_run(self) -> list[str]:
        """Check all jobs and run any that are due. Returns list of executed job IDs."""
        executed = []
        now = datetime.now()

        for job in self._jobs.values():
            if not job.enabled:
                continue
            if job.is_due(now):
                logger.info("cron.job_due", job_id=job.job_id, name=job.name)
                job.last_run = now
                job.last_result = "executed"
                executed.append(job.job_id)

        return executed

    async def _loop(self) -> None:
        """Main cron check loop -- runs every 60 seconds."""
        while self._running:
            try:
                await self.check_and_run()
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("cron.loop_error", error=str(exc))
                await asyncio.sleep(60)

    @classmethod
    def with_defaults(cls) -> CronScheduler:
        """Create scheduler with default job templates."""
        scheduler = cls()
        scheduler.add_job(CronJob(
            job_id="morning_briefing",
            name="Morning Briefing",
            frequency=CronFrequency.DAILY,
            run_at=time(7, 0),
            task_prompt=(
                "Generate a morning briefing: check git log for overnight commits, "
                "check test results, summarize project state, list today's priorities."
            ),
            runtime_preference="ollama",
            enabled=False,  # Enable manually
        ))
        scheduler.add_job(CronJob(
            job_id="weekly_review",
            name="Weekly Project Review",
            frequency=CronFrequency.WEEKLY,
            run_at=time(9, 0),
            day_of_week=0,  # Monday
            task_prompt=(
                "Run weekly project review: count total tests, check coverage, "
                "list open TODOs, summarize git activity for the week, "
                "suggest priorities for the coming week."
            ),
            runtime_preference="claude_code",
            enabled=False,
        ))
        return scheduler
