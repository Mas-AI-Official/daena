"""PR-GOOGLE-OAUTH-LIVE-SETUP-HELPERS (Sprint-10 PR-1, 2026-05-05).

Pins the contract for the new GET /connections/google-setup-status
endpoint that powers the GoogleAccountSetupGuide live checklist.

Hard guarantees:

  1. Endpoint requires auth (401 without bearer).
  2. Returns the four-step status payload with the pinned account
     emails (masoud.masoori@mas-ai.co, daena@mas-ai.co).
  3. ``founder_account.connected`` is True iff a CONNECTED
     ConnectorInstance with owner_email matching the founder email
     (case-insensitive) exists for this tenant.
  4. ``agent_account.connected`` follows the same rule for daena@.
  5. ``ready`` is True ONLY when client_configured AND both accounts
     are connected.
  6. Endpoint NEVER returns access tokens, refresh tokens, or any
     credential payload -- only booleans + emails + connected service
     slugs.
  7. The frontend pins the two pinned emails so a future copy refactor
     cannot silently drop one of the two accounts.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.connections import Connector, ConnectorInstance
from app.models.identity import Tenant, User


pytestmark = pytest.mark.asyncio


# ──────────────────────────────────────────────────────────────────
# Per-file seeded fixture (mirrors the rest of the test suite).
# ──────────────────────────────────────────────────────────────────


@pytest.fixture
async def seeded_tenant_user(db_session: AsyncSession) -> tuple[UUID, UUID, str]:
    tenant_id = uuid.uuid4()
    user_id = uuid.uuid4()
    db_session.add(Tenant(
        id=tenant_id,
        name=f"GS s10 {tenant_id.hex[:6]}",
        slug=f"gs-s10-{tenant_id.hex[:8]}",
    ))
    await db_session.flush()
    db_session.add(User(
        id=user_id, tenant_id=tenant_id,
        email=f"{user_id.hex[:8]}@gs-s10.local",
        password_hash="$2b$12$dummydummydummydummydummydummydummydummydummydummydu",
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
    """Seed a Connector + ConnectorInstance pair so the endpoint sees
    the pinned account as 'connected'. Uses minimal fields -- no
    credentials body (the endpoint never reads it).

    The Connectors table has a unique-name constraint and tests share
    the engine, so we get-or-create the Connector row to stay idempotent
    across tests in this file."""
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


# ──────────────────────────────────────────────────────────────────
# 1. Auth gate
# ──────────────────────────────────────────────────────────────────


async def test_endpoint_requires_auth(client: AsyncClient):
    res = await client.get("/api/v1/connections/google-setup-status")
    assert res.status_code in (401, 403), res.status_code


# ──────────────────────────────────────────────────────────────────
# 2. Empty-state response
# ──────────────────────────────────────────────────────────────────


async def test_empty_state_returns_pinned_emails_and_not_ready(
    client: AsyncClient, seeded_tenant_user, monkeypatch,
):
    _, _, token = seeded_tenant_user
    # Force the OAuth client to "not configured" for the empty-state.
    monkeypatch.setattr(
        "app.api.v1.google_setup.oauth_client_config_store.get_metadata",
        lambda slug: {"configured": False, "client_id_present": False},
    )
    res = await client.get(
        "/api/v1/connections/google-setup-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["client_configured"] is False
    assert body["founder_account"]["email"] == "masoud.masoori@mas-ai.co"
    assert body["founder_account"]["connected"] is False
    assert body["agent_account"]["email"] == "daena@mas-ai.co"
    assert body["agent_account"]["connected"] is False
    assert body["ready"] is False


# ──────────────────────────────────────────────────────────────────
# 3. Account-presence detection
# ──────────────────────────────────────────────────────────────────


async def test_founder_connection_flips_step_2(
    client: AsyncClient, db_session, seeded_tenant_user, monkeypatch,
):
    tenant_id, user_id, token = seeded_tenant_user
    monkeypatch.setattr(
        "app.api.v1.google_setup.oauth_client_config_store.get_metadata",
        lambda slug: {"configured": True, "client_id_present": True},
    )
    await _seed_google_instance(
        db_session,
        tenant_id=tenant_id, user_id=user_id,
        connector_name="gmail",
        owner_email="masoud.masoori@mas-ai.co",
    )
    await db_session.commit()
    res = await client.get(
        "/api/v1/connections/google-setup-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = res.json()
    assert body["founder_account"]["connected"] is True
    assert body["founder_account"]["instance_id"] is not None
    assert "gmail" in body["founder_account"]["connected_services"]
    assert body["agent_account"]["connected"] is False
    # Client configured + 1 of 2 accounts -> not ready yet.
    assert body["ready"] is False


async def test_agent_connection_flips_step_3(
    client: AsyncClient, db_session, seeded_tenant_user, monkeypatch,
):
    tenant_id, user_id, token = seeded_tenant_user
    monkeypatch.setattr(
        "app.api.v1.google_setup.oauth_client_config_store.get_metadata",
        lambda slug: {"configured": True, "client_id_present": True},
    )
    await _seed_google_instance(
        db_session,
        tenant_id=tenant_id, user_id=user_id,
        connector_name="google-drive",
        owner_email="daena@mas-ai.co",
    )
    await db_session.commit()
    res = await client.get(
        "/api/v1/connections/google-setup-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = res.json()
    assert body["agent_account"]["connected"] is True
    assert "google-drive" in body["agent_account"]["connected_services"]
    assert body["founder_account"]["connected"] is False


async def test_email_match_is_case_insensitive(
    client: AsyncClient, db_session, seeded_tenant_user, monkeypatch,
):
    """Google sometimes returns the user's email with a different
    case than the catalog's pinned value. Match case-insensitively
    so the operator isn't told they need to reconnect."""
    tenant_id, user_id, token = seeded_tenant_user
    monkeypatch.setattr(
        "app.api.v1.google_setup.oauth_client_config_store.get_metadata",
        lambda slug: {"configured": True, "client_id_present": True},
    )
    await _seed_google_instance(
        db_session,
        tenant_id=tenant_id, user_id=user_id,
        connector_name="gmail",
        owner_email="MASOUD.MASOORI@MAS-AI.CO",  # uppercase-as-stored
    )
    await db_session.commit()
    res = await client.get(
        "/api/v1/connections/google-setup-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = res.json()
    assert body["founder_account"]["connected"] is True


async def test_ready_only_when_both_connected_and_client_configured(
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
    await _seed_google_instance(
        db_session, tenant_id=tenant_id, user_id=user_id,
        connector_name="google-calendar", owner_email="daena@mas-ai.co",
    )
    await db_session.commit()
    res = await client.get(
        "/api/v1/connections/google-setup-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = res.json()
    assert body["founder_account"]["connected"] is True
    assert body["agent_account"]["connected"] is True
    assert body["client_configured"] is True
    assert body["ready"] is True


async def test_disconnected_instance_does_not_count_as_connected(
    client: AsyncClient, db_session, seeded_tenant_user, monkeypatch,
):
    """A row that exists but is DISCONNECTED (operator clicked
    Disconnect, or refresh failed) must NOT be counted as connected."""
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
        "/api/v1/connections/google-setup-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    body = res.json()
    assert body["founder_account"]["connected"] is False


# ──────────────────────────────────────────────────────────────────
# 4. No secret leakage
# ──────────────────────────────────────────────────────────────────


async def test_response_carries_no_credential_keys(
    client: AsyncClient, db_session, seeded_tenant_user, monkeypatch,
):
    """Defense-in-depth: the response body must contain none of the
    credential field names. A regression that adds a token field to
    the dataclass + the dict gets caught here."""
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
        "/api/v1/connections/google-setup-status",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Defense-in-depth: forbid any field that would carry a value
    # (the metadata field "client_secret_present" is a bool indicator
    # and NOT a leak, so we check value-shaped field names + the
    # well-known prefixes a vendor token would carry).
    body_text = res.text
    forbidden_fields = (
        '"access_token"', '"refresh_token"', '"id_token"',
        '"credentials":', '"client_secret":', '"bearer ',
    )
    for forbidden in forbidden_fields:
        assert forbidden not in body_text, (
            f"forbidden token-shaped string {forbidden!r} found in response"
        )
    # Belt-and-suspenders: well-known token prefixes / shapes.
    for prefix in ("ya29.", "1//0e", "Bearer "):
        assert prefix not in body_text


# ──────────────────────────────────────────────────────────────────
# 5. Frontend source-grep pins the two emails
# ──────────────────────────────────────────────────────────────────


def test_frontend_setup_guide_pins_both_emails():
    src = (
        Path(__file__).resolve().parents[1].parent
        / "frontend" / "src" / "pages" / "connections"
        / "GoogleAccountSetupGuide.tsx"
    ).read_text(encoding="utf-8")
    assert "masoud.masoori@mas-ai.co" in src
    assert "daena@mas-ai.co" in src
    # Live checklist test-ids must be present so a future redesign
    # cannot silently drop the live wiring.
    for testid in (
        "google-setup-checklist", "google-step-client",
        "google-step-founder", "google-step-agent", "google-step-ready",
    ):
        assert testid in src, f"missing test-id {testid!r}"


def test_frontend_hook_pins_relative_endpoint():
    """Hook must hit the relative API path so it works in dev (Vite
    proxy) and prod (reverse proxy). Same lesson as Sprint-9 PR-4's
    backend-health fix."""
    src = (
        Path(__file__).resolve().parents[1].parent
        / "frontend" / "src" / "hooks" / "useGoogleSetupStatus.ts"
    ).read_text(encoding="utf-8")
    assert "/connections/google-setup-status" in src
    # Must NOT use an absolute http://... URL.
    assert "http://127.0.0.1" not in src
    assert "http://localhost" not in src
