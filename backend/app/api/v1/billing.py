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

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.core.entitlements import resolve_effective_plan
from app.models.financial import UserQuota
from app.models.identity import User
from app.services.billing import checkout_service
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


# ---------------------------------------------------------------------------
# Checkout / subscription (Stripe, OFF by default)
# ---------------------------------------------------------------------------
class CheckoutRequest(BaseModel):
    plan: str = Field(..., description="Target plan tier, e.g. PRO / MAX / ENTERPRISE")


@router.get("/plans", summary="Purchasable plans and whether billing is live")
async def get_plans(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List the plan tiers a tenant can buy plus a billing_enabled flag.

    When billing is not configured the list is empty and billing_enabled is
    False, so the upgrade UI can show "contact us" instead of a dead button.

    current_plan is the tenant's effective plan (FOUNDER role short-circuits;
    otherwise the active subscription, defaulting to FREE) so the UI can label
    owned/current tiers without a second round-trip.
    """
    current_plan = await resolve_effective_plan(
        db, role=current_user.role, tenant_id=current_user.tenant_id
    )
    return {
        "billing_enabled": checkout_service.billing_configured(),
        "current_plan": current_plan,
        "plans": checkout_service.purchasable_plans(),
    }


@router.post("/checkout", summary="Start a Stripe Checkout session for a plan")
async def start_checkout(
    body: CheckoutRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Create a Stripe-hosted Checkout session and return its URL.

    422 if the plan is not a purchasable, priced tier; 503 if billing is not
    configured (so the frontend can degrade gracefully rather than 500).
    """
    if body.plan.upper() not in checkout_service.purchasable_plans():
        raise HTTPException(
            status_code=422,
            detail=f"Plan '{body.plan}' is not available for purchase",
        )
    try:
        url = checkout_service.create_checkout_session(
            plan=body.plan,
            tenant_id=current_user.tenant_id,
            customer_email=current_user.email or None,
        )
    except checkout_service.BillingNotConfigured as exc:
        raise HTTPException(status_code=503, detail={"error": "not_configured", "message": str(exc)})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return {"checkout_url": url}


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Receive + apply Stripe subscription lifecycle events.

    Intentionally unauthenticated by JWT: authenticity is proven by the
    Stripe-Signature header, verified against the webhook signing secret. A bad
    or missing signature is a 400; billing being off is a 503.
    """
    payload = await request.body()
    sig_header = request.headers.get("Stripe-Signature")
    try:
        event = checkout_service.verify_webhook_event(payload, sig_header)
    except checkout_service.BillingNotConfigured as exc:
        raise HTTPException(status_code=503, detail={"error": "not_configured", "message": str(exc)})
    except Exception as exc:  # bad signature / malformed payload
        raise HTTPException(status_code=400, detail=f"Invalid webhook: {exc}")

    result = await checkout_service.handle_event(db, event)
    return {"received": True, "result": result}
