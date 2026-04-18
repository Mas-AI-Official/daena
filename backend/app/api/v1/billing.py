"""Billing overview endpoints backed by UnifiedCostTracker.

All data is in-memory for the current process lifetime.
Endpoints:
    GET /billing/overview          -- session + daily + monthly totals
    GET /billing/by-provider       -- cost breakdown by provider
    GET /billing/by-task-type      -- cost breakdown by task type
    GET /billing/history           -- daily cost history (default 30 days)
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.models.financial import UserQuota
from app.services.billing.cost_tracker import UnifiedCostTracker
from app.services.cost_guard import CostGuard

router = APIRouter()


def _tracker() -> UnifiedCostTracker:
    return UnifiedCostTracker.get_instance()


@router.get("/overview", summary="Cost overview for the current session/day/month")
async def get_overview(
    session_id: str | None = Query(default=None, description="Filter session cost by session ID"),
    current_user: CurrentUser = Depends(get_current_user),
    tracker: UnifiedCostTracker = Depends(_tracker),
) -> dict[str, Any]:
    """Return session cost, daily cost, monthly cost, and total logged entries."""
    return tracker.get_overview(session_id=session_id)


@router.get("/by-provider", summary="Cost breakdown by LLM provider")
async def get_cost_by_provider(
    current_user: CurrentUser = Depends(get_current_user),
    tracker: UnifiedCostTracker = Depends(_tracker),
) -> dict[str, Any]:
    """Return cost, token usage, and call count per provider."""
    return tracker.get_cost_by_provider()


@router.get("/by-task-type", summary="Cost breakdown by task type")
async def get_cost_by_task_type(
    current_user: CurrentUser = Depends(get_current_user),
    tracker: UnifiedCostTracker = Depends(_tracker),
) -> dict[str, float]:
    """Return total cost per task type (chat, code_gen, research, etc.)."""
    return tracker.get_cost_by_task_type()


@router.get("/history", summary="Daily cost history")
async def get_usage_history(
    days: int = Query(default=30, ge=1, le=365, description="Number of days of history to return"),
    current_user: CurrentUser = Depends(get_current_user),
    tracker: UnifiedCostTracker = Depends(_tracker),
) -> list[dict[str, Any]]:
    """Return a list of {date, cost_usd} entries for the requested number of days."""
    return tracker.get_usage_history(days=days)


# ── Per-user quota endpoints ─────────────────────────────────


class QuotaUpdateRequest(BaseModel):
    monthly_credit_usd: float | None = None
    daily_credit_usd: float | None = None
    overage_action: str | None = None
    max_tenant_share_pct: int | None = None


@router.get("/my-quota", summary="Current user's quota status")
async def get_my_quota(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return the authenticated user's remaining credit, daily/monthly spend, and overage action."""
    guard = CostGuard(db)
    status = await guard.get_user_budget_status(current_user.tenant_id, current_user.id)
    return {
        "monthly_credit_usd": status.monthly_credit_usd,
        "spend_this_month_usd": round(status.spend_this_month_usd, 4),
        "remaining_monthly_usd": round(status.remaining_monthly_usd, 4),
        "daily_credit_usd": status.daily_credit_usd,
        "spend_today_usd": round(status.spend_today_usd, 4),
        "remaining_daily_usd": round(status.remaining_daily_usd, 4) if status.remaining_daily_usd is not None else None,
        "overage_action": status.overage_action,
        "is_over_quota": status.is_over_quota,
    }


@router.get("/user-quotas", summary="All user quotas for tenant (admin)")
async def list_user_quotas(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Admin-only: list all user quotas for the current tenant."""
    if current_user.role not in ("ADMIN", "OWNER", "FOUNDER"):
        raise HTTPException(status_code=403, detail="Admin access required")

    stmt = (
        select(UserQuota, User.email, User.display_name)
        .join(User, User.id == UserQuota.user_id)
        .where(UserQuota.tenant_id == current_user.tenant_id)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "user_id": str(q.user_id),
            "email": email,
            "display_name": name,
            "plan_tier": q.plan_tier,
            "monthly_credit_usd": float(q.monthly_credit_usd),
            "spend_this_month_usd": round(float(q.spend_this_month_usd), 4),
            "daily_credit_usd": float(q.daily_credit_usd) if q.daily_credit_usd is not None else None,
            "spend_today_usd": round(float(q.spend_today_usd), 4),
            "overage_action": q.overage_action,
            "max_tenant_share_pct": q.max_tenant_share_pct,
            "admin_override": q.admin_override,
        }
        for q, email, name in rows
    ]


@router.put("/user-quotas/{target_user_id}", summary="Update user quota (admin)")
async def update_user_quota(
    target_user_id: UUID,
    body: QuotaUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Admin-only: update a specific user's quota limits."""
    if current_user.role not in ("ADMIN", "OWNER", "FOUNDER"):
        raise HTTPException(status_code=403, detail="Admin access required")

    values: dict = {"admin_override": True}
    if body.monthly_credit_usd is not None:
        values["monthly_credit_usd"] = body.monthly_credit_usd
    if body.daily_credit_usd is not None:
        values["daily_credit_usd"] = body.daily_credit_usd
    if body.overage_action is not None:
        if body.overage_action not in ("warn", "block", "fallback_free", "allow_overage"):
            raise HTTPException(status_code=422, detail="Invalid overage_action")
        values["overage_action"] = body.overage_action
    if body.max_tenant_share_pct is not None:
        values["max_tenant_share_pct"] = max(1, min(100, body.max_tenant_share_pct))

    stmt = (
        update(UserQuota)
        .where(
            UserQuota.user_id == target_user_id,
            UserQuota.tenant_id == current_user.tenant_id,
        )
        .values(**values)
    )
    result = await db.execute(stmt)
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="User quota not found")

    return {"status": "updated"}
