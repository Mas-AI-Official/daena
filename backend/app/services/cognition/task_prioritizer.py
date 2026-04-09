"""TaskPrioritizer -- Eat the Frog + Pareto 80/20.

Brian Tracy (Eat the Frog): Do the hardest, most important thing FIRST.
Vilfredo Pareto (80/20): 20% of actions produce 80% of results. Find that 20%.

When Daena has multiple subtasks, she doesn't do the easiest first.
She scores each by IMPACT * URGENCY and tackles the highest first.

If a subtask is blocked, she skips it and works on the next highest,
then returns to the blocked one later (not a dead end, a detour).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PrioritizedTask:
    """A task with priority scoring."""
    description: str
    impact: float = 0.5  # 0.0 to 1.0
    urgency: float = 0.5  # 0.0 to 1.0
    difficulty: float = 0.5  # 0.0 to 1.0
    blocked: bool = False
    blocker_reason: str = ""

    @property
    def priority_score(self) -> float:
        """Impact * Urgency. High impact + high urgency = do first."""
        if self.blocked:
            return 0.0
        return self.impact * self.urgency

    @property
    def is_the_frog(self) -> bool:
        """The Frog = hardest AND most important task."""
        return self.impact > 0.7 and self.difficulty > 0.7


class TaskPrioritizer:
    """Prioritize subtasks by impact and urgency.

    Tracy: eat the frog first (hardest + most important).
    Pareto: focus on the 20% that produces 80% of results.
    """

    async def prioritize(
        self,
        tasks: list[str],
        context: dict[str, Any] | None = None,
    ) -> list[PrioritizedTask]:
        """Score and sort tasks by priority.

        Returns tasks sorted by priority_score descending.
        The Frog is always first (if identified).
        """
        prioritized = []

        for task_desc in tasks:
            pt = PrioritizedTask(
                description=task_desc,
                impact=self._score_impact(task_desc),
                urgency=self._score_urgency(task_desc),
                difficulty=self._score_difficulty(task_desc),
            )
            prioritized.append(pt)

        # Sort: frogs first, then by priority score
        prioritized.sort(
            key=lambda t: (t.is_the_frog, t.priority_score),
            reverse=True,
        )

        logger.info(
            "task_prioritizer.sorted",
            count=len(prioritized),
            frog=next((t.description[:50] for t in prioritized if t.is_the_frog), "none"),
        )

        return prioritized

    def _score_impact(self, task: str) -> float:
        """Estimate task impact. Higher = more important to the goal."""
        task_lower = task.lower()
        if any(kw in task_lower for kw in ["critical", "blocker", "production", "security", "data loss"]):
            return 0.9
        if any(kw in task_lower for kw in ["deploy", "fix", "repair", "restore", "migrate"]):
            return 0.8
        if any(kw in task_lower for kw in ["create", "build", "implement", "add"]):
            return 0.7
        if any(kw in task_lower for kw in ["test", "verify", "validate", "check"]):
            return 0.6
        if any(kw in task_lower for kw in ["clean", "organize", "document", "format"]):
            return 0.4
        return 0.5

    def _score_urgency(self, task: str) -> float:
        """Estimate task urgency."""
        task_lower = task.lower()
        if any(kw in task_lower for kw in ["now", "immediately", "urgent", "asap", "critical"]):
            return 0.95
        if any(kw in task_lower for kw in ["today", "soon", "priority", "before"]):
            return 0.8
        if any(kw in task_lower for kw in ["when possible", "eventually", "later"]):
            return 0.3
        return 0.5

    def _score_difficulty(self, task: str) -> float:
        """Estimate task difficulty. The Frog = high difficulty + high impact."""
        task_lower = task.lower()
        if any(kw in task_lower for kw in ["complex", "refactor", "migrate", "architect", "redesign"]):
            return 0.9
        if any(kw in task_lower for kw in ["debug", "investigate", "analyze", "optimize"]):
            return 0.7
        if any(kw in task_lower for kw in ["configure", "install", "connect"]):
            return 0.5
        if any(kw in task_lower for kw in ["list", "read", "check", "verify"]):
            return 0.3
        return 0.5
