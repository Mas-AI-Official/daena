"""NOTIF-02: durable mark-read state for in-app notifications."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient


async def _register_and_login(client: AsyncClient) -> dict[str, Any]:
    unique = uuid.uuid4().hex[:8]
    email = f"notifmr-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email, "password": "SecurePass123!",
            "display_name": "Notif MR", "tenant_name": f"NotifMR-{unique}",
        },
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "SecurePass123!"},
    )
    data = login.json()["data"]
    return {"headers": {"Authorization": f"Bearer {data['access_token']}"}}


async def _emit_test(client: AsyncClient, headers: dict) -> str:
    r = await client.post("/api/v1/notifications/test", json={}, headers=headers)
    assert r.status_code == 200, r.text
    return r.json()["data"]["id"]


@pytest.mark.asyncio
async def test_mark_read_decrements_unread_count(client: AsyncClient) -> None:
    auth = await _register_and_login(client)
    nid = await _emit_test(client, auth["headers"])

    before = await client.get("/api/v1/notifications", headers=auth["headers"])
    assert before.json()["unread_count"] >= 1

    r = await client.post(
        f"/api/v1/notifications/{nid}/read", headers=auth["headers"]
    )
    assert r.status_code == 200
    assert r.json()["marked"] == 1

    after = await client.get("/api/v1/notifications", headers=auth["headers"])
    assert after.json()["unread_count"] == before.json()["unread_count"] - 1
    # The specific row now carries a read_at timestamp.
    row = next(n for n in after.json()["data"] if n["id"] == nid)
    assert row["read_at"] is not None


@pytest.mark.asyncio
async def test_mark_read_cross_user_is_404(client: AsyncClient) -> None:
    """A user cannot mark another user's notification read (IDOR guard)."""
    owner = await _register_and_login(client)
    other = await _register_and_login(client)
    nid = await _emit_test(client, owner["headers"])

    r = await client.post(
        f"/api/v1/notifications/{nid}/read", headers=other["headers"]
    )
    assert r.status_code == 404, "cross-user mark-read must not succeed"

    # Owner's notification is still unread.
    owner_list = await client.get("/api/v1/notifications", headers=owner["headers"])
    row = next(n for n in owner_list.json()["data"] if n["id"] == nid)
    assert row["read_at"] is None


@pytest.mark.asyncio
async def test_read_all_clears_unread(client: AsyncClient) -> None:
    auth = await _register_and_login(client)
    await _emit_test(client, auth["headers"])
    await _emit_test(client, auth["headers"])

    r = await client.post("/api/v1/notifications/read-all", headers=auth["headers"])
    assert r.status_code == 200
    assert r.json()["marked"] >= 2

    after = await client.get("/api/v1/notifications", headers=auth["headers"])
    assert after.json()["unread_count"] == 0
