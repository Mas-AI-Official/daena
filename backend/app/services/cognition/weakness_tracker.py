"""WeaknessTracker -- Anders Ericsson's Deliberate Practice.

"It's not about how many hours you practice. It's about practicing
the things you're BAD at." -- Anders Ericsson

Most agents repeat what they're good at. Daena tracks what she
struggles with and deliberately improves in those areas.

Tracks:
    - Failure rates by problem type
    - Failure rates by tool
    - Failure rates by strategy
    - Identifies weak areas for focused improvement
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class PerformanceMetric:
    """Performance tracking for a category."""
    total: int = 0
    successes: int = 0
    failures: int = 0

    @property
    def success_rate(self) -> float:
        return self.successes / max(self.total, 1)

    @property
    def failure_rate(self) -> float:
        return self.failures / max(self.total, 1)

    @property
    def is_weak(self) -> bool:
        """Weak = less than 60% success rate with 3+ attempts."""
        return self.total >= 3 and self.success_rate < 0.6


@dataclass
class Weakness:
    """An identified weak area."""
    category: str  # "problem_type", "tool", "strategy"
    name: str
    failure_rate: float
    total_attempts: int
    common_errors: list[str] = field(default_factory=list)
    improvement_suggestion: str = ""


class WeaknessTracker:
    """Track and improve Daena's weak areas.

    Ericsson: deliberate practice on weaknesses improves performance
    faster than repeating strengths.
    """

    def __init__(self) -> None:
        self._by_problem_type: dict[str, PerformanceMetric] = defaultdict(PerformanceMetric)
        self._by_tool: dict[str, PerformanceMetric] = defaultdict(PerformanceMetric)
        self._by_strategy: dict[str, PerformanceMetric] = defaultdict(PerformanceMetric)
        self._error_log: dict[str, list[str]] = defaultdict(list)

    async def record(
        self,
        problem_type: str,
        strategy: str,
        tools_used: list[str],
        success: bool,
        error: str = "",
    ) -> None:
        """Record an execution outcome for tracking."""
        # Track by problem type
        self._by_problem_type[problem_type].total += 1
        if success:
            self._by_problem_type[problem_type].successes += 1
        else:
            self._by_problem_type[problem_type].failures += 1
            if error:
                self._error_log[f"pt_{problem_type}"].append(error[:200])

        # Track by strategy
        self._by_strategy[strategy].total += 1
        if success:
            self._by_strategy[strategy].successes += 1
        else:
            self._by_strategy[strategy].failures += 1

        # Track by tool
        for tool in tools_used:
            self._by_tool[tool].total += 1
            if success:
                self._by_tool[tool].successes += 1
            else:
                self._by_tool[tool].failures += 1

    async def get_weaknesses(self, min_attempts: int = 3) -> list[Weakness]:
        """Identify current weak areas.

        Returns weaknesses sorted by failure rate (worst first).
        """
        weaknesses = []

        for name, metric in self._by_problem_type.items():
            if metric.total >= min_attempts and metric.is_weak:
                weaknesses.append(Weakness(
                    category="problem_type",
                    name=name,
                    failure_rate=metric.failure_rate,
                    total_attempts=metric.total,
                    common_errors=self._error_log.get(f"pt_{name}", [])[:3],
                    improvement_suggestion=self._suggest_improvement("problem_type", name),
                ))

        for name, metric in self._by_tool.items():
            if metric.total >= min_attempts and metric.is_weak:
                weaknesses.append(Weakness(
                    category="tool",
                    name=name,
                    failure_rate=metric.failure_rate,
                    total_attempts=metric.total,
                    improvement_suggestion=self._suggest_improvement("tool", name),
                ))

        for name, metric in self._by_strategy.items():
            if metric.total >= min_attempts and metric.is_weak:
                weaknesses.append(Weakness(
                    category="strategy",
                    name=name,
                    failure_rate=metric.failure_rate,
                    total_attempts=metric.total,
                    improvement_suggestion=self._suggest_improvement("strategy", name),
                ))

        weaknesses.sort(key=lambda w: w.failure_rate, reverse=True)
        return weaknesses

    async def get_strengths(self, min_attempts: int = 5) -> list[dict[str, Any]]:
        """Identify current strong areas (for competence map)."""
        strengths = []
        for name, metric in self._by_problem_type.items():
            if metric.total >= min_attempts and metric.success_rate >= 0.8:
                strengths.append({
                    "category": "problem_type",
                    "name": name,
                    "success_rate": metric.success_rate,
                    "total": metric.total,
                })
        return strengths

    def _suggest_improvement(self, category: str, name: str) -> str:
        """Suggest how to improve in a weak area."""
        suggestions = {
            ("problem_type", "deployment"): "Add pre-deployment checks: health endpoint, env vars, port availability",
            ("problem_type", "debugging"): "Use 5 Whys more aggressively. Check actual state before assuming",
            ("problem_type", "configuration"): "Verify config format before writing. Check service restart needed",
            ("tool", "terminal"): "Always check command exists before running. Use absolute paths. Set timeouts",
            ("tool", "file"): "Verify path exists. Check permissions. Use workspace-relative paths",
            ("tool", "browser"): "Wait for page load. Handle dynamic content. Check element visibility",
            ("strategy", "direct_execution"): "Use more analytical strategies (first_principles, inversion) instead",
            ("strategy", "constraint_relaxation"): "Ensure hard constraints are not being relaxed",
        }
        return suggestions.get((category, name), f"Research best practices for {name} and create a cognitive skill")

    def get_summary(self) -> dict[str, Any]:
        """Summary of all tracking data."""
        return {
            "problem_types": {
                name: {"total": m.total, "success_rate": round(m.success_rate, 2)}
                for name, m in self._by_problem_type.items()
            },
            "tools": {
                name: {"total": m.total, "success_rate": round(m.success_rate, 2)}
                for name, m in self._by_tool.items()
            },
            "strategies": {
                name: {"total": m.total, "success_rate": round(m.success_rate, 2)}
                for name, m in self._by_strategy.items()
            },
        }
