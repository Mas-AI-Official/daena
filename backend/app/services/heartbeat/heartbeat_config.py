"""Heartbeat configuration -- interval, active hours, check list.

User-configurable via API or HEARTBEAT.md at project root.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import time
from enum import Enum
from typing import Any


class HeartbeatState(Enum):
    """Current state of the heartbeat daemon."""

    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"


class AutopilotLevel(Enum):
    """How aggressively heartbeat auto-executes."""

    OFF = "off"  # Run checks, queue ALL actions for approval
    ON = "on"  # Auto-execute non-critical, queue critical
    AGI = "agi"  # Auto-execute everything (with audit)


class CheckType(Enum):
    """Types of heartbeat checks."""

    INBOX = "inbox"  # Check inbox.md for new items
    TASKS = "tasks"  # Check tasks.md for pending work
    PROJECT_STATE = "project_state"  # Check STATE.md
    RUNTIME_HEALTH = "runtime_health"  # Check all runtime adapters
    TEST_SUITE = "test_suite"  # Run pytest, report failures
    GIT_STATUS = "git_status"  # Check for uncommitted changes
    QUEUE = "queue"  # Process overnight work queue
    GITHUB_ISSUES = "github_issues"  # Check GitHub repo for new bugs
    FAILED_TASKS = "failed_tasks"  # Retry failed execution tasks
    DAILY_REPORT = "daily_report"  # Generate engineering status report
    OLLAMA_HEALTH = "ollama_health"  # Check Ollama model loading status
    DEPARTMENT_WORKFLOWS = "department_workflows"  # Run scheduled department workflows
    AUTONOMOUS_WORK = "autonomous_work"  # AGI mode: pick up pending tasks and execute via SwarmPlanner
    OLLAMA_MODEL_UPDATES = "ollama_model_updates"  # Check and pull Ollama model updates
    CUSTOM = "custom"  # User-defined check


@dataclass
class HeartbeatCheck:
    """A single check the heartbeat daemon runs."""

    check_type: CheckType
    enabled: bool = True
    description: str = ""
    file_path: str | None = None  # For file-based checks
    command: str | None = None  # For command-based checks
    max_cost_usd: float = 0.01  # Cost guard per check
    use_cheap_runtime: bool = True  # Prefer Ollama over Claude Code


@dataclass
class HeartbeatConfig:
    """Full heartbeat configuration."""

    interval_minutes: int = 30
    active_start: time = field(default_factory=lambda: time(7, 0))
    active_end: time = field(default_factory=lambda: time(23, 0))
    autopilot_level: AutopilotLevel = AutopilotLevel.ON
    state: HeartbeatState = HeartbeatState.STOPPED
    checks: list[HeartbeatCheck] = field(default_factory=list)

    # Three-question reflection (OpenClaw pattern)
    reflection_enabled: bool = True
    reflection_questions: list[str] = field(default_factory=lambda: [
        "What can I do right now that hasn't been done?",
        "Which action has the highest ROI?",
        "What did I do last cycle and what happened?",
    ])

    # Cost guards
    max_cost_per_cycle_usd: float = 0.10
    max_cost_per_day_usd: float = 2.00
    daily_cost_accumulated: float = 0.0

    @classmethod
    def default(cls) -> HeartbeatConfig:
        """Create default configuration with standard checks."""
        return cls(
            checks=[
                HeartbeatCheck(
                    check_type=CheckType.RUNTIME_HEALTH,
                    description="Check all runtime adapters are online",
                ),
                HeartbeatCheck(
                    check_type=CheckType.TASKS,
                    description="Check tasks.md for pending work",
                    file_path="D:/Claude-Coworker/tasks.md",
                ),
                HeartbeatCheck(
                    check_type=CheckType.INBOX,
                    description="Check inbox.md for new items",
                    file_path="D:/Claude-Coworker/inbox.md",
                ),
                HeartbeatCheck(
                    check_type=CheckType.PROJECT_STATE,
                    description="Check STATE.md for project status",
                    file_path="D:/Ideas/Daena/Doc/STATE.md",
                ),
                HeartbeatCheck(
                    check_type=CheckType.GIT_STATUS,
                    description="Check for uncommitted changes",
                    command="git status --porcelain",
                ),
                HeartbeatCheck(
                    check_type=CheckType.QUEUE,
                    description="Process overnight work queue",
                    enabled=False,  # Enabled manually for overnight runs
                ),
                # Engineering Department checks (24/7 employee)
                HeartbeatCheck(
                    check_type=CheckType.TEST_SUITE,
                    description="Run pytest to detect regressions",
                ),
                HeartbeatCheck(
                    check_type=CheckType.GITHUB_ISSUES,
                    description="Check Mas-AI-Official/daena for new bug reports",
                    command="gh issue list --repo Mas-AI-Official/daena --state open --label bug --json number,title,createdAt --limit 10",
                ),
                HeartbeatCheck(
                    check_type=CheckType.FAILED_TASKS,
                    description="Find failed execution tasks and retry them",
                ),
                HeartbeatCheck(
                    check_type=CheckType.OLLAMA_HEALTH,
                    description="Verify all Ollama models are loaded and responsive",
                ),
                HeartbeatCheck(
                    check_type=CheckType.DAILY_REPORT,
                    description="Generate daily engineering status to Daena-Mind/reports/",
                    enabled=True,
                ),
                HeartbeatCheck(
                    check_type=CheckType.DEPARTMENT_WORKFLOWS,
                    description="Run scheduled department workflows (briefings, reports, tasks)",
                    enabled=True,
                ),
                HeartbeatCheck(
                    check_type=CheckType.OLLAMA_MODEL_UPDATES,
                    description="Check installed Ollama models for available updates (weekly)",
                    enabled=True,
                    max_cost_usd=0.0,
                ),
                HeartbeatCheck(
                    check_type=CheckType.AUTONOMOUS_WORK,
                    description="AGI mode: pick up pending tasks, decompose via SwarmPlanner, execute in parallel",
                    enabled=True,
                    max_cost_usd=0.50,
                ),
            ],
        )

    def is_within_active_hours(self) -> bool:
        """Check if current time is within active hours."""
        from datetime import datetime

        now = datetime.now().time()
        if self.active_start <= self.active_end:
            return self.active_start <= now <= self.active_end
        # Handles overnight range (e.g., 22:00 - 06:00)
        return now >= self.active_start or now <= self.active_end

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API/frontend."""
        return {
            "interval_minutes": self.interval_minutes,
            "active_start": self.active_start.isoformat(),
            "active_end": self.active_end.isoformat(),
            "autopilot_level": self.autopilot_level.value,
            "state": self.state.value,
            "checks": [
                {
                    "check_type": c.check_type.value,
                    "enabled": c.enabled,
                    "description": c.description,
                    "file_path": c.file_path,
                    "max_cost_usd": c.max_cost_usd,
                    "use_cheap_runtime": c.use_cheap_runtime,
                }
                for c in self.checks
            ],
            "reflection_enabled": self.reflection_enabled,
            "reflection_questions": self.reflection_questions,
            "max_cost_per_cycle_usd": self.max_cost_per_cycle_usd,
            "max_cost_per_day_usd": self.max_cost_per_day_usd,
            "daily_cost_accumulated": self.daily_cost_accumulated,
        }
