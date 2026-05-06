"""Sprint-20 PR-1 -- Google activation summary contract.

Pins:
  1. Endpoint requires auth.
  2. Returns ``ready: bool`` + ``client_configured: bool`` +
     ``blockers: list``.
  3. Empty state -> ready=False, client + both account blockers
     present.
  4. Connecting client + both accounts on all three Google services
     -> ready=True, blockers=[].
  5. Partial connection (gmail only for one account) flags missing
     drive + calendar in that account's blocker.
  6. Wrong account email connections do NOT flip the pinned account
     ready (case-insensitive match still applies).
  7. NEVER returns secrets / tokens / instance ids / counts.
"""

from __future__ import annotations

import uuid
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.connections import Connector, ConnectorInstance
from app.models.identity import Tenant, User


pytestmark = pytest.mark.asyncio


@pytest.fixture
async def seeded_tenant_user(db_session: AsyncSession) -> tuple[UUID, UUID, str]:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db_session.add(Tenant(
        id=tenant_id,
        name=f"GA s20 {tenant_id.hex[:6]}",
        slug=f"ga-s20-{tenant_id.hex[:8]}",
    ))
    await db_session.flush()
    db_session.add(User(
        id=user_id, tenant_id=tenant_id,
        email=f"{user_id.hex[:8]}@ga-s20.local",
        password_hash="$2b$12$dummy" + "x" * 50,
        role="FOUNDER", email_verified=True,
    ))
    await db_session.flush()
    token = create_access_token(
        user_id=str(user_id), tenant_id=str(tenant_id),
        role="FOUNDER", email="dev@daena.dev", display_name="Dev",
    )
    return tenant_id, user_id, token


async def _seed_google_instance(
    db_session: AsyncSession, *,
    tenant_id: UUID, user_id: UUID,
    connector_name: str, owner_email: str,
    status: str = "CONNECTED",
) -> None:
    from sqlalchemy import select
    existing = (await db_session.execute(
        select(Connector).where(Connector.name == connector_name)
    )).scalar_one_or_none()
    if existing is None:
        connector = Connector(
            id=uuid.uuid4(),
            name=connector_name,
            description=f"Test {connector_name}",
            auth_type="oauth2",
            config_schema={},
            tools=[],
        )
        db_session.add(connector)
        await db_session.flush()
    else:
        connector = existing
    db_session.add(ConnectorInstance(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        connector_id=connector.id,
        user_id=user_id,
        status=status,
        credentials={},
        owner_email=owner_email,
    ))
    await db_session.flush()


# ────────────────────────────────────────────────────────────────────


async def test_endpoint_requires_auth(client: AsyncClient):
    res = await client.get("/api/v1/connections/google-activation-summary")
    assert res.status_code in (401, 403)


async def test_empty_state_lists_client_and_both_account_blockers(
    client: AsyncClient, seeded_tenant_user, monkeypatch,
):
    _, _, token = seeded_tenant_user
    monkeypatch.setattr(
        "app.api.v1.google_setup.oauth_client_config_store.get_metadata",
        lambda slug: {"configured": False, "client_id_present": False},
    )
    res = await client.get(
        "/api/v1/connections/google-activation-summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ready"] is False
    assert body["client_configured"] is False
    roles = {b["role"] for b in body["blockers"]}
    assert "client" in roles
    assert "founder" in roles
    assert "agent" in roles


async def test_full_connection_flips_ready(
    client: AsyncClient, db_session, seeded_tenant_user, monkeypatch,
):
    tenant_id, user_id, token = seeded_tenant_user
    monkeypatch.setattr(
        "app.api.v1.google_setup.oauth_client_config_store.get_metadata",
        lambda slug: {"configured": True, "client_id_present": True},
    )
    for slug in ("gmail", "google-drive", "google-calendar"):
        await _seed_google_instance(
            db_session, tenant_id=tenant_id, user_id=user_id,
            connector_name=slug, owner_email="masoud.masoori@mas-ai.co",
        )
        await _seed_google_instance(
            db_session, tenant_id=tenant_id, user_id=user_id,
            connector_name=slug, owner_email="daena@mas-ai.co",
        )
    await db_session.commit()

    res = await client.get(
        "/api/v1/connections/google-activation-summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = res.json()
    assert body["ready"] is True
    assert body["client_configured"] is True
    assert body["blockers"] == []


async def test_partial_connection_lists_missing_providers(
    client: AsyncClient, db_session, seeded_tenant_user, monkeypatch,
):
    tenant_id, user_id, token = seeded_tenant_user
    monkeypatch.setattr(
        "app.api.v1.google_setup.oauth_client_config_store.get_metadata",
        lambda slug: {"configured": True, "client_id_present": True},
    )
    # Founder has gmail only; agent has nothing.
    await _seed_google_instance(
        db_session, tenant_id=tenant_id, user_id=user_id,
        connector_name="gmail", owner_email="masoud.masoori@mas-ai.co",
    )
    await db_session.commit()

    res = await client.get(
        "/api/v1/connections/google-activation-summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = res.json()
    assert body["ready"] is False
    by_role = {b["role"]: b for b in body["blockers"]}
    assert "founder" in by_role
    assert set(by_role["founder"]["missing"]) == {"drive", "calendar"}
    assert "agent" in by_role
    assert set(by_role["agent"]["missing"]) == {"gmail", "drive", "calendar"}


async def test_email_match_is_case_insensitive(
    client: AsyncClient, db_session, seeded_tenant_user, monkeypatch,
):
    tenant_id, user_id, token = seeded_tenant_user
    monkeypatch.setattr(
        "app.api.v1.google_setup.oauth_client_config_store.get_metadata",
        lambda slug: {"configured": True, "client_id_present": True},
    )
    for slug in ("gmail", "google-drive", "google-calendar"):
        await _seed_google_instance(
            db_session, tenant_id=tenant_id, user_id=user_id,
            connector_name=slug, owner_email="MASOUD.MASOORI@MAS-AI.CO",
        )
        await _seed_google_instance(
            db_session, tenant_id=tenant_id, user_id=user_id,
            connector_name=slug, owner_email="DAENA@MAS-AI.CO",
        )
    await db_session.commit()

    res = await client.get(
        "/api/v1/connections/google-activation-summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = res.json()
    assert body["ready"] is True


async def test_disconnected_instance_does_not_count(
    client: AsyncClient, db_session, seeded_tenant_user, monkeypatch,
):
    tenant_id, user_id, token = seeded_tenant_user
    monkeypatch.setattr(
        "app.api.v1.google_setup.oauth_client_config_store.get_metadata",
        lambda slug: {"configured": True, "client_id_present": True},
    )
    await _seed_google_instance(
        db_session, tenant_id=tenant_id, user_id=user_id,
        connector_name="gmail", owner_email="masoud.masoori@mas-ai.co",
        status="DISCONNECTED",
    )
    await db_session.commit()

    res = await client.get(
        "/api/v1/connections/google-activation-summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = res.json()
    assert body["ready"] is False
    by_role = {b["role"]: b for b in body["blockers"]}
    assert "gmail" in by_role["founder"]["missing"]


async def test_response_carries_no_credential_keys(
    client: AsyncClient, db_session, seeded_tenant_user, monkeypatch,
):
    tenant_id, user_id, token = seeded_tenant_user
    monkeypatch.setattr(
        "app.api.v1.google_setup.oauth_client_config_store.get_metadata",
        lambda slug: {"configured": True, "client_id_present": True},
    )
    await _seed_google_instance(
        db_session, tenant_id=tenant_id, user_id=user_id,
        connector_name="gmail", owner_email="masoud.masoori@mas-ai.co",
    )
    await db_session.commit()

    res = await client.get(
        "/api/v1/connections/google-activation-summary",
        headers={"Authorization": f"Bearer {token}"},
    )
    body_text = res.text
    for forbidden in (
        '"access_token"', '"refresh_token"', '"id_token"',
        '"credentials":', '"client_secret":',
        '"instance_id"', "ya29.", "1//0e",
    ):
        assert forbidden not in body_text, (
            f"forbidden token-shaped string {forbidden!r} in response"
        )


# ────────────────────────────────────────────────────────────────────
# Probe-result next_action surface
# ────────────────────────────────────────────────────────────────────


def test_probe_result_carries_next_action_for_all_statuses():
    """Each readiness status maps to a non-empty operator-facing
    next_action string. A regression that adds a new status without
    next_action coverage gets caught here."""
    from app.services.google_readiness_test import (
        _NEXT_ACTIONS, _classify_response, _next_action_for_status,
    )

    expected = {
        "connected", "expired", "insufficient_scope",
        "failed", "not_connected",
    }
    assert set(_NEXT_ACTIONS) == expected
    for status in expected:
        text = _next_action_for_status(status)
        assert isinstance(text, str) and len(text) > 0
        # Must not leak a URL or token (paranoia: this string lands in UI).
        assert "ya29." not in text
        assert "Bearer " not in text
