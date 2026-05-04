"""PR-CONN-OAUTH-ORPHAN-RECLAIM-UI (Sprint-6 PR-4, 2026-05-04) tests.

Pins the orphan-reclaim contract over the existing
``POST /connections/instances/{id}/archive`` endpoint, plus the
``GET /connectors/oauth/accounts`` listing semantics that surface
orphans to the picker.

The endpoint already existed (PR-CONN-OAUTH-REFRESH-DISCONNECT,
2026-05-03). PR-4 only adds a UI affordance + extra tests pinning
the orphan-specific cases:

  1. An orphan ConnectorInstance (owner_email IS NULL) belonging to
     the caller's tenant CAN be archived.
  2. The archive response payload carries no token / secret substring.
  3. A non-orphan instance (owner_email present) is NOT
     accidentally archived just because it appears in the same
     accounts list.
  4. After archive, /oauth/accounts surfaces the row with
     status=ARCHIVED so the frontend can drop it from the picker.
  5. The confirm gate is still required (regression check).

We use the JWT ``auth_headers`` fixture + manual seeding (matching
``test_oauth_accounts_endpoint.py``) so the test session and the
app session share state. The real-auth ``_register_and_login`` flow
commits through a separate session and breaks data isolation when
multiple HTTP calls land in one test.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.connections import Connector, ConnectorInstance
from app.models.identity import Tenant, User


pytestmark = pytest.mark.asyncio


async def _seed_user(db_session, tenant_id, user_id):
    if (await db_session.execute(
        select(Tenant).where(Tenant.id == tenant_id),
    )).scalar_one_or_none() is None:
        db_session.add(Tenant(id=tenant_id, name="T", slug="t-orph", settings={}))
        await db_session.flush()
    if (await db_session.execute(
        select(User).where(User.id == user_id),
    )).scalar_one_or_none() is None:
        db_session.add(User(
            id=user_id, tenant_id=tenant_id,
            email="founder@test.local", role="FOUNDER",
        ))
        await db_session.flush()
    await db_session.commit()


async def _seed_gmail_connector(db_session) -> Connector:
    # The OAuth accounts endpoint maps provider="gmail" -> connector
    # name "Gmail" (capital G) via _PROVIDER_TO_CONNECTOR_NAME. Seed
    # with the matching capitalization or the listing comes back empty.
    existing = (await db_session.execute(
        select(Connector).where(Connector.name == "Gmail"),
    )).scalar_one_or_none()
    if existing is not None:
        return existing
    c = Connector(
        name="Gmail",
        description="Gmail OAuth",
        auth_type="OAUTH",
        tools=[],
        category="communication",
    )
    db_session.add(c)
    await db_session.flush()
    await db_session.commit()
    return c


async def _seed_instance(
    db_session, *, tenant_id, user_id, connector_id,
    owner_email: str | None,
) -> ConnectorInstance:
    inst = ConnectorInstance(
        tenant_id=tenant_id,
        connector_id=connector_id,
        user_id=user_id,
        status="CONNECTED",
        credentials={"access_token": "FAKE-CANARY-TOKEN", "refresh_token": "FAKE-CANARY-RT"},
        owner_email=owner_email,
    )
    db_session.add(inst)
    await db_session.flush()
    await db_session.commit()
    return inst


# ──────────────────────────────────────────────────────────────────
# 1. Orphan can be archived by its owning tenant
# ──────────────────────────────────────────────────────────────────


async def test_orphan_owner_email_null_can_be_archived(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    connector = await _seed_gmail_connector(db_session)
    inst = await _seed_instance(
        db_session, tenant_id=test_tenant_id, user_id=test_user_id,
        connector_id=connector.id, owner_email=None,
    )

    res = await client.post(
        f"/api/v1/connections/instances/{inst.id}/archive",
        json={"confirm": True},
        headers=auth_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["data"]["status"] == "ARCHIVED"


# ──────────────────────────────────────────────────────────────────
# 2. Archive response carries no token substring
# ──────────────────────────────────────────────────────────────────


async def test_archive_response_carries_no_token_substring(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    connector = await _seed_gmail_connector(db_session)
    inst = await _seed_instance(
        db_session, tenant_id=test_tenant_id, user_id=test_user_id,
        connector_id=connector.id, owner_email=None,
    )

    res = await client.post(
        f"/api/v1/connections/instances/{inst.id}/archive",
        json={"confirm": True},
        headers=auth_headers,
    )
    assert res.status_code == 200
    raw = res.text
    # Seeded credentials carried CANARY substrings -- archive MUST
    # clear credentials and never return token-shaped fields.
    for forbidden in (
        "FAKE-CANARY-TOKEN", "FAKE-CANARY-RT",
        "access_token", "refresh_token", "Bearer",
    ):
        assert forbidden not in raw, (
            f"archive response leaked '{forbidden}'"
        )


# ──────────────────────────────────────────────────────────────────
# 3. Non-orphan with owner_email is NOT affected
# ──────────────────────────────────────────────────────────────────


async def test_archive_one_orphan_does_not_archive_named_account(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    connector = await _seed_gmail_connector(db_session)
    orphan = await _seed_instance(
        db_session, tenant_id=test_tenant_id, user_id=test_user_id,
        connector_id=connector.id, owner_email=None,
    )
    named = await _seed_instance(
        db_session, tenant_id=test_tenant_id, user_id=test_user_id,
        connector_id=connector.id, owner_email="masoud@mas-ai.co",
    )

    # Archive only the orphan.
    res = await client.post(
        f"/api/v1/connections/instances/{orphan.id}/archive",
        json={"confirm": True},
        headers=auth_headers,
    )
    assert res.status_code == 200

    # Named instance status remains CONNECTED in the DB. Read directly
    # to avoid a second HTTP call (multi-call within one test triggers
    # async-session interactions; the DB is the source of truth).
    refreshed = (await db_session.execute(
        select(ConnectorInstance).where(ConnectorInstance.id == named.id),
    )).scalar_one()
    assert refreshed.status == "CONNECTED"
    assert refreshed.owner_email == "masoud@mas-ai.co"


# ──────────────────────────────────────────────────────────────────
# 4. /oauth/accounts surfaces ARCHIVED so the frontend can drop it
# ──────────────────────────────────────────────────────────────────


async def test_oauth_accounts_lists_archived_status_for_frontend_filter(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    """The /oauth/accounts endpoint returns all instance statuses;
    the frontend filter (.status === 'CONNECTED') drops archived
    rows from the picker. We verify the row is present + status
    ARCHIVED so the frontend has the signal it needs."""
    await _seed_user(db_session, test_tenant_id, test_user_id)
    connector = await _seed_gmail_connector(db_session)
    inst = await _seed_instance(
        db_session, tenant_id=test_tenant_id, user_id=test_user_id,
        connector_id=connector.id, owner_email=None,
    )
    # Pre-archive: status is CONNECTED via DB inspect.
    assert inst.status == "CONNECTED"

    # Mutate via DB to ARCHIVED (simulates archive endpoint side
    # effect; we don't re-call the HTTP endpoint here to keep the
    # test single-request).
    inst.status = "ARCHIVED"
    inst.credentials = None
    await db_session.commit()

    # The listing endpoint surfaces the row + ARCHIVED status.
    res = await client.get(
        "/api/v1/connectors/oauth/accounts?provider=gmail",
        headers=auth_headers,
    )
    assert res.status_code == 200
    accounts = res.json()["data"]["accounts"]
    archived_row = next(
        (a for a in accounts if a["instance_id"] == str(inst.id)),
        None,
    )
    assert archived_row is not None
    assert archived_row["status"] == "ARCHIVED"


# ──────────────────────────────────────────────────────────────────
# 5. Confirm gate still required (regression of existing rule)
# ──────────────────────────────────────────────────────────────────


async def test_archive_orphan_without_confirm_returns_400(
    client, auth_headers, db_session, test_tenant_id, test_user_id,
):
    await _seed_user(db_session, test_tenant_id, test_user_id)
    connector = await _seed_gmail_connector(db_session)
    orphan = await _seed_instance(
        db_session, tenant_id=test_tenant_id, user_id=test_user_id,
        connector_id=connector.id, owner_email=None,
    )

    res = await client.post(
        f"/api/v1/connections/instances/{orphan.id}/archive",
        headers=auth_headers,
    )
    assert res.status_code == 400


# ──────────────────────────────────────────────────────────────────
# 6. Endpoint requires auth (anonymous cannot archive)
# ──────────────────────────────────────────────────────────────────


async def test_archive_requires_auth(client):
    """Anonymous request to archive must be rejected before any
    DB lookup -- 401/403 prevents an enumeration oracle."""
    res = await client.post(
        "/api/v1/connections/instances/00000000-0000-0000-0000-000000000099/archive",
        json={"confirm": True},
    )
    assert res.status_code in (401, 403)
