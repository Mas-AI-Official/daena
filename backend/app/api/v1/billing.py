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

from fastapi import APIRouter, Depends, Query

from app.api.v1.auth import get_current_user
from app.models.identity import User
from app.services.billing.cost_tracker import UnifiedCostTracker

router = APIRouter()


def _tracker() -> UnifiedCostTracker:
    return UnifiedCostTracker.get_instance()


@router.get("/overview", summary="Cost overview for the current session/day/month")
async def get_overview(
    session_id: str | None = Query(default=None, description="Filter session cost by session ID"),
    current_user: User = Depends(get_current_user),
    tracker: UnifiedCostTracker = Depends(_tracker),
) -> dict[str, Any]:
    """Return session cost, daily cost, monthly cost, and total logged entries."""
    return tracker.get_overview(session_id=session_id)


@router.get("/by-provider", summary="Cost breakdown by LLM provider")
async def get_cost_by_provider(
    current_user: User = Depends(get_current_user),
    tracker: UnifiedCostTracker = Depends(_tracker),
) -> dict[str, Any]:
    """Return cost, token usage, and call count per provider."""
    return tracker.get_cost_by_provider()


@router.get("/by-task-type", summary="Cost breakdown by task type")
async def get_cost_by_task_type(
    current_user: User = Depends(get_current_user),
    tracker: UnifiedCostTracker = Depends(_tracker),
) -> dict[str, float]:
    """Return total cost per task type (chat, code_gen, research, etc.)."""
    return tracker.get_cost_by_task_type()


@router.get("/history", summary="Daily cost history")
async def get_usage_history(
    days: int = Query(default=30, ge=1, le=365, description="Number of days of history to return"),
    current_user: User = Depends(get_current_user),
    tracker: UnifiedCostTracker = Depends(_tracker),
) -> list[dict[str, Any]]:
    """Return a list of {date, cost_usd} entries for the requested number of days."""
    return tracker.get_usage_history(days=days)
