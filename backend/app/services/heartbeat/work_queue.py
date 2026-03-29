"""Overnight work queue -- task list for autonomous execution.

The heartbeat daemon processes this queue when QUEUE check is enabled.
Each task is a self-contained prompt that gets routed through the
governed pipeline to Claude Code or another runtime.

Tasks have states: pending -> in_progress -> completed | failed | skipped
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class QueueTaskStatus(Enum):
    """Status of a queued task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class QueueTaskPriority(Enum):
    """Priority for queue ordering."""

    P0_CRITICAL = 0  # Must do first
    P1_HIGH = 1
    P2_MEDIUM = 2
    P3_LOW = 3


@dataclass
class QueueTask:
    """A single task in the overnight work queue."""

    task_id: str
    title: str
    prompt: str  # Full prompt to send to runtime
    priority: QueueTaskPriority = QueueTaskPriority.P2_MEDIUM
    status: QueueTaskStatus = QueueTaskStatus.PENDING
    runtime_preference: str = "claude_code"  # Which runtime to use
    max_cost_usd: float = 1.0  # Cost guard per task
    max_duration_seconds: int = 300  # Timeout
    output_path: str | None = None  # Where to save output file
    depends_on: list[str] = field(default_factory=list)  # Task IDs this depends on
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    result_summary: str | None = None
    cost_usd: float = 0.0
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "prompt": self.prompt[:200] + "..." if len(self.prompt) > 200 else self.prompt,
            "priority": self.priority.value,
            "status": self.status.value,
            "runtime_preference": self.runtime_preference,
            "max_cost_usd": self.max_cost_usd,
            "output_path": self.output_path,
            "depends_on": self.depends_on,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result_summary": self.result_summary,
            "cost_usd": self.cost_usd,
            "error": self.error,
        }


class WorkQueue:
    """Ordered task queue for overnight autonomous execution.

    Tasks are processed in priority order. Dependencies are respected:
    a task won't start until all its dependencies are completed.
    """

    def __init__(self) -> None:
        self._tasks: dict[str, QueueTask] = {}

    def add(self, task: QueueTask) -> None:
        """Add a task to the queue."""
        self._tasks[task.task_id] = task
        logger.info("queue.task_added", task_id=task.task_id, title=task.title)

    def remove(self, task_id: str) -> bool:
        """Remove a task from the queue."""
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False

    def get_next(self) -> QueueTask | None:
        """Get the next task to execute (highest priority, dependencies met)."""
        completed_ids = {
            tid for tid, t in self._tasks.items()
            if t.status == QueueTaskStatus.COMPLETED
        }

        candidates = [
            t for t in self._tasks.values()
            if t.status == QueueTaskStatus.PENDING
            and all(dep in completed_ids for dep in t.depends_on)
        ]

        if not candidates:
            return None

        # Sort by priority (lower number = higher priority)
        candidates.sort(key=lambda t: t.priority.value)
        return candidates[0]

    def mark_in_progress(self, task_id: str) -> None:
        """Mark a task as in progress."""
        if task_id in self._tasks:
            self._tasks[task_id].status = QueueTaskStatus.IN_PROGRESS
            self._tasks[task_id].started_at = datetime.utcnow()

    def mark_completed(self, task_id: str, summary: str, cost: float = 0.0) -> None:
        """Mark a task as completed."""
        if task_id in self._tasks:
            self._tasks[task_id].status = QueueTaskStatus.COMPLETED
            self._tasks[task_id].completed_at = datetime.utcnow()
            self._tasks[task_id].result_summary = summary
            self._tasks[task_id].cost_usd = cost

    def mark_failed(self, task_id: str, error: str) -> None:
        """Mark a task as failed."""
        if task_id in self._tasks:
            self._tasks[task_id].status = QueueTaskStatus.FAILED
            self._tasks[task_id].completed_at = datetime.utcnow()
            self._tasks[task_id].error = error

    def get_all(self) -> list[dict[str, Any]]:
        """Get all tasks as dicts."""
        return [t.to_dict() for t in sorted(
            self._tasks.values(),
            key=lambda t: (t.priority.value, t.created_at),
        )]

    def get_summary(self) -> dict[str, Any]:
        """Get queue summary."""
        by_status = {}
        total_cost = 0.0
        for t in self._tasks.values():
            by_status[t.status.value] = by_status.get(t.status.value, 0) + 1
            total_cost += t.cost_usd
        return {
            "total": len(self._tasks),
            "by_status": by_status,
            "total_cost_usd": total_cost,
        }

    def generate_briefing(self) -> str:
        """Generate morning briefing from queue results."""
        completed = [t for t in self._tasks.values() if t.status == QueueTaskStatus.COMPLETED]
        failed = [t for t in self._tasks.values() if t.status == QueueTaskStatus.FAILED]
        pending = [t for t in self._tasks.values() if t.status == QueueTaskStatus.PENDING]
        total_cost = sum(t.cost_usd for t in self._tasks.values())

        lines = [
            "# Morning Briefing",
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "## Overnight Results",
            f"- Completed: {len(completed)}",
            f"- Failed: {len(failed)}",
            f"- Remaining: {len(pending)}",
            f"- Total cost: ${total_cost:.4f}",
            "",
        ]

        if completed:
            lines.append("## Completed Tasks")
            for t in completed:
                lines.append(f"- **{t.title}**: {t.result_summary or 'Done'} (${t.cost_usd:.4f})")
            lines.append("")

        if failed:
            lines.append("## Failed Tasks")
            for t in failed:
                lines.append(f"- **{t.title}**: {t.error or 'Unknown error'}")
            lines.append("")

        if pending:
            lines.append("## Remaining Tasks")
            for t in pending:
                lines.append(f"- {t.title}")
            lines.append("")

        lines.extend([
            "## Suggestions for Today",
            "- Review completed task outputs",
            "- Fix any failed tasks manually",
            "- Update priorities based on results",
        ])

        return "\n".join(lines)

    @classmethod
    def overnight_default(cls) -> WorkQueue:
        """Create queue with the standard overnight tasks."""
        queue = cls()

        queue.add(QueueTask(
            task_id="nvidia_inception",
            title="Draft NVIDIA Inception application",
            prompt=(
                "Draft the NVIDIA Inception application for MAS-AI Technologies Inc. "
                "Read D:/Claude-Coworker/skills/mas-ai-funding-agent.md for company context. "
                "Search the web for current NVIDIA Inception program requirements. "
                "Write a complete application draft and save to D:/Ideas/Daena/Doc/applications/nvidia-inception.md."
            ),
            priority=QueueTaskPriority.P0_CRITICAL,
            output_path="D:/Ideas/Daena/Doc/applications/nvidia-inception.md",
            max_cost_usd=1.0,
        ))

        queue.add(QueueTask(
            task_id="msft_founders_hub",
            title="Draft Microsoft Founders Hub application",
            prompt=(
                "Search the web for current Microsoft Founders Hub program requirements and benefits. "
                "Read D:/Claude-Coworker/skills/mas-ai-funding-agent.md for company context. "
                "Write a complete application draft and save to D:/Ideas/Daena/Doc/applications/msft-founders-hub.md."
            ),
            priority=QueueTaskPriority.P0_CRITICAL,
            output_path="D:/Ideas/Daena/Doc/applications/msft-founders-hub.md",
            max_cost_usd=1.0,
        ))

        queue.add(QueueTask(
            task_id="improve_test_coverage",
            title="Improve test coverage to 960+",
            prompt=(
                "Run pytest with coverage in D:/Ideas/Daena/backend. Find files below 70% coverage. "
                "Write additional tests for the lowest-coverage files. Target: 960+ total tests."
            ),
            priority=QueueTaskPriority.P1_HIGH,
            max_cost_usd=0.50,
            max_duration_seconds=600,
        ))

        queue.add(QueueTask(
            task_id="fix_todos",
            title="Fix TODO/FIXME comments in codebase",
            prompt=(
                "Search for all TODO and FIXME comments across D:/Ideas/Daena/backend and D:/Ideas/Daena/frontend. "
                "Fix every easy one (estimated time < 5 min each). "
                "Document complex ones in D:/Ideas/Daena/Doc/TECH-DEBT.md."
            ),
            priority=QueueTaskPriority.P2_MEDIUM,
            max_cost_usd=0.50,
        ))

        queue.add(QueueTask(
            task_id="seo_audit",
            title="SEO audit on landing page",
            prompt=(
                "Audit D:/Ideas/Daena/landing/index.html for SEO: check meta tags, OG tags, "
                "structured data, sitemap, robots.txt. Fix any missing elements."
            ),
            priority=QueueTaskPriority.P2_MEDIUM,
            max_cost_usd=0.30,
        ))

        queue.add(QueueTask(
            task_id="a11y_audit",
            title="Accessibility audit",
            prompt=(
                "Audit D:/Ideas/Daena/frontend/src for accessibility: check color contrast ratios, "
                "keyboard navigation support, ARIA attributes, screen reader compatibility. "
                "Fix critical issues found."
            ),
            priority=QueueTaskPriority.P3_LOW,
            max_cost_usd=0.50,
        ))

        return queue
