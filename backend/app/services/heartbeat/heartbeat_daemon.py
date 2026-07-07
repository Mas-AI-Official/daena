"""Heartbeat daemon -- background async loop.

Runs periodic checks at configurable intervals. Each check goes
through the governance pipeline. Actions are auto-executed or
queued based on autopilot level and criticality.

Usage:
    daemon = HeartbeatDaemon.get_instance()
    await daemon.start()
    # ... later
    await daemon.pause()
    await daemon.resume()
    await daemon.stop()
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.heartbeat.heartbeat_checks import (
    ActionPriority,
    HeartbeatCheckResult,
    check_autonomous_work,
    check_department_workflows,
    check_file,
    check_git_status,
    check_runtime_health,
    check_test_suite,
    check_github_issues,
    check_failed_tasks,
    check_memory_quarantine,
    check_ollama_health,
    check_ollama_model_updates,
    generate_daily_report,
)
from app.services.heartbeat.heartbeat_config import (
    AutopilotLevel,
    CheckType,
    HeartbeatConfig,
    HeartbeatState,
)

logger = get_logger(__name__)

CHECK_TIMEOUT_SECONDS: dict[CheckType, float] = {
    CheckType.GIT_STATUS: 4.0,
    CheckType.TEST_SUITE: 6.0,
    CheckType.GITHUB_ISSUES: 6.0,
    CheckType.OLLAMA_HEALTH: 5.0,
    CheckType.OLLAMA_MODEL_UPDATES: 6.0,
    CheckType.MEMORY_QUARANTINE: 15.0,  # DB pass over up to 10 tenants x 50 entries
}
DEFAULT_CHECK_TIMEOUT_SECONDS = 8.0


@dataclass
class HeartbeatCycleLog:
    """Record of a single heartbeat cycle."""

    cycle_id: int
    started_at: datetime
    completed_at: datetime | None = None
    results: list[HeartbeatCheckResult] = field(default_factory=list)
    actions_taken: list[dict[str, Any]] = field(default_factory=list)
    actions_queued: list[dict[str, Any]] = field(default_factory=list)
    total_cost_usd: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "check_count": len(self.results),
            "actions_taken": len(self.actions_taken),
            "actions_queued": len(self.actions_queued),
            "total_cost_usd": self.total_cost_usd,
            "error": self.error,
            "results": [
                {
                    "check_type": r.check_type,
                    "status": r.status,
                    "summary": r.summary,
                    "action_count": len(r.actions),
                    "duration_ms": r.duration_ms,
                }
                for r in self.results
            ],
        }


class HeartbeatDaemon:
    """Singleton background daemon that runs periodic checks."""

    _instance: HeartbeatDaemon | None = None

    def __init__(self) -> None:
        self.config = HeartbeatConfig.default()
        self._task: asyncio.Task | None = None
        self._cycle_count = 0
        self._history: list[HeartbeatCycleLog] = []
        self._max_history = 100
        self._last_check: datetime | None = None
        self._next_check: datetime | None = None

    @classmethod
    def get_instance(cls) -> HeartbeatDaemon:
        """Get or create the singleton daemon."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def start(self) -> None:
        """Start the heartbeat loop.

        Idempotent: if a loop task is already alive (RUNNING or PAUSED),
        returns without creating a duplicate. The previous check guarded
        only on RUNNING state, which left a hole where calling start()
        on a PAUSED daemon would overwrite ``self._task`` and orphan the
        original loop. PR-HB-DAEMON-WIRE (2026-05-02) tightened the
        guard so a repeat lifespan boot or stray operator call cannot
        spawn a second loop.
        """
        if self._task is not None and not self._task.done():
            logger.warning(
                "heartbeat.already_running",
                state=self.config.state.value,
            )
            return

        # S-02: hydrate persisted operator config (interval / active-hours /
        # autopilot / cost-caps / per-check toggles) from the DB before the
        # loop spins up, so a restart honors the last /configure call instead
        # of silently reverting to defaults (ADR-001 hydrate-from-DB).
        await self.hydrate_from_db()

        self.config.state = HeartbeatState.RUNNING
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "heartbeat.started",
            interval=self.config.interval_minutes,
            autopilot=self.config.autopilot_level.value,
        )

    async def pause(self) -> None:
        """Pause the heartbeat (keeps task alive, skips execution)."""
        self.config.state = HeartbeatState.PAUSED
        logger.info("heartbeat.paused")

    async def resume(self) -> None:
        """Resume a paused heartbeat."""
        if self.config.state != HeartbeatState.PAUSED:
            logger.warning("heartbeat.not_paused")
            return
        self.config.state = HeartbeatState.RUNNING
        logger.info("heartbeat.resumed")

    async def stop(self) -> None:
        """Stop the heartbeat loop entirely."""
        self.config.state = HeartbeatState.STOPPED
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("heartbeat.stopped")

    async def run_once(self) -> HeartbeatCycleLog:
        """Run a single heartbeat cycle (for testing or manual trigger)."""
        return await self._run_cycle()

    def get_status(self) -> dict[str, Any]:
        """Get current daemon status."""
        return {
            "state": self.config.state.value,
            "interval_minutes": self.config.interval_minutes,
            "autopilot_level": self.config.autopilot_level.value,
            "cycle_count": self._cycle_count,
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "next_check": self._next_check.isoformat() if self._next_check else None,
            "daily_cost_usd": self.config.daily_cost_accumulated,
            "active_hours": f"{self.config.active_start.isoformat()}-{self.config.active_end.isoformat()}",
            "checks_enabled": [
                c.check_type.value for c in self.config.checks if c.enabled
            ],
        }

    def get_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent heartbeat cycle history."""
        return [h.to_dict() for h in self._history[-limit:]]

    def configure(self, updates: dict[str, Any]) -> None:
        """Update configuration from API."""
        if "interval_minutes" in updates:
            self.config.interval_minutes = max(1, int(updates["interval_minutes"]))
        if "autopilot_level" in updates:
            self.config.autopilot_level = AutopilotLevel(updates["autopilot_level"])
        if "active_start" in updates:
            from datetime import time

            parts = updates["active_start"].split(":")
            self.config.active_start = time(int(parts[0]), int(parts[1]))
        if "active_end" in updates:
            from datetime import time

            parts = updates["active_end"].split(":")
            self.config.active_end = time(int(parts[0]), int(parts[1]))
        if "reflection_enabled" in updates:
            self.config.reflection_enabled = bool(updates["reflection_enabled"])
        if "max_cost_per_cycle_usd" in updates:
            self.config.max_cost_per_cycle_usd = float(updates["max_cost_per_cycle_usd"])
        if "max_cost_per_day_usd" in updates:
            self.config.max_cost_per_day_usd = float(updates["max_cost_per_day_usd"])
        if "checks" in updates and isinstance(updates["checks"], dict):
            enabled_by_type = {
                str(check_type): bool(enabled)
                for check_type, enabled in updates["checks"].items()
            }
            for check_cfg in self.config.checks:
                key = check_cfg.check_type.value
                if key in enabled_by_type:
                    check_cfg.enabled = enabled_by_type[key]

        logger.info("heartbeat.configured", updates=updates)

    async def hydrate_from_db(self) -> None:
        """Load the persisted operator config and apply it (S-02).

        Fail-open: any DB error leaves the in-process defaults untouched and
        is logged at debug, so a storage hiccup never blocks daemon start.
        Reuses ``configure()`` so there is no second apply path to drift.
        """
        try:
            from app.services.heartbeat.heartbeat_config_store import load_persisted

            stored = await load_persisted()
            if stored:
                self.configure(stored)
                logger.info("heartbeat.hydrated_from_db", keys=sorted(stored.keys()))
        except Exception:
            logger.debug("heartbeat.hydrate_failed", exc_info=True)

    # ── Internal ──

    async def _loop(self) -> None:
        """Main heartbeat loop."""
        while self.config.state != HeartbeatState.STOPPED:
            try:
                if self.config.state == HeartbeatState.RUNNING:
                    if self.config.is_within_active_hours():
                        await self._run_cycle()
                    else:
                        logger.debug("heartbeat.outside_active_hours")

                # Calculate next check time
                interval = self.config.interval_minutes * 60
                self._next_check = datetime.utcnow().__class__.utcnow()
                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("heartbeat.loop_error", error=str(exc))
                await asyncio.sleep(60)  # Back off on error

    async def _run_cycle(self) -> HeartbeatCycleLog:
        """Execute one heartbeat cycle."""
        self._cycle_count += 1
        cycle = HeartbeatCycleLog(
            cycle_id=self._cycle_count,
            started_at=datetime.utcnow(),
        )

        logger.info("heartbeat.cycle_start", cycle_id=self._cycle_count)

        # Cost guard: check daily limit
        if self.config.daily_cost_accumulated >= self.config.max_cost_per_day_usd:
            cycle.error = f"Daily cost limit reached: ${self.config.daily_cost_accumulated:.2f}"
            cycle.completed_at = datetime.utcnow()
            self._history.append(cycle)
            logger.warning("heartbeat.daily_limit", cost=self.config.daily_cost_accumulated)
            return cycle

        # Run enabled checks
        for check_cfg in self.config.checks:
            if not check_cfg.enabled:
                continue

            timeout_seconds = CHECK_TIMEOUT_SECONDS.get(
                check_cfg.check_type,
                DEFAULT_CHECK_TIMEOUT_SECONDS,
            )
            try:
                result = await asyncio.wait_for(
                    self._run_check(check_cfg.check_type, check_cfg),
                    timeout=timeout_seconds,
                )
                cycle.results.append(result)
                cycle.total_cost_usd += result.cost_usd

                # Process suggested actions
                for action in result.actions:
                    should_execute = self._should_auto_execute(action.priority)
                    if should_execute:
                        cycle.actions_taken.append({
                            "description": action.description,
                            "priority": action.priority.value,
                            "auto_executed": True,
                        })
                    else:
                        cycle.actions_queued.append({
                            "description": action.description,
                            "priority": action.priority.value,
                            "queued_for_approval": True,
                        })

            except asyncio.TimeoutError:
                result = HeartbeatCheckResult(
                    check_type=check_cfg.check_type.value,
                    status="error",
                    summary=f"Heartbeat check timed out after {timeout_seconds:g} seconds",
                    cost_usd=0.0,
                )
                cycle.results.append(result)
                logger.warning(
                    "heartbeat.check_timeout",
                    check_type=check_cfg.check_type.value,
                    timeout_seconds=timeout_seconds,
                )
            except Exception as exc:
                logger.warning(
                    "heartbeat.check_failed",
                    check_type=check_cfg.check_type.value,
                    error=str(exc),
                )
                cycle.results.append(
                    HeartbeatCheckResult(
                        check_type=check_cfg.check_type.value,
                        status="error",
                        summary=f"Heartbeat check failed: {exc}",
                        cost_usd=0.0,
                    )
                )

        # Run reflection if enabled
        if self.config.reflection_enabled and cycle.results:
            cycle.results.append(await self._reflect(cycle))

        cycle.completed_at = datetime.utcnow()
        self.config.daily_cost_accumulated += cycle.total_cost_usd
        self._last_check = cycle.completed_at
        self._history.append(cycle)

        # Trim history
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        logger.info(
            "heartbeat.cycle_complete",
            cycle_id=self._cycle_count,
            checks=len(cycle.results),
            actions_taken=len(cycle.actions_taken),
            actions_queued=len(cycle.actions_queued),
            cost_usd=cycle.total_cost_usd,
            duration_ms=int(
                (cycle.completed_at - cycle.started_at).total_seconds() * 1000
            ),
        )

        return cycle

    async def _run_check(self, check_type: CheckType, check_cfg: Any) -> HeartbeatCheckResult:
        """Dispatch a check to the appropriate function."""
        if check_type == CheckType.RUNTIME_HEALTH:
            return await check_runtime_health()
        elif check_type in (CheckType.INBOX, CheckType.TASKS, CheckType.PROJECT_STATE):
            if check_cfg.file_path:
                return await check_file(check_cfg.file_path, check_type.value)
            return HeartbeatCheckResult(
                check_type=check_type.value,
                status="warning",
                summary="No file path configured",
            )
        elif check_type == CheckType.GIT_STATUS:
            return await check_git_status()
        elif check_type == CheckType.TEST_SUITE:
            return await check_test_suite(backend_path=str(Path(__file__).resolve().parents[3]))
        elif check_type == CheckType.GITHUB_ISSUES:
            return await check_github_issues(
                gh_command=check_cfg.command if check_cfg.command else None,
            )
        elif check_type == CheckType.FAILED_TASKS:
            return await check_failed_tasks()
        elif check_type == CheckType.MEMORY_QUARANTINE:
            return await check_memory_quarantine()
        elif check_type == CheckType.OLLAMA_HEALTH:
            return await check_ollama_health()
        elif check_type == CheckType.DAILY_REPORT:
            return await generate_daily_report()
        elif check_type == CheckType.DEPARTMENT_WORKFLOWS:
            return await check_department_workflows()
        elif check_type == CheckType.OLLAMA_MODEL_UPDATES:
            return await check_ollama_model_updates()
        elif check_type == CheckType.AUTONOMOUS_WORK:
            # Only run in AGI mode -- expensive LLM calls
            if self.config.autopilot_level == AutopilotLevel.AGI:
                return await check_autonomous_work()
            return HeartbeatCheckResult(
                check_type="autonomous_work",
                status="ok",
                summary="Skipped: requires AGI autopilot level",
            )
        elif check_type == CheckType.SOUL_REFINEMENT:
            # Weekly refinement of the 10 Department Minds against
            # current domain best-practices. All produced proposals
            # are PENDING -- founder approves each one via the
            # /souls/proposals/{id}/approve endpoint. No live file is
            # touched autonomously. Cheapest cadence is weekly; this
            # check is disabled by default and must be enabled from
            # the Heartbeat config UI after the founder has reviewed
            # the Soul Maker token budget.
            try:
                from app.services.soul_maker.refinement import refine_all_departments

                results = await refine_all_departments(use_research=True)
                approved = sum(1 for r in results if r.verdict == "APPROVE")
                needs_work = sum(1 for r in results if r.verdict == "NEEDS_WORK")
                errors = sum(1 for r in results if r.verdict in {"ABORT", "REJECT"})
                total = len(results)
                return HeartbeatCheckResult(
                    check_type="soul_refinement",
                    status="ok" if errors == 0 else "warning",
                    summary=(
                        f"Refined {total} Minds -- "
                        f"{approved} APPROVE, {needs_work} NEEDS_WORK, {errors} error/reject. "
                        "Pending proposals await founder review at /souls/proposals."
                    ),
                )
            except Exception as exc:
                return HeartbeatCheckResult(
                    check_type="soul_refinement",
                    status="error",
                    summary=f"soul_refinement_failed: {exc}",
                )
        else:
            return HeartbeatCheckResult(
                check_type=check_type.value,
                status="ok",
                summary=f"Check type {check_type.value} not yet implemented",
            )

    def _should_auto_execute(self, priority: ActionPriority) -> bool:
        """Decide if an action should auto-execute based on autopilot level."""
        if self.config.autopilot_level == AutopilotLevel.OFF:
            return False
        elif self.config.autopilot_level == AutopilotLevel.ON:
            return priority in (ActionPriority.LOW, ActionPriority.MEDIUM, ActionPriority.HIGH)
        elif self.config.autopilot_level == AutopilotLevel.AGI:
            return True  # Execute everything, including critical
        return False

    async def _reflect(self, cycle: HeartbeatCycleLog) -> HeartbeatCheckResult:
        """Run the three-question reflection on this cycle's results."""
        summary_parts = []
        for r in cycle.results:
            summary_parts.append(f"[{r.check_type}] {r.status}: {r.summary}")

        reflection = "\n".join([
            f"Cycle {cycle.cycle_id} reflection:",
            f"Q1: {self.config.reflection_questions[0]}",
            f"  -> {len(cycle.actions_queued)} actions pending",
            f"Q2: {self.config.reflection_questions[1]}",
            f"  -> Focus on highest-priority queued actions",
            f"Q3: {self.config.reflection_questions[2]}",
            f"  -> Ran {len(cycle.results)} checks, found {len(cycle.actions_taken) + len(cycle.actions_queued)} actions",
        ])

        return HeartbeatCheckResult(
            check_type="reflection",
            status="ok",
            summary=reflection,
        )
