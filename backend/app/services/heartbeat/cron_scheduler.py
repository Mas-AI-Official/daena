"""Cron-style scheduler for daily/weekly tasks.

Handles precise scheduling for recurring jobs like:
- Morning briefing at 7am
- Weekly project review on Monday
- Nightly cleanup at 2am

Honesty fix (2026-04-29): previously ``check_and_run`` set
``job.last_result = "executed"`` without invoking any runtime, so
operators saw "executed" while nothing actually ran. The scheduler
now consults ``RuntimeRegistry``, streams output through a real
adapter, persists every attempt as a ``CronRun`` row, enforces a
per-run cost cap via ``CostEstimator``, and reports the truthful
summary back into the legacy ``job.last_result`` slot for backward
compatibility with the existing UI.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Hard cap (USD) on the estimated cost of a single cron run. Cron jobs
# are background, system-initiated work; without an upper bound a bad
# prompt template plus a high-cost adapter could quietly burn the
# operator's monthly budget overnight.
DEFAULT_CRON_COST_CAP_USD = 0.50

# Soft hint for the cost estimator: how many tokens a cron task tends
# to use end-to-end. Tuned for "morning briefing" / "weekly review"
# style prompts; adapters that need more headroom should override via
# their own per-task estimates downstream.
DEFAULT_CRON_TOKEN_BUDGET = 2000

# Wall-clock cap (seconds) on a single cron run. The scheduler awaits
# the adapter's stream inline; without a deadline one hung adapter
# wedges every subsequent cron job forever. On timeout the run is
# finalized with an error and the loop moves on.
DEFAULT_CRON_JOB_TIMEOUT_S = 120.0

# Ordered preference for a LOCAL fallback runtime when a cron job's
# configured ``runtime_preference`` is not registered. Cron work is
# background + cost-capped, so we bias toward the cheapest local
# runtimes first (vllm before the deprecated ollama) and only then
# fall through to whatever else the registry reports online. Mirrors
# the runtime registry's own local-fallback order so behaviour is
# consistent whichever path resolves the runtime.
_LOCAL_FALLBACK_ORDER = ("vllm", "ollama")


def _pick_online_fallback(registry: Any, *, exclude: str) -> tuple[str | None, Any]:
    """Pick the first ONLINE runtime to stand in for an unregistered
    preference.

    Returns ``(runtime_id, adapter)`` for the first online runtime whose
    adapter resolves, biased by ``_LOCAL_FALLBACK_ORDER`` then any other
    online runtime the registry reports. Returns ``(None, None)`` when
    nothing usable is online. Never raises -- a flaky registry must not
    wedge the scheduler loop.
    """
    try:
        online = list(getattr(registry, "online_ids", None) or [])
    except Exception:
        online = []
    # Local runtimes first (in preferred order), then any other online
    # runtime the registry reports, so the cheapest local option wins.
    ordered = [rid for rid in _LOCAL_FALLBACK_ORDER if rid in online]
    ordered += [rid for rid in online if rid not in _LOCAL_FALLBACK_ORDER]
    for rid in ordered:
        if rid == exclude:
            continue
        try:
            adapter = registry.get_adapter(rid)
        except Exception:
            adapter = None
        if adapter is not None:
            return rid, adapter
    return None, None


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
    max_cost_usd: float = DEFAULT_CRON_COST_CAP_USD
    max_runtime_s: float = DEFAULT_CRON_JOB_TIMEOUT_S

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
            "max_cost_usd": self.max_cost_usd,
            "max_runtime_s": self.max_runtime_s,
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
        """Check all jobs and run any that are due.

        Returns the list of job IDs whose runtime invocation reached
        the registry (regardless of whether the runtime ultimately
        succeeded). A failure inside a single job NEVER breaks the
        scheduler loop: the error is captured on the ``CronRun`` row
        and surfaced to the legacy ``job.last_result`` slot, then we
        move on to the next due job.
        """
        executed: list[str] = []
        now = datetime.now()

        for job in self._jobs.values():
            if not job.enabled:
                continue
            if not job.is_due(now):
                continue

            logger.info("cron.job_due", job_id=job.job_id, name=job.name)
            # Append on dispatch -- even runtime failures count as "we
            # tried to run this job," which is what the operator and
            # the upstream tests are asserting on.
            executed.append(job.job_id)
            try:
                await self._execute_job(job, now)
            except Exception as exc:
                # Final safety net: any unexpected error here is logged
                # and absorbed so a single broken job cannot wedge the
                # whole scheduler. Real runtime errors are already
                # captured inside ``_execute_job`` and persisted to the
                # ``CronRun`` row; this branch only fires for truly
                # unexpected failures (DB unavailable at acquire time,
                # serialization bugs, etc.).
                logger.error(
                    "cron.execute_safety_net",
                    job_id=job.job_id,
                    error=str(exc),
                    error_type=type(exc).__name__,
                )
                job.last_run = now
                job.last_result = f"error: {exc}"[:500]

        return executed

    async def _execute_job(self, job: CronJob, now: datetime) -> None:
        """Run one due job through the real runtime registry.

        Inserts a ``CronRun`` row before invoking the runtime,
        accumulates streamed output, applies a hard cost cap via
        ``CostEstimator``, then updates the row with the final state
        (success or error) inside a fresh async session.
        """
        # Local imports keep this module importable in environments
        # that do not have the full app stack on the import path
        # (e.g. unit tests that exercise scheduling logic only).
        from app.core.database import async_session_factory
        from app.models.cron_run import CronRun
        from app.services.runtimes.cost_estimator import CostEstimator
        from app.services.runtimes.registry import RuntimeRegistry

        registry = _get_runtime_registry()
        cost_estimator = _get_cost_estimator()
        run_id = uuid.uuid4()
        # Best-effort lifecycle event so SSE subscribers see the run
        # start in real time. Channel publish never raises; if the
        # import path is missing (unit tests with no app stack) we
        # silently skip.
        await _emit_cron_event(
            "cron.run_started",
            {
                "job_id": job.job_id,
                "run_id": str(run_id),
                "name": job.name,
                "runtime": job.runtime_preference,
                "started_at": now.isoformat(),
            },
        )

        # Pre-insert the CronRun row so even a hard crash leaves a
        # forensic trail of "started but never finished".
        try:
            async with async_session_factory() as session:
                row = CronRun(
                    id=run_id,
                    job_id=job.job_id,
                    runtime=job.runtime_preference,
                    started_at=now,
                )
                session.add(row)
                await session.commit()
        except Exception as exc:
            # If the audit row cannot be written we still log + flip
            # last_result so the operator sees the truth in the UI.
            logger.error(
                "cron.audit_row_insert_failed",
                job_id=job.job_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            job.last_run = now
            job.last_result = f"audit insert failed: {exc}"[:500]
            return

        # Hard cost cap. Reject before invoking the runtime if the
        # estimated cost exceeds the per-run cap.
        estimate = cost_estimator.estimate(
            runtime_id=job.runtime_preference,
            estimated_tokens=DEFAULT_CRON_TOKEN_BUDGET,
        )
        if estimate.estimated_cost_usd > job.max_cost_usd:
            error = (
                f"cost cap exceeded: estimated ${estimate.estimated_cost_usd:.4f} "
                f"> cap ${job.max_cost_usd:.4f} for runtime {job.runtime_preference}"
            )
            logger.warning(
                "cron.cost_cap_exceeded",
                job_id=job.job_id,
                runtime=job.runtime_preference,
                estimated_cost_usd=estimate.estimated_cost_usd,
                cap_usd=job.max_cost_usd,
            )
            await self._finalize_run(
                run_id=run_id,
                started_at=now,
                summary=None,
                full_text=None,
                error=error,
                cost_usd=0.0,
                tokens_in=0,
                tokens_out=0,
            )
            job.last_run = now
            job.last_result = error[:500]
            return

        # Resolve the adapter. Prefer the job's configured runtime; if it
        # is not registered, fall back to the first ONLINE runtime instead
        # of dead-ending -- the whole point of the registry is that a
        # working runtime may be standing right there. We track the ACTUAL
        # runtime used in ``effective_runtime`` so the audit row, cost
        # accounting, and adapter context never lie (Rule 17 / ADR-001).
        effective_runtime = job.runtime_preference
        adapter = None
        if registry is not None:
            adapter = registry.get_adapter(job.runtime_preference)
            if adapter is None:
                fallback_runtime, fallback_adapter = _pick_online_fallback(
                    registry, exclude=job.runtime_preference,
                )
                if fallback_adapter is not None:
                    logger.info(
                        "cron.runtime_substituted",
                        job_id=job.job_id,
                        requested=job.runtime_preference,
                        substituted=fallback_runtime,
                    )
                    effective_runtime = fallback_runtime
                    adapter = fallback_adapter
        if adapter is None:
            error = (
                f"no runtime available: preferred "
                f"'{job.runtime_preference}' not registered and no "
                "online runtime to fall back to"
            )
            logger.warning(
                "cron.no_runtime_available",
                job_id=job.job_id,
                runtime=job.runtime_preference,
            )
            await self._finalize_run(
                run_id=run_id,
                started_at=now,
                summary=None,
                full_text=None,
                error=error,
                cost_usd=0.0,
                tokens_in=0,
                tokens_out=0,
            )
            job.last_run = now
            job.last_result = error[:500]
            return

        # Execute. Cron is system-initiated, so tenant_id is "system".
        context: dict[str, Any] = {
            "task_prompt": job.task_prompt,
            "runtime_preference": effective_runtime,
            "tenant_id": "system",
            "source": "cron_scheduler",
            "job_id": job.job_id,
        }

        chunks: list[str] = []

        async def _consume() -> None:
            async for chunk in adapter.execute(
                task=job.task_prompt, context=context,
            ):
                chunks.append(chunk)

        try:
            await asyncio.wait_for(_consume(), timeout=job.max_runtime_s)
        except asyncio.TimeoutError:
            # Must precede the generic handler: on Python 3.11+
            # asyncio.TimeoutError IS builtins.TimeoutError, which is
            # an Exception subclass.
            error = (
                f"timeout: job exceeded max_runtime_s="
                f"{job.max_runtime_s}s"
            )
            logger.error(
                "cron.runtime_timeout",
                job_id=job.job_id,
                runtime=job.runtime_preference,
                max_runtime_s=job.max_runtime_s,
            )
            await self._finalize_run(
                run_id=run_id,
                started_at=now,
                summary=None,
                full_text="\n".join(chunks) or None,
                error=error,
                cost_usd=0.0,
                tokens_in=0,
                tokens_out=0,
                runtime=effective_runtime,
            )
            job.last_run = now
            job.last_result = error[:500]
            return
        except Exception as exc:
            error = f"runtime error: {exc}"
            logger.error(
                "cron.runtime_error",
                job_id=job.job_id,
                runtime=job.runtime_preference,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            await self._finalize_run(
                run_id=run_id,
                started_at=now,
                summary=None,
                full_text="\n".join(chunks) or None,
                error=error,
                cost_usd=0.0,
                tokens_in=0,
                tokens_out=0,
                runtime=effective_runtime,
            )
            job.last_run = now
            job.last_result = error[:500]
            return

        full_text = "\n".join(chunks)
        summary = full_text[:500] if full_text else "no output"

        # Approximate token accounting: input ~= prompt length, output
        # ~= total streamed text. The CostEstimator's pricing table
        # turns those into a cost figure consistent with the rest of
        # the platform.
        tokens_in = max(len(job.task_prompt) // 4, 0)
        tokens_out = max(len(full_text) // 4, 0)
        cost_usd = cost_estimator.record_actual(
            session_id=str(run_id),
            runtime_id=effective_runtime,
            actual_input_tokens=tokens_in,
            actual_output_tokens=tokens_out,
        )

        await self._finalize_run(
            run_id=run_id,
            started_at=now,
            summary=summary,
            full_text=full_text or None,
            error=None,
            cost_usd=cost_usd,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            runtime=effective_runtime,
        )

        job.last_run = now
        job.last_result = summary or "completed"

    async def _finalize_run(
        self,
        *,
        run_id: uuid.UUID,
        started_at: datetime,
        summary: str | None,
        full_text: str | None,
        error: str | None,
        cost_usd: float,
        tokens_in: int,
        tokens_out: int,
        runtime: str | None = None,
    ) -> None:
        """Update the pre-inserted CronRun row with the final state.

        Wrapped in try/except so a DB hiccup at finalize time does not
        leak back into the scheduler loop. The forensic row will simply
        stay "started but no finish", which is the correct signal.

        ``runtime`` corrects the pre-inserted ``row.runtime`` to the
        ACTUAL runtime that ran when the scheduler substituted an online
        fallback for an unregistered preference. Left ``None`` (the bail
        paths) the row keeps its originally-intended runtime.
        """
        from app.core.database import async_session_factory
        from app.models.cron_run import CronRun
        from sqlalchemy import select

        finished_at = datetime.now()
        duration_ms = max(
            int((finished_at - started_at).total_seconds() * 1000),
            0,
        )

        try:
            async with async_session_factory() as session:
                stmt = select(CronRun).where(CronRun.id == run_id)
                result = await session.execute(stmt)
                row = result.scalar_one_or_none()
                if row is None:
                    logger.warning(
                        "cron.finalize_row_missing",
                        run_id=str(run_id),
                    )
                    return
                row.finished_at = finished_at
                row.duration_ms = duration_ms
                row.summary = summary
                row.full_text = full_text
                row.error = error
                row.cost_usd = cost_usd
                row.tokens_in = tokens_in
                row.tokens_out = tokens_out
                if runtime is not None:
                    row.runtime = runtime
                await session.commit()
        except Exception as exc:
            logger.error(
                "cron.finalize_failed",
                run_id=str(run_id),
                error=str(exc),
                error_type=type(exc).__name__,
            )

        # Lifecycle event AFTER persistence so subscribers only see
        # finalized runs. Failures publish the error path; successes
        # publish the summary + cost.
        if error is not None:
            await _emit_cron_event(
                "cron.run_failed",
                {
                    "run_id": str(run_id),
                    "error": error,
                    "duration_ms": duration_ms,
                    "finished_at": finished_at.isoformat(),
                },
            )
        else:
            await _emit_cron_event(
                "cron.run_completed",
                {
                    "run_id": str(run_id),
                    "summary": summary,
                    "cost_usd": cost_usd,
                    "duration_ms": duration_ms,
                    "tokens_in": tokens_in,
                    "tokens_out": tokens_out,
                    "finished_at": finished_at.isoformat(),
                },
            )

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
        """Create scheduler with default job templates.

        Defaults are ``enabled=True`` so the scheduler runs out of the
        box. Operators can opt out cleanly by setting the env var
        ``DAENA_CRON_DEFAULT_DISABLED=true`` before startup, in which
        case the seeded jobs are present but disabled.
        """
        scheduler = cls()
        defaults_disabled = (
            os.environ.get("DAENA_CRON_DEFAULT_DISABLED", "").lower() == "true"
        )
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
            enabled=not defaults_disabled,
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
            enabled=not defaults_disabled,
        ))
        return scheduler


# ── Module-level singletons + lifecycle hooks ──────────────────────────

_cron_scheduler_instance: CronScheduler | None = None
_runtime_registry_resolver = None
_cost_estimator_singleton = None


def get_cron_scheduler() -> CronScheduler:
    """Return the process-wide scheduler, creating it on first access."""
    global _cron_scheduler_instance
    if _cron_scheduler_instance is None:
        _cron_scheduler_instance = CronScheduler.with_defaults()
    return _cron_scheduler_instance


def reset_cron_scheduler_singleton() -> None:
    """Test-only helper: clear the cached singleton."""
    global _cron_scheduler_instance
    _cron_scheduler_instance = None


def set_runtime_registry_resolver(resolver) -> None:  # noqa: ANN001
    """Wire the scheduler to a callable returning the live RuntimeRegistry.

    main.py owns the registry singleton; rather than import it (which
    would create a circular dependency from scheduler -> chat services
    -> back to heartbeat), main.py calls this once during lifespan
    startup with a closure that yields the live registry. Tests can
    pass a stub resolver returning a fake registry.
    """
    global _runtime_registry_resolver
    _runtime_registry_resolver = resolver


def _get_runtime_registry():  # noqa: ANN202
    """Resolve the live RuntimeRegistry, or None if unwired (tests)."""
    if _runtime_registry_resolver is None:
        return None
    try:
        return _runtime_registry_resolver()
    except Exception as exc:
        logger.warning(
            "cron.registry_resolver_failed",
            error=str(exc),
            error_type=type(exc).__name__,
        )
        return None


def _get_cost_estimator():  # noqa: ANN202
    """Lazy singleton for the cost estimator (cheap to construct)."""
    global _cost_estimator_singleton
    if _cost_estimator_singleton is None:
        from app.services.runtimes.cost_estimator import CostEstimator

        _cost_estimator_singleton = CostEstimator()
    return _cost_estimator_singleton


async def start_cron_scheduler() -> None:
    """Start the process-wide cron scheduler. Called once from main.py.lifespan."""
    scheduler = get_cron_scheduler()
    await scheduler.start()


async def stop_cron_scheduler() -> None:
    """Stop the process-wide cron scheduler. Called once from main.py.lifespan."""
    if _cron_scheduler_instance is not None:
        await _cron_scheduler_instance.stop()


async def _emit_cron_event(event_type: str, data: dict[str, Any]) -> None:
    """Publish a lifecycle event to the cron SSE channel.

    Wrapped in a best-effort try so a missing import path or a
    publisher error never wedges the scheduler. Real subscribers see
    the event; absent subscribers no-op.
    """
    try:
        from app.core.sse_channels import cron_channel

        await cron_channel.publish(event_type, data)
    except Exception as exc:
        logger.debug(
            "cron.event_emit_failed",
            event_type=event_type,
            error=str(exc),
        )
