"""Analytics dashboard endpoint -- single aggregate query for the frontend dashboard.

Returns usage, cost, governance, department activity, provider breakdown,
and 30-day daily usage in one round-trip.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, case, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.database import get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.governance import GoaRequest
from app.models.organization import Department
from app.services.billing.cost_tracker import UnifiedCostTracker

logger = logging.getLogger(__name__)

router = APIRouter()


def _tracker() -> UnifiedCostTracker:
    return UnifiedCostTracker.get_instance()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _start_of_today() -> datetime:
    return datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def _start_of_week() -> datetime:
    now = _now_utc()
    start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return start


async def _query_usage(
    db: AsyncSession,
    tenant_id: UUID,
) -> dict[str, Any]:
    """Message and token counts for today and this week."""
    try:
        today_start = _start_of_today()
        week_start = _start_of_week()

        stmt = (
            select(
                func.count(
                    case((ChatMessage.created_at >= today_start, ChatMessage.id))
                ).label("messages_today"),
                func.count(
                    case((ChatMessage.created_at >= week_start, ChatMessage.id))
                ).label("messages_this_week"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ChatMessage.created_at >= today_start,
                                func.coalesce(ChatMessage.token_count_input, 0)
                                + func.coalesce(ChatMessage.token_count_output, 0),
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("tokens_today"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                ChatMessage.created_at >= week_start,
                                func.coalesce(ChatMessage.token_count_input, 0)
                                + func.coalesce(ChatMessage.token_count_output, 0),
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("tokens_this_week"),
            )
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .where(ChatSession.tenant_id == tenant_id)
            .where(ChatMessage.created_at >= week_start)
        )
        result = await db.execute(stmt)
        row = result.one()
        return {
            "messages_today": int(row.messages_today),
            "messages_this_week": int(row.messages_this_week),
            "tokens_today": int(row.tokens_today),
            "tokens_this_week": int(row.tokens_this_week),
        }
    except Exception:
        logger.exception("analytics.usage_query_failed")
        return {
            "messages_today": 0,
            "messages_this_week": 0,
            "tokens_today": 0,
            "tokens_this_week": 0,
        }


async def _query_governance(
    db: AsyncSession,
    tenant_id: UUID,
) -> dict[str, Any]:
    """Governance stats: pending, decided today, auto-approved %, avg decision time."""
    try:
        today_start = _start_of_today()

        stmt = select(
            func.count(
                case((GoaRequest.status == "pending", GoaRequest.id))
            ).label("approvals_pending"),
            func.count(
                case(
                    (
                        and_(
                            GoaRequest.status != "pending",
                            GoaRequest.decided_at >= today_start,
                        ),
                        GoaRequest.id,
                    )
                )
            ).label("approvals_decided_today"),
            func.count(
                case((GoaRequest.status == "auto_approved", GoaRequest.id))
            ).label("auto_approved_count"),
            func.count(GoaRequest.id).label("total_count"),
        ).where(GoaRequest.tenant_id == tenant_id)

        result = await db.execute(stmt)
        row = result.one()

        total = int(row.total_count) or 1  # avoid division by zero
        auto_approved_pct = round(int(row.auto_approved_count) / total * 100, 1)

        # Average decision time for decided requests
        avg_stmt = (
            select(
                func.avg(
                    func.extract("epoch", GoaRequest.decided_at)
                    - func.extract("epoch", GoaRequest.created_at)
                )
            )
            .where(GoaRequest.tenant_id == tenant_id)
            .where(GoaRequest.decided_at.isnot(None))
        )
        avg_result = await db.execute(avg_stmt)
        avg_seconds = avg_result.scalar()
        avg_decision_time_ms = round(avg_seconds * 1000) if avg_seconds else 0

        return {
            "approvals_pending": int(row.approvals_pending),
            "approvals_decided_today": int(row.approvals_decided_today),
            "auto_approved_pct": auto_approved_pct,
            "avg_decision_time_ms": avg_decision_time_ms,
        }
    except Exception:
        logger.exception("analytics.governance_query_failed")
        return {
            "approvals_pending": 0,
            "approvals_decided_today": 0,
            "auto_approved_pct": 0.0,
            "avg_decision_time_ms": 0,
        }


async def _query_departments(
    db: AsyncSession,
    tenant_id: UUID,
) -> list[dict[str, Any]]:
    """Top 10 departments by message count with last active timestamp."""
    try:
        stmt = (
            select(
                Department.name,
                func.count(ChatMessage.id).label("message_count"),
                func.max(ChatMessage.created_at).label("last_active"),
            )
            .join(ChatSession, ChatSession.department_id == Department.id)
            .join(ChatMessage, ChatMessage.session_id == ChatSession.id)
            .where(Department.tenant_id == tenant_id)
            .group_by(Department.id, Department.name)
            .order_by(func.count(ChatMessage.id).desc())
            .limit(10)
        )
        result = await db.execute(stmt)
        rows = result.all()
        return [
            {
                "name": row.name,
                "message_count": int(row.message_count),
                "last_active": row.last_active.isoformat() if row.last_active else None,
            }
            for row in rows
        ]
    except Exception:
        logger.exception("analytics.departments_query_failed")
        return []


async def _query_daily_usage(
    db: AsyncSession,
    tenant_id: UUID,
) -> list[dict[str, Any]]:
    """Daily message count, token total, and cost for the last 30 days."""
    try:
        thirty_days_ago = _now_utc() - timedelta(days=30)
        day_expr = func.date(ChatMessage.created_at)

        stmt = (
            select(
                day_expr.label("day"),
                func.count(ChatMessage.id).label("messages"),
                func.coalesce(
                    func.sum(
                        func.coalesce(ChatMessage.token_count_input, 0)
                        + func.coalesce(ChatMessage.token_count_output, 0)
                    ),
                    0,
                ).label("tokens"),
                func.coalesce(func.sum(ChatMessage.cost_usd), 0).label("cost_usd"),
            )
            .join(ChatSession, ChatSession.id == ChatMessage.session_id)
            .where(ChatSession.tenant_id == tenant_id)
            .where(ChatMessage.created_at >= thirty_days_ago)
            .group_by(day_expr)
            .order_by(day_expr)
        )
        result = await db.execute(stmt)
        rows = result.all()

        # Build a full 30-day series, filling gaps with zeros
        data_map: dict[str, dict[str, Any]] = {}
        for row in rows:
            day_str = str(row.day)
            data_map[day_str] = {
                "date": day_str,
                "messages": int(row.messages),
                "tokens": int(row.tokens),
                "cost_usd": round(float(row.cost_usd), 6),
            }

        today = date.today()
        series: list[dict[str, Any]] = []
        for i in range(30):
            d = today - timedelta(days=29 - i)
            key = d.isoformat()
            series.append(
                data_map.get(key, {"date": key, "messages": 0, "tokens": 0, "cost_usd": 0.0})
            )
        return series
    except Exception:
        logger.exception("analytics.daily_usage_query_failed")
        return []


def _get_costs(tracker: UnifiedCostTracker) -> dict[str, float]:
    """Cost totals from the in-memory tracker."""
    try:
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        cost_this_week = sum(
            v
            for k, v in tracker._daily_totals.items()
            if k >= week_start.isoformat()
        )
        return {
            "cost_today_usd": round(tracker.get_daily_cost(), 6),
            "cost_this_week_usd": round(cost_this_week, 6),
            "cost_this_month_usd": round(tracker.get_monthly_cost(), 6),
        }
    except Exception:
        logger.exception("analytics.cost_query_failed")
        return {
            "cost_today_usd": 0.0,
            "cost_this_week_usd": 0.0,
            "cost_this_month_usd": 0.0,
        }


def _get_providers(tracker: UnifiedCostTracker) -> list[dict[str, Any]]:
    """Provider breakdown from in-memory tracker."""
    try:
        by_provider = tracker.get_cost_by_provider()
        return [
            {
                "provider": provider,
                "cost_usd": round(data["cost_usd"], 6),
                "calls": data["call_count"],
                "tokens": data["total_tokens"],
            }
            for provider, data in sorted(
                by_provider.items(), key=lambda x: x[1]["cost_usd"], reverse=True
            )
        ]
    except Exception:
        logger.exception("analytics.providers_query_failed")
        return []


@router.get("/dashboard", summary="Aggregate analytics dashboard")
async def get_dashboard(
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    tracker: UnifiedCostTracker = Depends(_tracker),
) -> dict[str, Any]:
    """Return a single JSON payload with usage, costs, governance,
    department activity, provider breakdown, and 30-day daily usage.

    All DB queries are scoped to the authenticated user's tenant.
    Individual sections return safe defaults on failure so the
    endpoint never returns an error status.
    """
    tenant_id = current_user.tenant_id

    # SQLAlchemy AsyncSession is not concurrency-safe. The previous
    # version gathered four coroutines against this same request-scoped
    # session, which raised:
    #   InvalidRequestError: This session is provisioning a new connection;
    #   concurrent operations are not permitted.
    # Keep the endpoint stable by running the sections sequentially.
    usage = await _query_usage(db, tenant_id)
    governance = await _query_governance(db, tenant_id)
    departments = await _query_departments(db, tenant_id)
    daily_usage = await _query_daily_usage(db, tenant_id)

    return {
        "usage": usage,
        "costs": _get_costs(tracker),
        "governance": governance,
        "departments": departments,
        "providers": _get_providers(tracker),
        "daily_usage": daily_usage,
    }
