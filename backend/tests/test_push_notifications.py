"""Tests for the G6 Web Push mirror (Phase 4 item 12, 2026-07-02).

Covers the whole seam without any network or pywebpush install:

* ``WebPushChannel.available()`` is False out of the box (default OFF).
* ``_PUSH_TYPES`` excludes the spam-trainers (heartbeat, system_info).
* FOUNDER-only subscribe/unsubscribe; status open to any authed user.
* Endpoint-alone upsert (create, re-register, Rule 2 resurrect, device
  reassignment across users).
* https-only endpoint validation (anti-SSRF).
* emit mirrors push-worthy types through the channel with the locked
  payload + subscription shapes; non-push types and ``notif_push=False``
  users skip the mirror while the in-app row still lands.
* gone=True soft-revokes the subscription; a raising channel never
  breaks emit (fail-open contract).

Tests inject a FakeChannel via ``set_push_channel``. The two tests
that assert the UNPROVISIONED world pin it explicitly by monkeypatching
the cached settings instance: since G6 went live (2026-07-02) the dev
.env legitimately carries real VAPID keys, so the dormant state must
be constructed, never inherited from the developer's environment.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.push_subscription import PushSubscription
from app.services.notification_channels import (
    ChannelResult,
    WebPushChannel,
    set_push_channel,
)
from app.services.notification_service import _PUSH_TYPES, NotificationService


# ── Helpers (mirror test_phase11_notification_emitter.py) ──────────


async def _register_and_login(client: AsyncClient) -> dict[str, Any]:
    """Register a fresh user (FOUNDER of a fresh tenant) and log in."""
    unique = uuid.uuid4().hex[:8]
    email = f"push-{unique}@example.com"
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "SecurePass123!",
            "display_name": "Push Tester",
            "tenant_name": f"PushOrg-{unique}",
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
    client: AsyncClient, headers: dict[str, str], key: str, value: Any
) -> None:
    resp = await client.put(
        "/api/v1/settings/user", json={key: value}, headers=headers
    )
    assert resp.status_code == 200, resp.text


def _endpoint() -> str:
    return f"https://push.example.com/sub/{uuid.uuid4().hex}"


def _subscribe_body(endpoint: str) -> dict[str, Any]:
    return {
        "endpoint": endpoint,
        "keys": {"p256dh": "test-p256dh-key", "auth": "test-auth"},
        "user_agent": "pytest",
    }


class FakeChannel:
    """Duck-typed channel that records deliver calls (no network)."""

    name = "fake"

    def __init__(self) -> None:
        self.is_available = True
        self.result = ChannelResult(ok=True)
        self.exc: Exception | None = None
        self.calls: list[dict[str, Any]] = []

    def available(self) -> bool:
        return self.is_available

    async def deliver(
        self, *, subscription: dict, payload: dict
    ) -> ChannelResult:
        self.calls.append({"subscription": subscription, "payload": payload})
        if self.exc is not None:
            raise self.exc
        return self.result


@pytest.fixture
def fake_channel():
    """Install a FakeChannel for the test, always restore the real one."""
    fake = FakeChannel()
    set_push_channel(fake)  # type: ignore[arg-type]
    yield fake
    set_push_channel(None)


# ── Channel + type-gate unit tests ─────────────────────────────────


@pytest.mark.asyncio
async def test_webpush_channel_unavailable_by_default(monkeypatch):
    """Real channel reports unavailable in the config-default state
    (flag off). Pinned explicitly -- the dev .env may carry live keys."""
    monkeypatch.setattr(get_settings(), "push_alerts_enabled", False)
    assert WebPushChannel().available() is False


def test_push_types_exclude_spam_trainers():
    """heartbeat/system_info must never push -- they would train the
    founder to ignore the channel."""
    assert "heartbeat" not in _PUSH_TYPES
    assert "system_info" not in _PUSH_TYPES
    assert _PUSH_TYPES == frozenset({
        "task_complete",
        "budget_alert",
        "governance_rejection",
        "runtime_disconnect",
        "privacy_blocked",
    })


# ── Endpoint auth + validation ─────────────────────────────────────


@pytest.mark.asyncio
async def test_subscribe_requires_founder(client: AsyncClient):
    """Non-FOUNDER roles get 403 on subscribe/unsubscribe, 200 on status."""
    auth = await _register_and_login(client)
    operator_token = create_access_token(
        user_id=str(auth["user_id"]),
        tenant_id=str(auth["tenant_id"]),
        role="OPERATOR",
    )
    op_headers = {"Authorization": f"Bearer {operator_token}"}

    sub = await client.post(
        "/api/v1/notifications/push/subscribe",
        json=_subscribe_body(_endpoint()),
        headers=op_headers,
    )
    assert sub.status_code == 403, sub.text

    unsub = await client.post(
        "/api/v1/notifications/push/unsubscribe",
        json={"endpoint": _endpoint()},
        headers=op_headers,
    )
    assert unsub.status_code == 403, unsub.text

    # Status stays readable so the Settings UI renders honestly (Rule 17).
    status = await client.get(
        "/api/v1/notifications/push/status", headers=op_headers
    )
    assert status.status_code == 200, status.text


@pytest.mark.asyncio
async def test_subscribe_rejects_non_https_endpoint(client: AsyncClient):
    """http:// endpoints are a client bug or an SSRF attempt -> 422."""
    auth = await _register_and_login(client)
    body = _subscribe_body(_endpoint())
    body["endpoint"] = "http://evil.example.com/collect"
    resp = await client.post(
        "/api/v1/notifications/push/subscribe",
        json=body,
        headers=auth["headers"],
    )
    assert resp.status_code == 422, resp.text


@pytest.mark.asyncio
async def test_subscribe_creates_upserts_and_resurrects(
    client: AsyncClient, db_session: AsyncSession
):
    """Same endpoint: first call creates, repeats update in place, and a
    soft-revoked row resurrects (Rule 2: no deletes)."""
    auth = await _register_and_login(client)
    endpoint = _endpoint()

    first = await client.post(
        "/api/v1/notifications/push/subscribe",
        json=_subscribe_body(endpoint),
        headers=auth["headers"],
    )
    assert first.status_code == 200, first.text
    assert first.json()["created"] is True

    second = await client.post(
        "/api/v1/notifications/push/subscribe",
        json=_subscribe_body(endpoint),
        headers=auth["headers"],
    )
    assert second.status_code == 200, second.text
    assert second.json()["created"] is False

    unsub = await client.post(
        "/api/v1/notifications/push/unsubscribe",
        json={"endpoint": endpoint},
        headers=auth["headers"],
    )
    assert unsub.status_code == 200, unsub.text

    third = await client.post(
        "/api/v1/notifications/push/subscribe",
        json=_subscribe_body(endpoint),
        headers=auth["headers"],
    )
    assert third.status_code == 200, third.text
    assert third.json()["created"] is False

    db_session.expire_all()
    rows = (
        (
            await db_session.execute(
                select(PushSubscription).where(
                    PushSubscription.endpoint == endpoint
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].revoked_at is None


@pytest.mark.asyncio
async def test_subscribe_reassigns_endpoint_across_users(
    client: AsyncClient, db_session: AsyncSession
):
    """Push endpoints are per browser profile, not per account: a second
    user registering the same endpoint takes ownership in place."""
    first_user = await _register_and_login(client)
    second_user = await _register_and_login(client)
    endpoint = _endpoint()

    resp_a = await client.post(
        "/api/v1/notifications/push/subscribe",
        json=_subscribe_body(endpoint),
        headers=first_user["headers"],
    )
    assert resp_a.json()["created"] is True

    resp_b = await client.post(
        "/api/v1/notifications/push/subscribe",
        json=_subscribe_body(endpoint),
        headers=second_user["headers"],
    )
    assert resp_b.status_code == 200, resp_b.text
    assert resp_b.json()["created"] is False

    db_session.expire_all()
    rows = (
        (
            await db_session.execute(
                select(PushSubscription).where(
                    PushSubscription.endpoint == endpoint
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].user_id == second_user["user_id"]
    assert rows[0].tenant_id == second_user["tenant_id"]


@pytest.mark.asyncio
async def test_unsubscribe_revokes_and_404s_unknown(
    client: AsyncClient, db_session: AsyncSession
):
    auth = await _register_and_login(client)
    endpoint = _endpoint()
    await client.post(
        "/api/v1/notifications/push/subscribe",
        json=_subscribe_body(endpoint),
        headers=auth["headers"],
    )

    resp = await client.post(
        "/api/v1/notifications/push/unsubscribe",
        json={"endpoint": endpoint},
        headers=auth["headers"],
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["revoked"] == 1

    db_session.expire_all()
    row = (
        await db_session.execute(
            select(PushSubscription).where(
                PushSubscription.endpoint == endpoint
            )
        )
    ).scalar_one()
    assert row.revoked_at is not None

    # Already revoked -> scoped active-only query matches nothing.
    again = await client.post(
        "/api/v1/notifications/push/unsubscribe",
        json={"endpoint": endpoint},
        headers=auth["headers"],
    )
    assert again.status_code == 404
    assert again.json()["detail"] == "push_subscription_not_found"


# ── emit mirror behaviour ──────────────────────────────────────────


async def _subscribed_user(client: AsyncClient) -> dict[str, Any]:
    """Register a user and attach one active push subscription."""
    auth = await _register_and_login(client)
    auth["endpoint"] = _endpoint()
    resp = await client.post(
        "/api/v1/notifications/push/subscribe",
        json=_subscribe_body(auth["endpoint"]),
        headers=auth["headers"],
    )
    assert resp.status_code == 200, resp.text
    return auth


@pytest.mark.asyncio
async def test_emit_push_type_mirrors_to_channel(
    client: AsyncClient, db_session: AsyncSession, fake_channel: FakeChannel
):
    """A push-worthy emit delivers once with the locked payload +
    subscription shapes."""
    auth = await _subscribed_user(client)

    result = await NotificationService(db_session).emit(
        tenant_id=auth["tenant_id"],
        user_id=auth["user_id"],
        type="task_complete",
        title="Goal finished",
        message="Delegated goal #42 completed.",
        severity="success",
    )
    assert result["id"] is not None
    assert len(fake_channel.calls) == 1

    payload = fake_channel.calls[0]["payload"]
    assert set(payload) == {
        "type", "title", "message", "severity", "notification_id",
    }
    assert payload["type"] == "task_complete"
    assert payload["notification_id"] == result["id"]

    subscription = fake_channel.calls[0]["subscription"]
    assert subscription["endpoint"] == auth["endpoint"]
    assert set(subscription["keys"]) == {"p256dh", "auth"}


@pytest.mark.asyncio
async def test_emit_non_push_type_skips_channel(
    client: AsyncClient, db_session: AsyncSession, fake_channel: FakeChannel
):
    """system_info lands in the bell but never pushes."""
    auth = await _subscribed_user(client)

    result = await NotificationService(db_session).emit(
        tenant_id=auth["tenant_id"],
        user_id=auth["user_id"],
        type="system_info",
        title="FYI",
        message="Not push-worthy.",
        severity="info",
    )
    assert result["id"] is not None
    assert fake_channel.calls == []


@pytest.mark.asyncio
async def test_notif_push_false_suppresses_mirror_not_row(
    client: AsyncClient, db_session: AsyncSession, fake_channel: FakeChannel
):
    """Opting out of push keeps the in-app row (push is a mirror, the DB
    row is the source of truth)."""
    auth = await _subscribed_user(client)
    await _set_user_setting(client, auth["headers"], "notif_push", False)

    result = await NotificationService(db_session).emit(
        tenant_id=auth["tenant_id"],
        user_id=auth["user_id"],
        type="budget_alert",
        title="Budget at 80%",
        message="Monthly spend crossed the soft cap.",
        severity="warning",
    )
    assert result["id"] is not None
    assert fake_channel.calls == []


@pytest.mark.asyncio
async def test_gone_result_soft_revokes_subscription(
    client: AsyncClient, db_session: AsyncSession, fake_channel: FakeChannel
):
    """404/410 from the push service revokes the row so dead endpoints
    stop being paid for."""
    auth = await _subscribed_user(client)
    fake_channel.result = ChannelResult(
        ok=False, gone=True, detail="endpoint gone (410)",
    )

    result = await NotificationService(db_session).emit(
        tenant_id=auth["tenant_id"],
        user_id=auth["user_id"],
        type="runtime_disconnect",
        title="Runtime lost",
        message="Codex runtime disconnected.",
        severity="error",
    )
    assert result["id"] is not None
    assert len(fake_channel.calls) == 1

    db_session.expire_all()
    row = (
        await db_session.execute(
            select(PushSubscription).where(
                PushSubscription.endpoint == auth["endpoint"]
            )
        )
    ).scalar_one()
    assert row.revoked_at is not None


@pytest.mark.asyncio
async def test_channel_exception_never_breaks_emit(
    client: AsyncClient, db_session: AsyncSession, fake_channel: FakeChannel
):
    """Fail-open contract: a blowing-up channel must not lose the row."""
    auth = await _subscribed_user(client)
    fake_channel.exc = RuntimeError("push infrastructure on fire")

    result = await NotificationService(db_session).emit(
        tenant_id=auth["tenant_id"],
        user_id=auth["user_id"],
        type="governance_rejection",
        title="Action blocked",
        message="Governance rejected a tool call.",
        severity="error",
    )
    assert result["id"] is not None
    assert len(fake_channel.calls) == 1


# ── Status endpoint ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_push_status_reports_channel_and_devices(
    client: AsyncClient, fake_channel: FakeChannel, monkeypatch
):
    # Pin the unprovisioned world: no public key regardless of .env.
    monkeypatch.setattr(get_settings(), "vapid_public_key", "")
    auth = await _register_and_login(client)

    before = await client.get(
        "/api/v1/notifications/push/status", headers=auth["headers"]
    )
    assert before.status_code == 200, before.text
    body = before.json()
    assert body["enabled"] is True  # fake channel reports available
    assert body["public_key"] is None  # no VAPID keys provisioned
    assert body["subscriptions"] == 0

    endpoint = _endpoint()
    await client.post(
        "/api/v1/notifications/push/subscribe",
        json=_subscribe_body(endpoint),
        headers=auth["headers"],
    )
    after = await client.get(
        "/api/v1/notifications/push/status", headers=auth["headers"]
    )
    assert after.json()["subscriptions"] == 1

    fake_channel.is_available = False
    await client.post(
        "/api/v1/notifications/push/unsubscribe",
        json={"endpoint": endpoint},
        headers=auth["headers"],
    )
    final = await client.get(
        "/api/v1/notifications/push/status", headers=auth["headers"]
    )
    assert final.json()["enabled"] is False
    assert final.json()["subscriptions"] == 0
