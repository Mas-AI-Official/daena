"""Phase 11 PR-S2 — pin the in-app notification emitter stub.

Phase 10b's settings downstream-read audit catalogued every
``users.settings.notif_*`` key as ``DEAD`` (no consumer). This test
pins the new behavior:

* ``NotificationService.emit`` writes a ``notifications`` row when the
  matching ``notif_*`` flag is True / unset.
* When the matching flag is explicitly False, the write is silently
  suppressed (returns sentinel; no DB row).
* Two event types are intentionally ungated:
  ``system_info`` and ``privacy_blocked``.
* ``GET /api/v1/notifications`` returns the user's recent rows, newest
  first, scoped to (tenant_id, user_id).
* ``POST /api/v1/notifications/test`` always lands one
  ``system_info`` row.

What this PR does NOT cover:
* External delivery (no email, no SMS, no OS push) — see report §5.
* Mark-read endpoint — punted to a follow-up PR.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.services.notification_service import NotificationService


async def _register_and_login(client: AsyncClient) -> dict[str, Any]:
    """Register + login → real tenant + user → real headers + ids."""
    unique = uuid.uuid4().hex[:8]
    email = f"notif-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Notif Tester",
            "tenant_name": f"NotifOrg-{unique}",
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
    """Toggle a single users.settings JSONB key via the canonical endpoint."""
    resp = await client.put(
        "/api/v1/settings/user", json={key: value}, headers=headers,
    )
    assert resp.status_code == 200, resp.text


# ---------------------------------------------------------------------------
# Per-event flag gate at NotificationService.emit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_emit_default_writes_row(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """No setting -> default behavior: row is written."""
    auth = await _register_and_login(client)
    svc = NotificationService(db_session)
    result = await svc.emit(
        tenant_id=auth["tenant_id"],
        user_id=auth["user_id"],
        type="task_complete",
        title="Mission complete",
        message="Outreach sent 12 drafts.",
        severity="success",
        source="test",
    )
    assert "blocked_by_setting" not in result
    assert result.get("id") is not None
    rows = (
        await db_session.execute(
            select(Notification).where(
                Notification.tenant_id == auth["tenant_id"],
                Notification.user_id == auth["user_id"],
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].type == "task_complete"
    assert rows[0].severity == "success"


@pytest.mark.asyncio
async def test_emit_disabled_flag_suppresses_row(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """notif_task_complete=false -> sentinel + no DB row."""
    auth = await _register_and_login(client)
    await _set_user_setting(
        client, auth["headers"], "notif_task_complete", False,
    )
    svc = NotificationService(db_session)
    result = await svc.emit(
        tenant_id=auth["tenant_id"],
        user_id=auth["user_id"],
        type="task_complete",
        title="Should not land",
        message="If you see this row, the gate is broken.",
    )
    assert result.get("blocked_by_setting") is True
    assert result.get("reason") == "notif_task_complete=false"
    assert result.get("id") is None
    rows = (
        await db_session.execute(
            select(Notification).where(
                Notification.tenant_id == auth["tenant_id"],
                Notification.user_id == auth["user_id"],
            )
        )
    ).scalars().all()
    assert rows == []


@pytest.mark.asyncio
async def test_emit_ungated_type_always_writes(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """system_info has no opt-out flag — always emits even if every
    notif_* setting is False (defense against accidental silencing of
    system messages)."""
    auth = await _register_and_login(client)
    # Turn EVERYTHING off
    for key in (
        "notif_desktop", "notif_task_complete", "notif_budget_alert",
        "notif_heartbeat", "notif_gov_reject", "notif_runtime_disconnect",
        "notif_sound", "notif_email", "notif_daily_digest",
    ):
        await _set_user_setting(client, auth["headers"], key, False)

    svc = NotificationService(db_session)
    result = await svc.emit(
        tenant_id=auth["tenant_id"],
        user_id=auth["user_id"],
        type="system_info",
        title="System info should land",
        message="Even when every flag is off.",
    )
    assert "blocked_by_setting" not in result
    assert result.get("id") is not None


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_test_endpoint_creates_row(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """POST /notifications/test -> one system_info row + DTO returned."""
    auth = await _register_and_login(client)
    resp = await client.post(
        "/api/v1/notifications/test",
        json={"title": "From the test", "message": "hello", "severity": "info"},
        headers=auth["headers"],
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    row = body["data"]
    assert row["type"] == "system_info"
    assert row["title"] == "From the test"
    assert row["severity"] == "info"
    assert row["source"] == "settings.notifications.test_button"
    assert row["read_at"] is None
    assert row["id"]


@pytest.mark.asyncio
async def test_get_list_returns_recent_for_user(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """GET /notifications returns recent rows scoped to current user.

    Also asserts cross-user isolation: a different user's rows must
    not leak into this user's list.
    """
    auth_a = await _register_and_login(client)
    auth_b = await _register_and_login(client)

    # User A: emit two rows via the test endpoint
    for i in range(2):
        await client.post(
            "/api/v1/notifications/test",
            json={"title": f"a-{i}", "message": f"msg-{i}"},
            headers=auth_a["headers"],
        )
    # User B: emit one row
    await client.post(
        "/api/v1/notifications/test",
        json={"title": "b-only", "message": "msg-b"},
        headers=auth_b["headers"],
    )

    # User A's listing
    resp_a = await client.get(
        "/api/v1/notifications?limit=10", headers=auth_a["headers"],
    )
    assert resp_a.status_code == 200
    rows_a = resp_a.json()["data"]
    titles_a = [r["title"] for r in rows_a]
    assert "a-0" in titles_a and "a-1" in titles_a
    assert "b-only" not in titles_a, "Cross-tenant leak!"

    # User B's listing
    resp_b = await client.get(
        "/api/v1/notifications?limit=10", headers=auth_b["headers"],
    )
    assert resp_b.status_code == 200
    rows_b = resp_b.json()["data"]
    titles_b = [r["title"] for r in rows_b]
    assert "b-only" in titles_b
    assert "a-0" not in titles_b and "a-1" not in titles_b


@pytest.mark.asyncio
async def test_get_list_unread_only_filter(
    client: AsyncClient, db_session: AsyncSession,
) -> None:
    """unread_only=true only returns rows with read_at IS NULL."""
    auth = await _register_and_login(client)
    # Emit 2 rows
    for i in range(2):
        await client.post(
            "/api/v1/notifications/test",
            json={"title": f"row-{i}", "message": "x"},
            headers=auth["headers"],
        )

    # All 2 are unread
    resp_unread = await client.get(
        "/api/v1/notifications?unread_only=true",
        headers=auth["headers"],
    )
    assert resp_unread.status_code == 200
    assert len(resp_unread.json()["data"]) == 2

    # Mark one read directly in DB (no public mark-read endpoint yet)
    from datetime import datetime, timezone
    rows = (
        await db_session.execute(
            select(Notification).where(
                Notification.user_id == auth["user_id"],
            )
        )
    ).scalars().all()
    rows[0].read_at = datetime.now(timezone.utc)
    await db_session.flush()

    resp_unread2 = await client.get(
        "/api/v1/notifications?unread_only=true",
        headers=auth["headers"],
    )
    assert resp_unread2.status_code == 200
    assert len(resp_unread2.json()["data"]) == 1
