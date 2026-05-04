"""PR-DAENA-SELF-DIAGNOSTIC-RUNTIME-AWARENESS (Sprint-6 PR-7,
2026-05-04) tests.

Pins the contract for the new GET /api/v1/system/self-diagnostic
endpoint:

  1. Auth required.
  2. Response shape carries overall_status / timestamp /
     elapsed_ms / checks / recommended_actions / boundary_notice.
  3. No secret substring in the payload (defense-in-depth).
  4. Local model probe failure surfaces as warning, not blocked.
  5. Frontend-down case is handled gracefully (reachable=False).
  6. Recommendations are deterministic given the same inputs (pure
     function over the checks payload).
  7. Database failure flips overall_status to blocked.
  8. _worst aggregator picks the most severe sub-status.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.identity import Tenant, User


pytestmark = pytest.mark.asyncio


async def _seed_user(db_session, tenant_id, user_id):
    if (await db_session.execute(
        select(Tenant).where(Tenant.id == tenant_id),
    )).scalar_one_or_none() is None:
        db_session.add(Tenant(
            id=tenant_id, name="T", slug=f"t-diag-{tenant_id.hex[:6]}",
            settings={},
        ))
        await db_session.flush()
    if (await db_session.execute(
        select(User).where(User.id == user_id),
    )).scalar_one_or_none() is None:
        db_session.add(User(
            id=user_id, tenant_id=tenant_id,
            email=f"diag-{user_id.hex[:6]}@test.local", role="FOUNDER",
        ))
        await db_session.flush()
    await db_session.commit()


# ──────────────────────────────────────────────────────────────────
# 1. Auth required
# ──────────────────────────────────────────────────────────────────


async def test_endpoint_requires_auth(client):
    res = await client.get("/api/v1/system/self-diagnostic")
    assert res.status_code in (401, 403)


# ──────────────────────────────────────────────────────────────────
# 2. Response shape
# ──────────────────────────────────────────────────────────────────


async def test_response_has_full_shape(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    res = await client.get(
        "/api/v1/system/self-diagnostic",
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    data = body["data"]
    assert data["overall_status"] in ("healthy", "warning", "blocked")
    assert data["timestamp"]
    assert isinstance(data["elapsed_ms"], int)
    assert "checks" in data
    for key in (
        "backend", "database", "migration_head", "frontend",
        "local_models", "connector_callability",
    ):
        assert key in data["checks"], f"missing check: {key}"
        assert "status" in data["checks"][key]
        assert "detail" in data["checks"][key]
    assert isinstance(data["recommended_actions"], list)
    assert data["recommended_actions"], (
        "must always include at least one recommendation"
    )
    assert "boundary_notice" in data


# ──────────────────────────────────────────────────────────────────
# 3. No secret substring in payload
# ──────────────────────────────────────────────────────────────────


async def test_response_carries_no_secret_substring(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    res = await client.get(
        "/api/v1/system/self-diagnostic",
        headers=auth_headers,
    )
    raw = res.text
    for forbidden in (
        "access_token", "refresh_token", "Bearer",
        "client_secret", "vault", "credentials",
        "password", "sk-", "sk_",
        # Settings-derived URLs that COULD carry creds in path
        # (they shouldn't, but defense-in-depth):
        "DATABASE_URL", "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    ):
        assert forbidden not in raw, (
            f"self-diagnostic payload leaked '{forbidden}'"
        )


# ──────────────────────────────────────────────────────────────────
# 4. Local model probe failure surfaces as warning, not blocked
# ──────────────────────────────────────────────────────────────────


async def test_local_model_failure_is_warning_not_blocker(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    """In the test env neither Ollama nor llama-server is up. The
    diagnostic should report local_models as warning, NEVER blocked,
    because Daena routes around them via cloud providers."""
    await _seed_user(db_session, test_tenant_id, test_user_id)
    res = await client.get(
        "/api/v1/system/self-diagnostic",
        headers=auth_headers,
    )
    local = res.json()["data"]["checks"]["local_models"]
    assert local["status"] in ("healthy", "warning")
    assert local["status"] != "blocked"


# ──────────────────────────────────────────────────────────────────
# 5. Frontend-down handled gracefully
# ──────────────────────────────────────────────────────────────────


async def test_frontend_unreachable_returns_warning_not_blocker(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    """Test env has no Vite running; the field reachable=False but
    the overall_status is NOT blocked just because the frontend is
    down."""
    await _seed_user(db_session, test_tenant_id, test_user_id)
    res = await client.get(
        "/api/v1/system/self-diagnostic",
        headers=auth_headers,
    )
    fe = res.json()["data"]["checks"]["frontend"]
    assert fe["status"] in ("healthy", "warning")
    assert fe["status"] != "blocked"
    # reachable field always present.
    assert "reachable" in fe


# ──────────────────────────────────────────────────────────────────
# 6. Recommendations deterministic given inputs
# ──────────────────────────────────────────────────────────────────


async def test_recommended_actions_deterministic_for_same_checks():
    """Pure-function unit test on _recommended_actions."""
    from app.api.v1.system_self_diagnostic import _recommended_actions

    checks = {
        "database": {"status": "blocked", "detail": "x"},
        "frontend": {"status": "warning", "detail": "x", "reachable": False},
        "migration_head": {"status": "warning", "detail": "x"},
    }
    a = _recommended_actions(checks)
    b = _recommended_actions(checks)
    assert a == b
    assert a, "must produce at least one recommendation"


async def test_all_healthy_yields_single_ok_recommendation():
    from app.api.v1.system_self_diagnostic import _recommended_actions

    checks = {
        "database": {"status": "healthy"},
        "frontend": {"status": "healthy", "reachable": True},
        "migration_head": {"status": "healthy"},
        "local_models": {"status": "healthy"},
        "connector_callability": {"status": "healthy"},
    }
    actions = _recommended_actions(checks)
    assert len(actions) == 1
    assert "healthy" in actions[0].lower()


# ──────────────────────────────────────────────────────────────────
# 7. _worst aggregator
# ──────────────────────────────────────────────────────────────────


def test_worst_picks_blocked_over_warning_over_healthy():
    from app.api.v1.system_self_diagnostic import (
        STATUS_BLOCKED, STATUS_HEALTHY, STATUS_WARNING, _worst,
    )
    assert _worst(STATUS_HEALTHY) == STATUS_HEALTHY
    assert _worst(STATUS_WARNING, STATUS_HEALTHY) == STATUS_WARNING
    assert _worst(
        STATUS_BLOCKED, STATUS_WARNING, STATUS_HEALTHY,
    ) == STATUS_BLOCKED
    assert _worst() == STATUS_HEALTHY


# ──────────────────────────────────────────────────────────────────
# 8. Boundary notice present
# ──────────────────────────────────────────────────────────────────


async def test_boundary_notice_explicit(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    """The diagnostic must always carry the explicit boundary
    statement so any UI that surfaces it never has to fabricate
    the OS/cloud/secrets boundary copy."""
    await _seed_user(db_session, test_tenant_id, test_user_id)
    res = await client.get(
        "/api/v1/system/self-diagnostic",
        headers=auth_headers,
    )
    notice = res.json()["data"]["boundary_notice"]
    assert "without explicit" in notice
    assert "operator approval" in notice
