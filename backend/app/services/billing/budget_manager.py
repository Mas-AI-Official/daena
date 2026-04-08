"""Budget enforcement across the platform.

Checks before every task execution. Can warn, pause, or switch
to free models when budget is exceeded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class BudgetConfig:
    monthly_limit: float = 50.0
    daily_limit: float = 10.0
    per_task_limit: float = 2.0
    alert_thresholds: list[float] | None = None  # [0.5, 0.8, 1.0]
    over_budget_action: str = "warn_only"  # warn_only, pause_tasks, free_models_only

    def __post_init__(self):
        if self.alert_thresholds is None:
            self.alert_thresholds = [0.5, 0.8, 1.0]


PLAN_DEFAULTS: dict[str, dict] = {
    "FREE": {
        "monthly_credit_usd": 0.50,
        "daily_credit_usd": 0.10,
        "overage_action": "fallback_free",
        "max_tenant_share_pct": 100,
    },
    "BASIC": {
        "monthly_credit_usd": 5.00,
        "daily_credit_usd": 1.00,
        "overage_action": "warn",
        "max_tenant_share_pct": 50,
    },
    "PRO": {
        "monthly_credit_usd": 10.00,
        "daily_credit_usd": 2.00,
        "overage_action": "warn",
        "max_tenant_share_pct": 50,
    },
    "ENTERPRISE": {
        "monthly_credit_usd": 50.00,
        "daily_credit_usd": None,
        "overage_action": "allow_overage",
        "max_tenant_share_pct": 30,
    },
}


class BudgetManager:
    """Enforces cost limits."""

    _instance: "BudgetManager | None" = None

    def __init__(self) -> None:
        self.config = BudgetConfig()
        self._alerts_sent: set[float] = set()

    @classmethod
    def get_instance(cls) -> "BudgetManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @staticmethod
    def get_user_defaults(plan: str) -> dict:
        """Return default per-user quota values for a plan tier."""
        return PLAN_DEFAULTS.get(plan.upper(), PLAN_DEFAULTS["FREE"]).copy()

    def check_before_execution(self, estimated_cost: float) -> dict[str, Any]:
        """Called before every task. Returns allow/warn/block decision."""
        from app.services.billing.cost_tracker import UnifiedCostTracker

        tracker = UnifiedCostTracker.get_instance()

        # Per-task limit
        if estimated_cost > self.config.per_task_limit:
            return {
                "decision": "warn",
                "reason": f"Estimated cost ${estimated_cost:.4f} exceeds per-task limit ${self.config.per_task_limit:.2f}",
            }

        # Daily limit
        daily = tracker.get_daily_cost()
        if daily + estimated_cost > self.config.daily_limit:
            if self.config.over_budget_action == "pause_tasks":
                return {"decision": "block", "reason": f"Daily limit ${self.config.daily_limit:.2f} reached (${daily:.2f} used)"}
            if self.config.over_budget_action == "free_models_only":
                return {"decision": "free_only", "reason": "Daily limit reached. Routing to free models only."}
            return {"decision": "warn", "reason": f"Approaching daily limit: ${daily:.2f} / ${self.config.daily_limit:.2f}"}

        # Monthly limit
        monthly = tracker.get_monthly_cost()
        if monthly + estimated_cost > self.config.monthly_limit:
            if self.config.over_budget_action == "pause_tasks":
                return {"decision": "block", "reason": f"Monthly limit ${self.config.monthly_limit:.2f} reached"}
            if self.config.over_budget_action == "free_models_only":
                return {"decision": "free_only", "reason": "Monthly limit reached. Routing to free models only."}
            return {"decision": "warn", "reason": f"Approaching monthly limit: ${monthly:.2f} / ${self.config.monthly_limit:.2f}"}

        # Check alert thresholds
        pct = monthly / self.config.monthly_limit if self.config.monthly_limit > 0 else 0
        for threshold in (self.config.alert_thresholds or []):
            if pct >= threshold and threshold not in self._alerts_sent:
                self._alerts_sent.add(threshold)
                logger.info("budget.threshold_reached", pct=round(pct * 100), threshold=round(threshold * 100))

        return {"decision": "allow"}

    def get_budget_status(self) -> dict[str, Any]:
        from app.services.billing.cost_tracker import UnifiedCostTracker

        tracker = UnifiedCostTracker.get_instance()
        monthly = tracker.get_monthly_cost()
        daily = tracker.get_daily_cost()

        return {
            "monthly_limit": self.config.monthly_limit,
            "monthly_used": round(monthly, 4),
            "monthly_pct": round(monthly / self.config.monthly_limit * 100, 1) if self.config.monthly_limit > 0 else 0,
            "daily_limit": self.config.daily_limit,
            "daily_used": round(daily, 4),
            "per_task_limit": self.config.per_task_limit,
            "over_budget_action": self.config.over_budget_action,
        }

    def update_config(self, **kwargs: Any) -> None:
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        logger.info("budget.config_updated", **kwargs)
