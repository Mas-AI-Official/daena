"""DECISION-003 (2026-06-01): budget settings -> real enforcement.

The SettingsBilling UI has three budget controls that, before this change,
persisted to user.settings but were consumed by nothing (the audit flagged
them BACKEND_EXISTS_NOT_WIRED). This wires them into the EXISTING per-user
enforcement model (UserQuota, enforced by CostGuard.preflight_check on every
chat) via a sync-on-save in PUT /settings/user. No migration; the
user_quotas table and the CostGuard enforcement already exist.

Covered:
  * over_budget_action value map (warn|fallback|block ->
    warn|fallback_free|block) at the settings-save layer.
  * monthly_budget -> UserQuota.monthly_credit_usd.
  * explicit-only: a PUT that omits the budget fields must NOT clobber the
    user's existing quota (a FOUNDER stays uncapped).
  * the resulting UserQuota actually drives CostGuard enforcement
    (block -> BudgetExceededError once spend is over the new cap).
  * budget_alert_threshold early-warning notification via preflight_check.
"""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.settings import _OVER_BUDGET_ACTION_MAP
from app.core.exceptions import BudgetExceededError
from app.models.financial import UserQuota
from app.models.notification import Notification
from app.services.cost_guard import CostGuard


async def _register_and_login(client: AsyncClient) -> dict:
    unique = uuid.uuid4().hex[:8]
    email = f"budget-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Budget Tester",
            "tenant_name": f"BudgetOrg-{unique}",
        },
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    data = login.json()["data"]
    u = data["user"]
    uid = u.get("id") or u.get("user_id") or u.get("sub")
    return {
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user_id": uuid.UUID(uid),
        "tenant_id": uuid.UUID(u["tenant_id"]),
    }


async def _quota_for(db: AsyncSession, user_id: uuid.UUID) -> UserQuota | None:
    return (
        await db.execute(select(UserQuota).where(UserQuota.user_id == user_id))
    ).scalar_one_or_none()


def test_over_budget_action_map_is_total_over_ui_values() -> None:
    """Every value the SettingsBilling dropdown can send must map to a
    real UserQuota.overage_action the CostGuard understands."""
    # The UI's <select> options (settings.py pattern ^(warn|fallback|block)$)
    assert _OVER_BUDGET_ACTION_MAP == {
        "warn": "warn",
        "fallback": "fallback_free",
        "block": "block",
    }


@pytest.mark.asyncio
async def test_put_budget_settings_syncs_into_user_quota(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """PUT /settings/user with monthly_budget + over_budget_action writes
    the per-user UserQuota row that CostGuard enforces."""
    auth = await _register_and_login(client)

    resp = await client.put(
        "/api/v1/settings/user",
        json={"monthly_budget": 7, "over_budget_action": "block"},
        headers=auth["headers"],
    )
    assert resp.status_code == 200, resp.text

    quota = await _quota_for(db_session, auth["user_id"])
    assert quota is not None
    assert float(quota.monthly_credit_usd) == 7.0
    # UI "block" maps to UserQuota "block"
    assert quota.overage_action == "block"


@pytest.mark.asyncio
async def test_put_fallback_action_maps_to_fallback_free(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """UI 'fallback' must land as UserQuota 'fallback_free' (the value the
    CostGuard branches on to route to a free model)."""
    auth = await _register_and_login(client)

    resp = await client.put(
        "/api/v1/settings/user",
        json={"over_budget_action": "fallback"},
        headers=auth["headers"],
    )
    assert resp.status_code == 200, resp.text

    quota = await _quota_for(db_session, auth["user_id"])
    assert quota is not None
    assert quota.overage_action == "fallback_free"


@pytest.mark.asyncio
async def test_put_without_budget_fields_does_not_clobber_quota(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """A settings PUT that omits the budget fields must NOT create or
    overwrite the user's quota -- so a user who never touches the budget
    controls keeps their plan-default quota (a FOUNDER stays uncapped)."""
    auth = await _register_and_login(client)

    # First, establish a known quota via an explicit budget save.
    await client.put(
        "/api/v1/settings/user",
        json={"monthly_budget": 12, "over_budget_action": "warn"},
        headers=auth["headers"],
    )
    before = await _quota_for(db_session, auth["user_id"])
    assert before is not None and float(before.monthly_credit_usd) == 12.0

    # Now save an UNRELATED preference. The quota must be untouched.
    resp = await client.put(
        "/api/v1/settings/user",
        json={"dark_mode": True},
        headers=auth["headers"],
    )
    assert resp.status_code == 200, resp.text

    after = await _quota_for(db_session, auth["user_id"])
    assert after is not None
    assert float(after.monthly_credit_usd) == 12.0
    assert after.overage_action == "warn"


@pytest.mark.asyncio
async def test_synced_quota_drives_real_enforcement(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """End-to-end: set monthly_budget=block via the UI path, push spend over
    that cap, and confirm CostGuard.preflight_check now raises -- proving the
    UI control reaches real enforcement (not a fake label)."""
    auth = await _register_and_login(client)
    CostGuard._recent_warn_emits.pop(auth["user_id"], None)

    await client.put(
        "/api/v1/settings/user",
        json={"monthly_budget": 1, "over_budget_action": "block"},
        headers=auth["headers"],
    )

    # Drive spend over the $1.00 cap directly on the quota row.
    quota = await _quota_for(db_session, auth["user_id"])
    assert quota is not None
    quota.spend_this_month_usd = 1.5
    await db_session.flush()

    guard = CostGuard(db_session)
    with pytest.raises(BudgetExceededError):
        await guard.preflight_check(
            tenant_id=auth["tenant_id"],
            estimated_cost=0.0,
            user_id=auth["user_id"],
        )


@pytest.mark.asyncio
async def test_alert_threshold_emits_early_warning(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """budget_alert_threshold fires the 'approaching budget' notification
    BEFORE the user is fully over quota."""
    auth = await _register_and_login(client)
    CostGuard._recent_warn_emits.pop(auth["user_id"], None)

    # $10 monthly cap, warn action so nothing blocks.
    await client.put(
        "/api/v1/settings/user",
        json={"monthly_budget": 10, "over_budget_action": "warn"},
        headers=auth["headers"],
    )
    # Spend $8 of $10 -> 80%. Threshold of 0.75 should fire.
    quota = await _quota_for(db_session, auth["user_id"])
    assert quota is not None
    quota.spend_this_month_usd = 8.0
    await db_session.flush()

    guard = CostGuard(db_session)
    await guard.preflight_check(
        tenant_id=auth["tenant_id"],
        estimated_cost=0.0,
        user_id=auth["user_id"],
        alert_threshold_pct=0.75,
    )

    rows = (
        await db_session.execute(
            select(Notification).where(
                Notification.user_id == auth["user_id"],
                Notification.type == "budget_alert",
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].severity == "info"
    assert "Approaching" in rows[0].title


@pytest.mark.asyncio
async def test_alert_threshold_silent_below_threshold(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """No early-warning when spend is below the chosen threshold."""
    auth = await _register_and_login(client)
    CostGuard._recent_warn_emits.pop(auth["user_id"], None)

    await client.put(
        "/api/v1/settings/user",
        json={"monthly_budget": 10, "over_budget_action": "warn"},
        headers=auth["headers"],
    )
    # Spend $3 of $10 -> 30%, below a 0.75 threshold.
    quota = await _quota_for(db_session, auth["user_id"])
    assert quota is not None
    quota.spend_this_month_usd = 3.0
    await db_session.flush()

    guard = CostGuard(db_session)
    await guard.preflight_check(
        tenant_id=auth["tenant_id"],
        estimated_cost=0.0,
        user_id=auth["user_id"],
        alert_threshold_pct=0.75,
    )

    rows = (
        await db_session.execute(
            select(Notification).where(
                Notification.user_id == auth["user_id"],
                Notification.type == "budget_alert",
            )
        )
    ).scalars().all()
    assert rows == []
