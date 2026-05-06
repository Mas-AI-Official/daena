"""Sprint-20 PR-4 -- Send rate limit visibility endpoint contract.

Pins:
  1. GET /opportunities/send-rate-limit requires auth.
  2. Returns {today_utc, used, cap, remaining}.
  3. Reflects current state of the persistent counter.
  4. ``remaining = max(cap - used, 0)`` (never negative).
  5. Endpoint NEVER mutates the counter.
"""

from __future__ import annotations

import pytest


pytestmark = pytest.mark.asyncio


@pytest.fixture
def isolated_rate_state(tmp_path, monkeypatch):
    from app.services.outreach import send_rate_limit as srl
    monkeypatch.setattr(
        srl, "_STATE_FILE", tmp_path / ".send_rate_limit.json",
    )
    yield


async def test_returns_zero_used_for_fresh_tenant(
    isolated_rate_state, client, auth_headers,
):
    r = await client.get(
        "/api/v1/opportunities/send-rate-limit", headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert body["used"] == 0
    assert body["cap"] >= 0
    assert body["remaining"] == body["cap"]
    # today_utc is YYYY-MM-DD shape.
    assert len(body["today_utc"]) == 10
    assert body["today_utc"].count("-") == 2


async def test_remaining_decreases_after_increment(
    isolated_rate_state, client, auth_headers, test_tenant_id,
):
    from app.services.outreach.send_rate_limit import check_and_increment
    decision = check_and_increment(test_tenant_id)
    assert decision.allowed is True

    r = await client.get(
        "/api/v1/opportunities/send-rate-limit", headers=auth_headers,
    )
    body = r.json()
    assert body["used"] == 1
    assert body["remaining"] == body["cap"] - 1


async def test_remaining_clamped_at_zero(
    isolated_rate_state, client, auth_headers, test_tenant_id, monkeypatch,
):
    """If env cap is 1 and we increment twice (we'll only allow 1),
    remaining floors at 0, not negative."""
    monkeypatch.setenv("DAENA_SEND_RATE_LIMIT_PER_DAY", "1")
    from app.services.outreach.send_rate_limit import check_and_increment
    d1 = check_and_increment(test_tenant_id)
    assert d1.allowed is True
    d2 = check_and_increment(test_tenant_id)
    assert d2.allowed is False  # second refused

    r = await client.get(
        "/api/v1/opportunities/send-rate-limit", headers=auth_headers,
    )
    body = r.json()
    assert body["cap"] == 1
    assert body["used"] == 1
    assert body["remaining"] == 0


async def test_endpoint_never_mutates_counter(
    isolated_rate_state, client, auth_headers, test_tenant_id,
):
    from app.services.outreach.send_rate_limit import get_usage
    before = get_usage(test_tenant_id)
    for _ in range(3):
        await client.get(
            "/api/v1/opportunities/send-rate-limit", headers=auth_headers,
        )
    after = get_usage(test_tenant_id)
    assert after == before


async def test_requires_auth(client):
    r = await client.get("/api/v1/opportunities/send-rate-limit")
    assert r.status_code in (401, 403)
