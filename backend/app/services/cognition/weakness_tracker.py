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

import json
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_SNAPSHOT_VERSION = 1
_MAX_ERRORS_PER_KEY = 20


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

    def __init__(self, storage_path: Path | None = None) -> None:
        self._by_problem_type: dict[str, PerformanceMetric] = defaultdict(PerformanceMetric)
        self._by_tool: dict[str, PerformanceMetric] = defaultdict(PerformanceMetric)
        self._by_strategy: dict[str, PerformanceMetric] = defaultdict(PerformanceMetric)
        self._error_log: dict[str, list[str]] = defaultdict(list)
        self._storage_path = storage_path
        if self._storage_path is not None:
            self._load()

    def _save(self) -> None:
        """Persist a snapshot to disk. Never raises (Rule 17: fail open, visibly)."""
        if self._storage_path is None:
            return
        try:
            snapshot = {
                "version": _SNAPSHOT_VERSION,
                "problem_types": {
                    name: {"total": m.total, "successes": m.successes, "failures": m.failures}
                    for name, m in self._by_problem_type.items()
                },
                "tools": {
                    name: {"total": m.total, "successes": m.successes, "failures": m.failures}
                    for name, m in self._by_tool.items()
                },
                "strategies": {
                    name: {"total": m.total, "successes": m.successes, "failures": m.failures}
                    for name, m in self._by_strategy.items()
                },
                "errors": dict(self._error_log),
            }
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._storage_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self._storage_path)
        except Exception:
            logger.warning(
                "weakness_tracker_save_failed",
                path=str(self._storage_path),
                exc_info=True,
            )

    def _load(self) -> None:
        """Rehydrate from a snapshot. Corrupt/invalid -> warn + fresh start."""
        if self._storage_path is None or not self._storage_path.exists():
            return
        try:
            raw = json.loads(self._storage_path.read_text(encoding="utf-8"))
            dims = (
                ("problem_types", self._by_problem_type),
                ("tools", self._by_tool),
                ("strategies", self._by_strategy),
            )
            for key, target in dims:
                for name, counts in dict(raw.get(key) or {}).items():
                    target[str(name)] = PerformanceMetric(
                        total=int(counts.get("total", 0)),
                        successes=int(counts.get("successes", 0)),
                        failures=int(counts.get("failures", 0)),
                    )
            for key, errors in dict(raw.get("errors") or {}).items():
                self._error_log[str(key)] = [str(e) for e in list(errors)][-_MAX_ERRORS_PER_KEY:]
        except Exception:
            logger.warning(
                "weakness_tracker_load_failed",
                path=str(self._storage_path),
                exc_info=True,
            )
            self._by_problem_type.clear()
            self._by_tool.clear()
            self._by_strategy.clear()
            self._error_log.clear()

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
                log = self._error_log[f"pt_{problem_type}"]
                log.append(error[:200])
                del log[:-_MAX_ERRORS_PER_KEY]

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

        self._save()

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


_TRACKERS: dict[str, WeaknessTracker] = {}


def _storage_dir() -> Path:
    configured = getattr(get_settings(), "weakness_dir", None)
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / "var" / "cognition"


def get_weakness_tracker(tenant_id: UUID | None) -> WeaknessTracker:
    """Process-wide per-tenant tracker with a durable JSON snapshot.

    tenant_id None -> shared pure in-memory instance, no file (leak guard).
    Multi-worker deployments are last-writer-wins per tenant snapshot; the
    signal is advisory (prompt shaping), so that trade-off is acceptable.
    """
    key = tenant_id.hex if tenant_id is not None else "__memory__"
    tracker = _TRACKERS.get(key)
    if tracker is None:
        path = _storage_dir() / f"weakness-{tenant_id.hex}.json" if tenant_id is not None else None
        tracker = WeaknessTracker(storage_path=path)
        _TRACKERS[key] = tracker
    return tracker


async def build_weakness_note(tracker: WeaknessTracker, problem_type: str) -> str:
    """Render the orientation note for known weaknesses in this problem area.

    Lives next to the tracker API so callers cannot drift onto a
    nonexistent method name again (the old ooda_engine bug class).
    """
    weaknesses = await tracker.get_weaknesses()
    relevant = [
        w for w in weaknesses
        if (w.category == "problem_type" and w.name == problem_type)
        or w.category == "strategy"
    ]
    if not relevant:
        return ""
    weak_names = [w.name for w in relevant[:3]]
    note = (
        f" KNOWN WEAKNESSES in this area: {', '.join(weak_names)}."
        " Adjust approach accordingly."
    )
    for w in relevant:
        if w.improvement_suggestion:
            note += f" Suggestion: {w.improvement_suggestion}"
            break
    return note
