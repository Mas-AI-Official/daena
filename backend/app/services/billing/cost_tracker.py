"""Unified cost tracking across all providers.

Every API call, CLI execution, and Ollama query gets logged.
Aggregates by session, day, month, provider, task type, and project.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class UsageEntry:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    task_type: str  # chat, code_gen, research, file_ops, governance
    project_id: str | None = None
    session_id: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class UnifiedCostTracker:
    """Tracks costs across ALL providers in real-time.

    Singleton per process. Every provider call logs through here.
    """

    _instance: "UnifiedCostTracker | None" = None

    def __init__(self) -> None:
        self._entries: list[UsageEntry] = []
        self._daily_totals: dict[str, float] = defaultdict(float)  # "YYYY-MM-DD" -> cost
        self._provider_totals: dict[str, float] = defaultdict(float)
        self._task_type_totals: dict[str, float] = defaultdict(float)

    @classmethod
    def get_instance(cls) -> "UnifiedCostTracker":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def log_usage(
        self,
        provider: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        task_type: str = "chat",
        project_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        """Log a single API/CLI usage event."""
        entry = UsageEntry(
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            task_type=task_type,
            project_id=project_id,
            session_id=session_id,
        )
        self._entries.append(entry)

        # Bucket by LOCAL day to match every read path (get_daily_cost /
        # get_monthly_cost / get_usage_history all key on date.today()). The
        # stored entry.timestamp stays UTC for the audit record, but the daily
        # aggregate must use the same frame the budget caps read, or spend
        # logged while local-day != UTC-day vanishes from get_daily_cost and
        # the cap silently stops enforcing.
        day_key = date.today().strftime("%Y-%m-%d")
        self._daily_totals[day_key] += cost_usd
        self._provider_totals[provider] += cost_usd
        self._task_type_totals[task_type] += cost_usd

        # Cap in-memory entries (keep last 10K)
        if len(self._entries) > 10_000:
            self._entries = self._entries[-10_000:]

        logger.debug(
            "cost.logged",
            provider=provider,
            model=model,
            cost=cost_usd,
            task_type=task_type,
        )

    def get_session_cost(self, session_id: str) -> float:
        return sum(e.cost_usd for e in self._entries if e.session_id == session_id)

    def get_daily_cost(self, day: date | None = None) -> float:
        key = (day or date.today()).strftime("%Y-%m-%d")
        return self._daily_totals.get(key, 0.0)

    def get_monthly_cost(self) -> float:
        today = date.today()
        prefix = today.strftime("%Y-%m")
        return sum(v for k, v in self._daily_totals.items() if k.startswith(prefix))

    def get_cost_by_provider(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for provider in set(e.provider for e in self._entries):
            entries = [e for e in self._entries if e.provider == provider]
            result[provider] = {
                "cost_usd": sum(e.cost_usd for e in entries),
                "total_tokens": sum(e.input_tokens + e.output_tokens for e in entries),
                "call_count": len(entries),
            }
        return result

    def get_cost_by_task_type(self) -> dict[str, float]:
        return dict(self._task_type_totals)

    def get_cost_by_project(self) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for entry in self._entries:
            pid = entry.project_id or "general"
            if pid not in result:
                result[pid] = {"cost_usd": 0.0, "task_count": 0}
            result[pid]["cost_usd"] += entry.cost_usd
            result[pid]["task_count"] += 1
        return result

    def get_usage_history(self, days: int = 30) -> list[dict[str, Any]]:
        today = date.today()
        history = []
        for i in range(days):
            d = date.fromordinal(today.toordinal() - i)
            key = d.strftime("%Y-%m-%d")
            history.append({"date": key, "cost_usd": self._daily_totals.get(key, 0.0)})
        return list(reversed(history))

    def get_overview(self, session_id: str | None = None) -> dict[str, Any]:
        return {
            "session_cost": self.get_session_cost(session_id) if session_id else 0.0,
            "daily_cost": self.get_daily_cost(),
            "monthly_cost": self.get_monthly_cost(),
            "total_entries": len(self._entries),
        }
