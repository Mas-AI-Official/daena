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
    check_department_workflows,
    check_file,
    check_git_status,
    check_runtime_health,
    check_test_suite,
    check_github_issues,
    check_failed_tasks,
    check_ollama_health,
    generate_daily_report,
)
from app.services.heartbeat.heartbeat_config import (
    AutopilotLevel,
    CheckType,
    HeartbeatConfig,
    HeartbeatState,
)

logger = get_logger(__name__)


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
        """Start the heartbeat loop."""
        if self.config.state == HeartbeatState.RUNNING:
            logger.warning("heartbeat.already_running")
            return

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

        logger.info("heartbeat.configured", updates=updates)

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

            try:
                result = await self._run_check(check_cfg.check_type, check_cfg)
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

            except Exception as exc:
                logger.warning(
                    "heartbeat.check_failed",
                    check_type=check_cfg.check_type.value,
                    error=str(exc),
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
        elif check_type == CheckType.OLLAMA_HEALTH:
            return await check_ollama_health()
        elif check_type == CheckType.DAILY_REPORT:
            return await generate_daily_report()
        elif check_type == CheckType.DEPARTMENT_WORKFLOWS:
            return await check_department_workflows()
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
