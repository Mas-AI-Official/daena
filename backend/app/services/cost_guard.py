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
    await guard.preflight_check(tenant_id, estimated_cost=0.05)
    # ... LLM call ...
    await guard.record_usage(tenant_id, user_id, response)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BudgetExceededError
from app.core.logging import get_logger
from app.models.financial import Subscription, UsageLedger

logger = get_logger(__name__)


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


# ── Cost Guard ────────────────────────────────────────────────

class CostGuard:
    """Enforce per-tenant spending limits on LLM usage.

    Requires an async database session for reading subscription
    data and writing usage records.
    """

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

    async def preflight_check(
        self,
        tenant_id: uuid.UUID,
        estimated_cost: float = 0.0,
    ) -> BudgetStatus:
        """Check if the tenant can afford an upcoming LLM call.

        Raises BudgetExceededError if the estimated cost would
        push the tenant over their monthly budget.
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
