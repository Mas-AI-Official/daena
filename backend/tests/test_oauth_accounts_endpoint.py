"""PR-CONN-FRONTEND-ACCOUNT-PROFILE-PICKER (Sprint-5 PR-2, 2026-05-03) tests
for the backend slice: ``GET /api/v1/connectors/oauth/accounts``.

Pins:

  1. Endpoint requires auth (no anonymous account enumeration).
  2. Unsupported provider -> 400 with explicit ``unsupported_provider``
     code (matches the executor's account-profile gate vocabulary).
  3. Provider known but no Connector catalog row installed -> 200 with
     empty list (honest, not error).
  4. Returns ALL ConnectorInstance rows for the (tenant, user, provider)
     triple, regardless of CONNECTED / DISCONNECTED status. The picker
     UI applies status filter; backend stays neutral.
  5. Response NEVER carries token material. Even if credentials JSONB
     contains ``access_token`` / ``refresh_token`` substrings, the
     serialized payload only exposes ``instance_id`` / ``owner_email``
     / ``status``.
  6. Tenant isolation: a different tenant's instances are NEVER returned.
"""

from __future__ import annotations

import json

import pytest


pytestmark = pytest.mark.asyncio


async def _seed_one_user_and_tenant(db_session, tenant_id, user_id):
    from sqlalchemy import select
    from app.models.identity import Tenant, User

    tenant = (
        await db_session.execute(select(Tenant).where(Tenant.id == tenant_id))
    ).scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(id=tenant_id, name="T", slug="t-acc-ep", settings={})
        db_session.add(tenant)
        await db_session.flush()
    user = (
        await db_session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        user = User(
            id=user_id, tenant_id=tenant_id,
            email="founder@test.local", role="FOUNDER",
        )
        db_session.add(user)
        await db_session.flush()
    await db_session.commit()


async def _wipe_connectors(db_session):
    from sqlalchemy import select
    from app.models.connections import Connector, ConnectorInstance
    for inst in (await db_session.execute(select(ConnectorInstance))).scalars().all():
        await db_session.delete(inst)
    for c in (await db_session.execute(select(Connector))).scalars().all():
        await db_session.delete(c)
    await db_session.commit()


async def _seed_connector(db_session, name="Gmail"):
    from sqlalchemy import select
    from app.models.connections import Connector
    existing = (
        await db_session.execute(select(Connector).where(Connector.name == name))
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    c = Connector(name=name, auth_type="OAUTH2", config_schema={}, tools=[])
    db_session.add(c)
    await db_session.flush()
    await db_session.commit()
    return c


async def _seed_instance(
    db_session, *, connector, tenant_id, user_id,
    owner_email, status="CONNECTED",
):
    from app.core.constants import ConnectorStatus
    from app.core.vault import encrypt_dict
    from app.models.connections import ConnectorInstance
    inst = ConnectorInstance(
        connector_id=connector.id,
        tenant_id=tenant_id, user_id=user_id,
        status=getattr(ConnectorStatus, status).value
            if hasattr(ConnectorStatus, status) else status,
        credentials=encrypt_dict({
            "access_token": "tok-LEAK-CANARY-123",
            "refresh_token": "rfr-LEAK-CANARY-456",
            "expires_at": "2099-01-01T00:00:00+00:00",
            "token_type": "Bearer",
        }),
        owner_email=owner_email,
    )
    db_session.add(inst)
    await db_session.flush()
    await db_session.commit()
    return inst


# ──────────────────────────────────────────────────────────────────
# 1. Auth required
# ──────────────────────────────────────────────────────────────────


async def test_endpoint_requires_auth(client):
    res = await client.get(
        "/api/v1/connectors/oauth/accounts?provider=gmail",
    )
    # FastAPI's default missing-auth response code is 401 or 403
    # depending on the dependency setup. Either is acceptable; what
    # matters is "anonymous cannot enumerate accounts".
    assert res.status_code in (401, 403), res.text


# ──────────────────────────────────────────────────────────────────
# 2. Unsupported provider -> 400
# ──────────────────────────────────────────────────────────────────


async def test_unsupported_provider_returns_400(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_one_user_and_tenant(db_session, test_tenant_id, test_user_id)
    res = await client.get(
        "/api/v1/connectors/oauth/accounts?provider=mythos-invented",
        headers=auth_headers,
    )
    assert res.status_code == 400
    body = res.json()
    assert body.get("error") == "unsupported_provider"
    assert body.get("provider") == "mythos-invented"


# ──────────────────────────────────────────────────────────────────
# 3. Catalog row missing -> empty list (honest)
# ──────────────────────────────────────────────────────────────────


async def test_catalog_row_missing_returns_empty_list(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_one_user_and_tenant(db_session, test_tenant_id, test_user_id)
    await _wipe_connectors(db_session)  # No Gmail catalog row.
    res = await client.get(
        "/api/v1/connectors/oauth/accounts?provider=gmail",
        headers=auth_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["data"]["provider"] == "gmail"
    assert body["data"]["accounts"] == []


# ──────────────────────────────────────────────────────────────────
# 4. Returns ALL statuses
# ──────────────────────────────────────────────────────────────────


async def test_returns_all_statuses_for_picker_filter(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_one_user_and_tenant(db_session, test_tenant_id, test_user_id)
    await _wipe_connectors(db_session)
    connector = await _seed_connector(db_session, name="Gmail")
    await _seed_instance(
        db_session, connector=connector,
        tenant_id=test_tenant_id, user_id=test_user_id,
        owner_email="masoud.masoori@mas-ai.co", status="CONNECTED",
    )
    await _seed_instance(
        db_session, connector=connector,
        tenant_id=test_tenant_id, user_id=test_user_id,
        owner_email="daena@mas-ai.co", status="DISCONNECTED",
    )

    res = await client.get(
        "/api/v1/connectors/oauth/accounts?provider=gmail",
        headers=auth_headers,
    )
    assert res.status_code == 200
    accounts = res.json()["data"]["accounts"]
    assert len(accounts) == 2
    by_email = {a["owner_email"]: a for a in accounts}
    assert by_email["masoud.masoori@mas-ai.co"]["status"] == "CONNECTED"
    assert by_email["daena@mas-ai.co"]["status"] == "DISCONNECTED"
    # Each row carries the disambiguating instance_id for picker UI use.
    for a in accounts:
        assert "instance_id" in a
        assert len(a["instance_id"]) == 36  # UUID string length


# ──────────────────────────────────────────────────────────────────
# 5. Token material NEVER leaks into the response
# ──────────────────────────────────────────────────────────────────


async def test_response_payload_never_contains_token_material(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_one_user_and_tenant(db_session, test_tenant_id, test_user_id)
    await _wipe_connectors(db_session)
    connector = await _seed_connector(db_session, name="Gmail")
    await _seed_instance(
        db_session, connector=connector,
        tenant_id=test_tenant_id, user_id=test_user_id,
        owner_email="masoud@mas-ai.co", status="CONNECTED",
    )

    res = await client.get(
        "/api/v1/connectors/oauth/accounts?provider=gmail",
        headers=auth_headers,
    )
    assert res.status_code == 200
    raw = res.text
    # The seeded credentials carried both LEAK-CANARY substrings; if
    # ANY of them appear in the serialized payload, the endpoint
    # leaked encrypted material into a picker-facing response.
    assert "LEAK-CANARY" not in raw, (
        "endpoint leaked credentials JSONB substring into picker response"
    )
    assert "access_token" not in raw
    assert "refresh_token" not in raw
    assert "Bearer" not in raw
    # Sanity: round-trip the JSON -- the structural shape is the
    # only thing that should appear.
    body = json.loads(raw)
    keys_seen: set[str] = set()
    for acc in body["data"]["accounts"]:
        keys_seen.update(acc.keys())
    assert keys_seen == {"instance_id", "owner_email", "status"}


# ──────────────────────────────────────────────────────────────────
# 6. Tenant isolation
# ──────────────────────────────────────────────────────────────────


async def test_other_tenants_instances_never_leak(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    """A second tenant has its own ConnectorInstance for Gmail. Caller
    tenant must NOT see it. This is the load-bearing security rule for
    a multi-tenant Daena deployment."""
    import uuid
    from app.models.identity import Tenant, User

    await _seed_one_user_and_tenant(db_session, test_tenant_id, test_user_id)
    await _wipe_connectors(db_session)

    # Caller tenant: one Gmail account.
    connector = await _seed_connector(db_session, name="Gmail")
    await _seed_instance(
        db_session, connector=connector,
        tenant_id=test_tenant_id, user_id=test_user_id,
        owner_email="caller@mas-ai.co", status="CONNECTED",
    )

    # Other tenant: a different Gmail account that MUST NOT leak.
    other_tenant_id = uuid.UUID("33333333-3333-3333-3333-333333333333")
    other_user_id = uuid.UUID("44444444-4444-4444-4444-444444444444")
    other_tenant = Tenant(
        id=other_tenant_id, name="Other", slug="other-acc-ep", settings={},
    )
    db_session.add(other_tenant)
    await db_session.flush()
    other_user = User(
        id=other_user_id, tenant_id=other_tenant_id,
        email="other@test.local", role="FOUNDER",
    )
    db_session.add(other_user)
    await db_session.flush()
    await db_session.commit()
    await _seed_instance(
        db_session, connector=connector,
        tenant_id=other_tenant_id, user_id=other_user_id,
        owner_email="leaked-from-other@mas-ai.co", status="CONNECTED",
    )

    res = await client.get(
        "/api/v1/connectors/oauth/accounts?provider=gmail",
        headers=auth_headers,
    )
    assert res.status_code == 200
    accounts = res.json()["data"]["accounts"]
    owner_emails = sorted(a["owner_email"] for a in accounts)
    assert owner_emails == ["caller@mas-ai.co"], (
        f"Cross-tenant leak: {owner_emails!r}"
    )
