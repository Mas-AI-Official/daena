"""Cost Guard — per-tenant spending limits enforcement.

Called before and after LLM requests to prevent budget overruns.

Pre-flight:
    Estimate cost from model pricing × expected tokens.
    Reject if estimated cost would exceed the tenant's monthly budget.

Post-flight:
    Record actual cost in the UsageLedger table.
    Increment the Subscription's spend_this_month_usd.

Budget hierarchy:
    Subscription.monthly_budget_usd → hard cap (NULL = unlimited).
    Future: per-user sub-limits, daily caps, rollover logic.

Usage::

    guard = CostGuard(db)
    await guard.preflight_check(tenant_id, estimated_cost=estimated)
    # ... LLM call ...
    await guard.record_usage(tenant_id, user_id, response)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import ClassVar

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BudgetExceededError, UserQuotaExhaustedError
from app.core.logging import get_logger
from app.models.financial import Subscription, UsageLedger, UserQuota

logger = get_logger(__name__)

# Phase 11 PR-S2.1: dedup window for budget_alert in-app notifications.
# preflight_check fires before EVERY LLM call. Without a window, a user
# over their personal quota with action="warn" would get a notification
# row per chat message — spam. 60 minutes is the smallest window that
# keeps the bell readable while still surfacing the breach soon enough
# to act on. Per process; restart resets so a fresh deploy re-emits.
_BUDGET_WARN_WINDOW_SECONDS = 60 * 60


# ── Data structures ───────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class CostEstimate:
    """Estimated cost for an upcoming LLM call."""

    model_id: str
    estimated_input_tokens: int
    estimated_output_tokens: int
    cost_per_1m_input: float
    cost_per_1m_output: float

    @property
    def estimated_cost_usd(self) -> float:
        input_cost = (self.estimated_input_tokens / 1_000_000) * self.cost_per_1m_input
        output_cost = (self.estimated_output_tokens / 1_000_000) * self.cost_per_1m_output
        return round(input_cost + output_cost, 8)


@dataclass(frozen=True, slots=True)
class BudgetStatus:
    """Current budget state for a tenant."""

    monthly_budget_usd: float | None  # None = unlimited
    spend_this_month_usd: float
    remaining_usd: float | None  # None = unlimited
    is_over_budget: bool


@dataclass(frozen=True, slots=True)
class UserBudgetStatus:
    """Current quota state for a user."""
    monthly_credit_usd: float
    spend_this_month_usd: float
    daily_credit_usd: float | None
    spend_today_usd: float
    remaining_monthly_usd: float
    remaining_daily_usd: float | None
    overage_action: str
    is_over_quota: bool


PLAN_DEFAULTS: dict[str, dict] = {
    "FREE": {"monthly_credit_usd": 0.50, "daily_credit_usd": 0.10, "overage_action": "fallback_free", "max_tenant_share_pct": 100},
    "BASIC": {"monthly_credit_usd": 5.00, "daily_credit_usd": 1.00, "overage_action": "warn", "max_tenant_share_pct": 50},
    "PRO": {"monthly_credit_usd": 10.00, "daily_credit_usd": 2.00, "overage_action": "warn", "max_tenant_share_pct": 50},
    "ENTERPRISE": {"monthly_credit_usd": 50.00, "daily_credit_usd": None, "overage_action": "allow_overage", "max_tenant_share_pct": 30},
    # FOUNDER: the platform owner's account. Shadow-cost tracking is
    # useful (sees movement in usage meters, makes the "what would
    # this cost on API" view honest), but the owner should never be
    # capped by their own billing system. 10000 USD / month + no
    # daily cap + allow_overage means the meter visibly moves with
    # every request but the system never refuses a call.
    "FOUNDER": {"monthly_credit_usd": 10000.00, "daily_credit_usd": None, "overage_action": "allow_overage", "max_tenant_share_pct": 100},
}


# ── Cost Guard ────────────────────────────────────────────────

class CostGuard:
    """Enforce per-tenant spending limits on LLM usage.

    Requires an async database session for reading subscription
    data and writing usage records.
    """

    # Phase 11 PR-S2.1: per-user "last warn-emit timestamp" so the same
    # user does not get a notification row on every preflight call when
    # they are over quota with action="warn" or "allow_overage". Cleared
    # on process restart (intentional: a fresh deploy gives one signal
    # per user that the gate is still firing).
    _recent_warn_emits: ClassVar[dict[uuid.UUID, float]] = {}

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_budget_status(
        self, tenant_id: uuid.UUID,
    ) -> BudgetStatus:
        """Look up the tenant's current budget state."""
        stmt = select(Subscription).where(
            Subscription.tenant_id == tenant_id,
            Subscription.status == "ACTIVE",
        )
        result = await self._db.execute(stmt)
        sub = result.scalar_one_or_none()

        if sub is None:
            # No subscription → treat as unlimited (free tier)
            return BudgetStatus(
                monthly_budget_usd=None,
                spend_this_month_usd=0.0,
                remaining_usd=None,
                is_over_budget=False,
            )

        budget = float(sub.monthly_budget_usd) if sub.monthly_budget_usd is not None else None
        spent = float(sub.spend_this_month_usd)

        if budget is None:
            remaining = None
            over = False
        else:
            remaining = max(0.0, budget - spent)
            over = spent >= budget

        return BudgetStatus(
            monthly_budget_usd=budget,
            spend_this_month_usd=spent,
            remaining_usd=remaining,
            is_over_budget=over,
        )

    async def _get_or_create_user_quota(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID,
    ) -> UserQuota:
        """Lazy-provision: get existing quota or create with plan defaults."""
        from datetime import date, timezone

        stmt = select(UserQuota).where(UserQuota.user_id == user_id)
        result = await self._db.execute(stmt)
        quota = result.scalar_one_or_none()

        if quota is not None:
            # Lazy daily reset: if period_start is from a previous day, reset daily spend
            today = date.today()
            if quota.period_start.date() < today:
                await self._db.execute(
                    update(UserQuota)
                    .where(UserQuota.id == quota.id)
                    .values(spend_today_usd=0, period_start=func.now())
                )
                await self._db.flush()
                # Re-read to get updated values
                result = await self._db.execute(
                    select(UserQuota).where(UserQuota.id == quota.id)
                )
                quota = result.scalar_one()
            return quota

        # Determine plan tier. FOUNDER users get the FOUNDER tier
        # automatically -- they're the platform owner and should never
        # see "Free mode" in their own app. All other users fall back
        # to whatever their tenant's Subscription plan is (or FREE if
        # no Subscription row exists yet).
        from app.models.identity import User

        user_result = await self._db.execute(
            select(User.role).where(User.id == user_id)
        )
        user_role = (user_result.scalar_one_or_none() or "").upper()

        if user_role == "FOUNDER":
            plan = "FOUNDER"
        else:
            sub_stmt = select(Subscription.plan).where(
                Subscription.tenant_id == tenant_id,
                Subscription.status == "ACTIVE",
            )
            sub_result = await self._db.execute(sub_stmt)
            plan = sub_result.scalar_one_or_none() or "FREE"

        defaults = PLAN_DEFAULTS.get(plan.upper(), PLAN_DEFAULTS["FREE"])

        new_quota = UserQuota(
            tenant_id=tenant_id,
            user_id=user_id,
            plan_tier=plan,
            monthly_credit_usd=defaults["monthly_credit_usd"],
            daily_credit_usd=defaults["daily_credit_usd"],
            spend_this_month_usd=0,
            spend_today_usd=0,
            overage_action=defaults["overage_action"],
            max_tenant_share_pct=defaults["max_tenant_share_pct"],
            admin_override=False,
        )
        self._db.add(new_quota)
        await self._db.flush()
        logger.info("cost_guard.user_quota_created", user_id=str(user_id), plan=plan)
        return new_quota

    async def get_user_budget_status(
        self, tenant_id: uuid.UUID, user_id: uuid.UUID,
    ) -> UserBudgetStatus:
        """Get the user's current quota state."""
        quota = await self._get_or_create_user_quota(tenant_id, user_id)

        monthly_credit = float(quota.monthly_credit_usd)
        monthly_spent = float(quota.spend_this_month_usd)
        daily_credit = float(quota.daily_credit_usd) if quota.daily_credit_usd is not None else None
        daily_spent = float(quota.spend_today_usd)

        remaining_monthly = max(0.0, monthly_credit - monthly_spent)
        remaining_daily = max(0.0, daily_credit - daily_spent) if daily_credit is not None else None

        is_over = (
            monthly_spent >= monthly_credit
            or (daily_credit is not None and daily_spent >= daily_credit)
        )

        return UserBudgetStatus(
            monthly_credit_usd=monthly_credit,
            spend_this_month_usd=monthly_spent,
            daily_credit_usd=daily_credit,
            spend_today_usd=daily_spent,
            remaining_monthly_usd=remaining_monthly,
            remaining_daily_usd=remaining_daily,
            overage_action=quota.overage_action,
            is_over_quota=is_over,
        )

    async def preflight_check(
        self,
        tenant_id: uuid.UUID,
        estimated_cost: float = 0.0,
        user_id: uuid.UUID | None = None,
        alert_threshold_pct: float | None = None,
    ) -> BudgetStatus:
        """Check if the tenant can afford an upcoming LLM call.

        Raises BudgetExceededError if the estimated cost would
        push the tenant over their monthly budget.

        ``alert_threshold_pct`` (DECISION-003, 2026-06-01): optional 0..1
        fraction from the user's SettingsBilling ``budget_alert_threshold``
        (which the UI stores as a 0..100 percent). When provided and the
        user is NOT yet over quota but has crossed this fraction of their
        monthly credit, a best-effort "approaching budget" notification is
        emitted (deduped by the same per-user window as the over-quota
        warning). This NEVER changes enforcement; it only changes when the
        warning bell rings. Default None = exact prior behavior.
        """
        status = await self.get_budget_status(tenant_id)

        if status.is_over_budget:
            logger.warning(
                "cost_guard.over_budget",
                tenant_id=str(tenant_id),
                spent=status.spend_this_month_usd,
                budget=status.monthly_budget_usd,
            )
            raise BudgetExceededError(
                f"Monthly budget exhausted: "
                f"${status.spend_this_month_usd:.2f} / "
                f"${status.monthly_budget_usd:.2f}"
            )

        if (
            status.remaining_usd is not None
            and estimated_cost > 0
            and estimated_cost > status.remaining_usd
        ):
            logger.warning(
                "cost_guard.would_exceed",
                tenant_id=str(tenant_id),
                estimated=estimated_cost,
                remaining=status.remaining_usd,
            )
            raise BudgetExceededError(
                f"Estimated cost ${estimated_cost:.4f} exceeds "
                f"remaining budget ${status.remaining_usd:.2f}"
            )

        # Per-user quota check (after tenant check passes)
        if user_id is not None:
            user_status = await self.get_user_budget_status(tenant_id, user_id)
            if user_status.is_over_quota:
                action = user_status.overage_action
                if action == "block":
                    raise BudgetExceededError(
                        f"Personal quota exhausted: "
                        f"${user_status.spend_this_month_usd:.2f} / "
                        f"${user_status.monthly_credit_usd:.2f}"
                    )
                if action == "fallback_free":
                    raise UserQuotaExhaustedError(
                        f"Personal quota reached: "
                        f"${user_status.spend_this_month_usd:.2f} / "
                        f"${user_status.monthly_credit_usd:.2f}. "
                        f"Routing to free model."
                    )
                # "warn" and "allow_overage" pass through
                logger.info(
                    "cost_guard.user_over_quota",
                    user_id=str(user_id),
                    action=action,
                    spent=user_status.spend_this_month_usd,
                    limit=user_status.monthly_credit_usd,
                )
                # Phase 11 PR-S2.1: in-app notification on quota breach.
                # Dedup by (user_id, 60-min window) so a long chat session
                # doesn't spam the bell. Best-effort — must NEVER raise
                # from preflight_check (the cost gate is load-bearing).
                _now = time.time()
                _last = self._recent_warn_emits.get(user_id, 0.0)
                if (_now - _last) >= _BUDGET_WARN_WINDOW_SECONDS:
                    self._recent_warn_emits[user_id] = _now
                    try:
                        from app.services.notification_service import (
                            NotificationService,
                        )
                        await NotificationService(self._db).emit(
                            tenant_id=tenant_id,
                            user_id=user_id,
                            type="budget_alert",
                            title="Personal usage near limit",
                            message=(
                                f"Spent ${user_status.spend_this_month_usd:.2f} of "
                                f"${user_status.monthly_credit_usd:.2f} this month "
                                f"(action: {action}). LLM calls will continue."
                            ),
                            severity="warning",
                            source="cost_guard.preflight_check",
                        )
                    except Exception as _notif_exc:  # noqa: BLE001
                        logger.warning(
                            "cost_guard.notify_failed",
                            user_id=str(user_id),
                            error=str(_notif_exc),
                        )

            # DECISION-003 (2026-06-01): early-warning at the user's chosen
            # threshold (SettingsBilling.budget_alert_threshold). Fires only
            # when NOT yet over quota (the over path above already warns) and
            # the user has crossed alert_threshold_pct of their monthly
            # credit. Best-effort, deduped by the same window, never raises.
            elif (
                alert_threshold_pct is not None
                and user_status.monthly_credit_usd > 0
            ):
                _pct = (
                    user_status.spend_this_month_usd
                    / user_status.monthly_credit_usd
                )
                if _pct >= alert_threshold_pct:
                    _now = time.time()
                    _last = self._recent_warn_emits.get(user_id, 0.0)
                    if (_now - _last) >= _BUDGET_WARN_WINDOW_SECONDS:
                        self._recent_warn_emits[user_id] = _now
                        try:
                            from app.services.notification_service import (
                                NotificationService,
                            )
                            await NotificationService(self._db).emit(
                                tenant_id=tenant_id,
                                user_id=user_id,
                                type="budget_alert",
                                title="Approaching monthly budget",
                                message=(
                                    f"Spent ${user_status.spend_this_month_usd:.2f} of "
                                    f"${user_status.monthly_credit_usd:.2f} this month "
                                    f"({round(_pct * 100)}%, alert at "
                                    f"{round(alert_threshold_pct * 100)}%). "
                                    f"LLM calls will continue."
                                ),
                                severity="info",
                                source="cost_guard.preflight_check",
                            )
                        except Exception as _notif_exc:  # noqa: BLE001
                            logger.warning(
                                "cost_guard.notify_failed",
                                user_id=str(user_id),
                                error=str(_notif_exc),
                            )

        return status

    async def record_usage(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        *,
        provider: str,
        model_name: str,
        tokens_input: int = 0,
        tokens_output: int = 0,
        cost_usd: float = 0.0,
        session_id: uuid.UUID | None = None,
    ) -> None:
        """Record actual LLM usage and update the tenant's spend.

        Writes a UsageLedger row and increments
        Subscription.spend_this_month_usd atomically.
        """
        # 1. Insert ledger entry
        entry = UsageLedger(
            tenant_id=tenant_id,
            user_id=user_id,
            session_id=session_id,
            provider=provider,
            model_name=model_name,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            cost_usd=cost_usd,
        )
        self._db.add(entry)

        # 2. Increment subscription spend (atomic SQL)
        if cost_usd > 0:
            stmt = (
                update(Subscription)
                .where(
                    Subscription.tenant_id == tenant_id,
                    Subscription.status == "ACTIVE",
                )
                .values(
                    spend_this_month_usd=Subscription.spend_this_month_usd + cost_usd,
                )
            )
            await self._db.execute(stmt)

            # Also increment user quota spend
            await self._db.execute(
                update(UserQuota)
                .where(UserQuota.user_id == user_id)
                .values(
                    spend_this_month_usd=UserQuota.spend_this_month_usd + cost_usd,
                    spend_today_usd=UserQuota.spend_today_usd + cost_usd,
                )
            )

        await self._db.flush()

        logger.info(
            "cost_guard.recorded",
            tenant_id=str(tenant_id),
            provider=provider,
            model=model_name,
            cost=cost_usd,
            tokens_in=tokens_input,
            tokens_out=tokens_output,
        )

    def estimate_cost(
        self,
        cost_per_1m_input: float,
        cost_per_1m_output: float,
        estimated_input_tokens: int = 1000,
        estimated_output_tokens: int = 500,
    ) -> float:
        """Quick cost estimate without creating a CostEstimate object."""
        input_cost = (estimated_input_tokens / 1_000_000) * cost_per_1m_input
        output_cost = (estimated_output_tokens / 1_000_000) * cost_per_1m_output
        return round(input_cost + output_cost, 8)
