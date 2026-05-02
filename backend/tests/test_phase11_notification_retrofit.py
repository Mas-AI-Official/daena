"""Phase 11 PR-S2.1 — pin the in-app notification retrofits.

PR-S2 shipped the NotificationService.emit primitive + the test
endpoint. PR-S2.1 wires three existing services to call emit at the
right moments:

* ``ExecutionService._background_run`` -> ``task_complete`` row on
  successful task completion.
* ``CostGuard.preflight_check`` -> ``budget_alert`` row on personal
  quota breach with ``action=warn``/``allow_overage`` (with 60-min
  per-user dedup so a long chat session doesn't spam).
* ``ApprovalService.reject`` -> ``governance_rejection`` row to the
  user whose request was rejected (NOT the approver).

Two paths were intentionally NOT wired:
* heartbeat — daemon is system-wide, no per-user fan-out point.
* runtime_disconnect — health_tracker has no tenant_id/user_id in
  scope.
See PHASE_11_NOTIFICATION_RETROFIT_REPORT.md §3 for the full rationale.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.services.cost_guard import CostGuard
from app.services.notification_service import NotificationService


async def _register_and_login(client: AsyncClient) -> dict[str, Any]:
    """Register + login → real tenant + user → real headers + ids."""
    unique = uuid.uuid4().hex[:8]
    email = f"retrofit-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Retrofit Tester",
            "tenant_name": f"RetrofitOrg-{unique}",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    data = login_resp.json()["data"]
    user_obj = data["user"]
    user_id_raw = (
        user_obj.get("id") or user_obj.get("user_id") or user_obj.get("sub")
    )
    return {
        "headers": {"Authorization": f"Bearer {data['access_token']}"},
        "user_id": uuid.UUID(user_id_raw),
        "tenant_id": uuid.UUID(user_obj["tenant_id"]),
    }


async def _set_user_setting(
    client: AsyncClient, headers: dict[str, str], key: str, value: Any,
) -> None:
    resp = await client.put(
        "/api/v1/settings/user", json={key: value}, headers=headers,
    )
    assert resp.status_code == 200, resp.text


async def _wait_for_task_complete(
    client: AsyncClient, headers: dict[str, str],
    task_id: str, max_wait_s: float = 6.0,
) -> dict:
    """Poll /tasks/{id} until status is COMPLETED or timeout."""
    deadline = time.monotonic() + max_wait_s
    while time.monotonic() < deadline:
        resp = await client.get(
            f"/api/v1/execution/tasks/{task_id}", headers=headers,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()["data"]
        if body["status"] == "COMPLETED":
            return body
        await asyncio.sleep(0.3)
    pytest.fail(f"Task {task_id} did not complete within {max_wait_s}s")


# ---------------------------------------------------------------------------
# task_complete retrofit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_complete_emits_notification_when_enabled(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """Default state -> task completion lands a `task_complete` row."""
    auth = await _register_and_login(client)

    create_resp = await client.post(
        "/api/v1/execution/tasks",
        json={"name": "Notif-on completion", "description": "Phase11 PR-S2.1"},
        headers=auth["headers"],
    )
    task_id = create_resp.json()["data"]["id"]

    run_resp = await client.post(
        f"/api/v1/execution/tasks/{task_id}/run", headers=auth["headers"],
    )
    assert run_resp.status_code == 200

    await _wait_for_task_complete(client, auth["headers"], task_id)

    # Look up the user's notifications via the API (not direct DB) so we
    # exercise the same surface the bell uses.
    notifs_resp = await client.get(
        "/api/v1/notifications?limit=20", headers=auth["headers"],
    )
    assert notifs_resp.status_code == 200
    rows = notifs_resp.json()["data"]
    completed_rows = [r for r in rows if r["type"] == "task_complete"]
    assert len(completed_rows) == 1, (
        f"Expected exactly 1 task_complete row, got {len(completed_rows)}"
    )
    row = completed_rows[0]
    assert row["severity"] == "success"
    assert row["source"] == "execution_service.background_run"
    assert "Notif-on completion" in row["title"]


@pytest.mark.asyncio
async def test_task_complete_suppressed_when_flag_off(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """notif_task_complete=false -> NO task_complete row appears."""
    auth = await _register_and_login(client)
    await _set_user_setting(
        client, auth["headers"], "notif_task_complete", False,
    )

    create_resp = await client.post(
        "/api/v1/execution/tasks",
        json={"name": "Should not notify"},
        headers=auth["headers"],
    )
    task_id = create_resp.json()["data"]["id"]
    await client.post(
        f"/api/v1/execution/tasks/{task_id}/run", headers=auth["headers"],
    )
    await _wait_for_task_complete(client, auth["headers"], task_id)

    notifs_resp = await client.get(
        "/api/v1/notifications?limit=20", headers=auth["headers"],
    )
    rows = notifs_resp.json()["data"]
    completed_rows = [r for r in rows if r["type"] == "task_complete"]
    assert completed_rows == [], (
        "task_complete row landed despite flag=false — gate broken"
    )


# ---------------------------------------------------------------------------
# governance_rejection retrofit
# ---------------------------------------------------------------------------


async def _create_pending_governance_request(
    db: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID,
) -> uuid.UUID:
    """Insert a GoaRequest with PENDING status directly via ORM.

    The /governance routes are typically internal (not user-facing
    create), so we exercise the service primitive (ApprovalService.reject)
    after seeding a request row.
    """
    from app.models.governance import GoaRequest
    req = GoaRequest(
        tenant_id=tenant_id,
        user_id=user_id,
        action_type="test.dangerous_action",
        action_params={"x": 1},
        risk_level="HIGH",
        governance_tier=3,
        status="PENDING",
    )
    db.add(req)
    await db.flush()
    await db.refresh(req)
    return req.id


@pytest.mark.asyncio
async def test_governance_rejection_emits_notification_to_requester(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """Reject a request -> requester (NOT approver) gets a row."""
    requester = await _register_and_login(client)
    approver = await _register_and_login(client)  # different user, same shape

    request_id = await _create_pending_governance_request(
        db_session,
        tenant_id=requester["tenant_id"],
        user_id=requester["user_id"],
    )

    from app.services.approval import ApprovalService
    await ApprovalService(db_session).reject(
        request_id=request_id,
        tenant_id=requester["tenant_id"],
        decided_by=approver["user_id"],
        reason="Not safe in production",
    )
    await db_session.commit()

    # The requester should have a governance_rejection row.
    rows_req = (
        await db_session.execute(
            select(Notification).where(
                Notification.user_id == requester["user_id"],
                Notification.type == "governance_rejection",
            )
        )
    ).scalars().all()
    assert len(rows_req) == 1
    assert rows_req[0].title == "Action rejected: test.dangerous_action"
    assert "Not safe in production" in rows_req[0].message
    assert rows_req[0].source == "approval.reject"
    assert rows_req[0].severity == "warning"

    # The approver MUST NOT receive a copy (different user).
    rows_app = (
        await db_session.execute(
            select(Notification).where(
                Notification.user_id == approver["user_id"],
                Notification.type == "governance_rejection",
            )
        )
    ).scalars().all()
    assert rows_app == [], "Approver should not receive a copy of their own decision"


@pytest.mark.asyncio
async def test_governance_rejection_suppressed_when_flag_off(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """notif_gov_reject=false -> requester gets NO governance_rejection row."""
    requester = await _register_and_login(client)
    approver = await _register_and_login(client)
    await _set_user_setting(
        client, requester["headers"], "notif_gov_reject", False,
    )

    request_id = await _create_pending_governance_request(
        db_session,
        tenant_id=requester["tenant_id"],
        user_id=requester["user_id"],
    )

    from app.services.approval import ApprovalService
    await ApprovalService(db_session).reject(
        request_id=request_id,
        tenant_id=requester["tenant_id"],
        decided_by=approver["user_id"],
        reason="quiet rejection",
    )
    await db_session.commit()

    rows = (
        await db_session.execute(
            select(Notification).where(
                Notification.user_id == requester["user_id"],
                Notification.type == "governance_rejection",
            )
        )
    ).scalars().all()
    assert rows == []


# ---------------------------------------------------------------------------
# budget_alert retrofit
# ---------------------------------------------------------------------------


async def _seed_over_quota_state(
    db: AsyncSession, *, tenant_id: uuid.UUID, user_id: uuid.UUID,
    monthly_credit: float = 1.0, action: str = "warn",
) -> None:
    """Pre-seed a UserQuota row whose spend already exceeds the limit.

    Note: cost_guard.get_user_budget_status reads
    ``quota.spend_this_month_usd`` *directly* from the UserQuota row
    (NOT a sum over UsageLedger), so we set that field explicitly.
    period_start=now keeps the daily-rollover branch from zeroing
    out our seed before preflight reads it.
    """
    from datetime import datetime, timezone

    from app.models.financial import UserQuota
    db.add(UserQuota(
        tenant_id=tenant_id,
        user_id=user_id,
        plan_tier="FREE",
        monthly_credit_usd=monthly_credit,
        spend_this_month_usd=monthly_credit + 0.5,  # over by $0.50
        daily_credit_usd=None,  # disable daily check
        spend_today_usd=0,
        overage_action=action,
        period_start=datetime.now(timezone.utc),
    ))
    await db.flush()


@pytest.mark.asyncio
async def test_budget_alert_emits_on_warn_action(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """User over personal quota with action=warn -> budget_alert row."""
    auth = await _register_and_login(client)
    # Reset the process-level dedup so test ordering can't suppress us.
    CostGuard._recent_warn_emits.pop(auth["user_id"], None)
    await _seed_over_quota_state(
        db_session,
        tenant_id=auth["tenant_id"],
        user_id=auth["user_id"],
        monthly_credit=1.0,
        action="warn",
    )

    guard = CostGuard(db_session)
    await guard.preflight_check(
        tenant_id=auth["tenant_id"],
        estimated_cost=0.0,  # allow it through; we only want the warn branch
        user_id=auth["user_id"],
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
    assert rows[0].severity == "warning"
    assert rows[0].source == "cost_guard.preflight_check"


@pytest.mark.asyncio
async def test_budget_alert_dedup_within_window(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """Repeated preflight calls within the 60-min window -> still ONE row.

    Pins the spam-protection dedup. A long chat session must not write
    one budget_alert row per LLM call.
    """
    auth = await _register_and_login(client)
    CostGuard._recent_warn_emits.pop(auth["user_id"], None)
    await _seed_over_quota_state(
        db_session,
        tenant_id=auth["tenant_id"],
        user_id=auth["user_id"],
        monthly_credit=1.0,
        action="warn",
    )

    guard = CostGuard(db_session)
    for _ in range(5):
        await guard.preflight_check(
            tenant_id=auth["tenant_id"],
            estimated_cost=0.0,
            user_id=auth["user_id"],
        )

    rows = (
        await db_session.execute(
            select(Notification).where(
                Notification.user_id == auth["user_id"],
                Notification.type == "budget_alert",
            )
        )
    ).scalars().all()
    assert len(rows) == 1, (
        f"Dedup broken: 5 preflights produced {len(rows)} rows in the window"
    )


@pytest.mark.asyncio
async def test_budget_alert_suppressed_when_flag_off(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """notif_budget_alert=false -> no row even on quota breach."""
    auth = await _register_and_login(client)
    CostGuard._recent_warn_emits.pop(auth["user_id"], None)
    await _set_user_setting(
        client, auth["headers"], "notif_budget_alert", False,
    )
    await _seed_over_quota_state(
        db_session,
        tenant_id=auth["tenant_id"],
        user_id=auth["user_id"],
        monthly_credit=1.0,
        action="warn",
    )

    guard = CostGuard(db_session)
    await guard.preflight_check(
        tenant_id=auth["tenant_id"],
        estimated_cost=0.0,
        user_id=auth["user_id"],
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
