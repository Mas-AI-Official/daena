"""Integration tests for the ORG_MANAGEMENT entitlement gate on org writes.

The three team-management writes are paywalled at ENTERPRISE via
``require_feature(Feature.ORG_MANAGEMENT)``:

    POST   /api/v1/org/members              (invite a seat)
    PATCH  /api/v1/org/members/{id}/role    (change a member's role)
    DELETE /api/v1/org/members/{id}         (deactivate a member)

This closes the monetization enforcement loop: before this gate the entitlement
map + checkout + upgrade UI gated nothing, because no live endpoint emitted the
402. Now a non-founder tenant below ENTERPRISE gets a 402 whose body is the
upgrade contract the frontend interceptor (api.ts) redirects on
(-> /account/billing). The gate is plan-sensitive, not blanket-deny: an
ENTERPRISE tenant reaches the handler and the invite succeeds.

Coverage of every resolve_effective_plan branch:
    FOUNDER short-circuit ... the 4 FOUNDER tests in test_org_invite.py (the
                              gate passes for FOUNDER, so those stay green).
    FREE  (no subscription) . 402 here, on all three writes, with the upgrade
                              contract in the body.
    ENTERPRISE subscription . gate opens -> 201 invite here.

A FREE non-founder is an ADMIN token on a tenant with no ACTIVE subscription:
resolve_effective_plan finds no row and defaults to FREE, which does not unlock
ORG_MANAGEMENT (min plan ENTERPRISE). The 402 fires before any DB write, so the
block tests need no seeding. get_current_user builds CurrentUser purely from the
JWT, so the ADMIN token's role passes require_role("ADMIN") and only the FEATURE
gate can reject -> the 402 (not 403) isolates the paywall from the RBAC gate.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.models.financial import Subscription
from app.models.identity import Tenant, User


def _admin_headers(user_id: uuid.UUID, tenant_id: uuid.UUID) -> dict[str, str]:
    """A valid JWT for a non-founder ADMIN on the given tenant.

    ADMIN clears require_role("ADMIN") on every member write, so any rejection
    must come from the ORG_MANAGEMENT feature gate -- the 402 we assert below.
    """
    token = create_access_token(
        user_id=str(user_id), tenant_id=str(tenant_id), role="ADMIN"
    )
    return {"Authorization": f"Bearer {token}"}


def _assert_upgrade_402(resp) -> None:
    """A member write blocked by the paywall: 402 carrying the upgrade contract.

    The body is exactly what the frontend api.ts 402 interceptor needs to route
    the user to the AccountBilling upgrade surface.
    """
    assert resp.status_code == 402, resp.text
    detail = resp.json()["detail"]
    assert detail["error"] == "upgrade_required"
    assert detail["feature"] == "org_management"
    assert detail["current_plan"] == "FREE"
    assert detail["required_plan"] == "ENTERPRISE"
    assert detail["upgrade_url"] == "/account/billing"


@pytest.mark.asyncio
async def test_invite_member_blocked_for_free_tenant(client):
    """FREE-tenant ADMIN inviting a seat -> 402 upgrade_required, no member made."""
    headers = _admin_headers(
        uuid.UUID("33333333-3333-3333-3333-333333333333"),
        uuid.UUID("44444444-4444-4444-4444-444444444444"),
    )
    resp = await client.post(
        "/api/v1/org/members",
        headers=headers,
        json={"email": "should.not.land@example.com", "role": "MEMBER"},
    )
    _assert_upgrade_402(resp)


@pytest.mark.asyncio
async def test_update_member_role_blocked_for_free_tenant(client):
    """FREE-tenant ADMIN changing a member's role -> 402 before the handler runs."""
    headers = _admin_headers(
        uuid.UUID("33333333-3333-3333-3333-333333333333"),
        uuid.UUID("44444444-4444-4444-4444-444444444444"),
    )
    resp = await client.patch(
        f"/api/v1/org/members/{uuid.uuid4()}/role",
        headers=headers,
        json={"role": "ADMIN"},
    )
    _assert_upgrade_402(resp)


@pytest.mark.asyncio
async def test_remove_member_blocked_for_free_tenant(client):
    """FREE-tenant ADMIN removing a member -> 402 before the handler runs."""
    headers = _admin_headers(
        uuid.UUID("33333333-3333-3333-3333-333333333333"),
        uuid.UUID("44444444-4444-4444-4444-444444444444"),
    )
    resp = await client.delete(
        f"/api/v1/org/members/{uuid.uuid4()}",
        headers=headers,
    )
    _assert_upgrade_402(resp)


@pytest.mark.asyncio
async def test_invite_member_allowed_for_enterprise_tenant(client, db_session):
    """An ACTIVE ENTERPRISE subscription opens the gate -> the invite succeeds.

    Proves the gate is plan-sensitive (not a blanket deny): the same ADMIN
    request that 402s on FREE returns 201 once the tenant's effective plan
    resolves to ENTERPRISE.
    """
    tenant_id = uuid.UUID("55555555-5555-5555-5555-555555555555")
    admin_id = uuid.UUID("66666666-6666-6666-6666-666666666666")

    # Seed the tenant FIRST (flush so the FK target exists) -- then the FK-bearing
    # member + subscription rows. resolve_effective_plan then returns ENTERPRISE.
    db_session.add(
        Tenant(id=tenant_id, name="Enterprise Co", slug="enterprise-co", settings={})
    )
    await db_session.flush()
    db_session.add(
        User(
            id=admin_id,
            tenant_id=tenant_id,
            email="enterprise-admin@example.com",
            password_hash="x",
            role="ADMIN",
            is_active=True,
        )
    )
    db_session.add(
        Subscription(tenant_id=tenant_id, plan="ENTERPRISE", status="ACTIVE")
    )
    await db_session.flush()

    resp = await client.post(
        "/api/v1/org/members",
        headers=_admin_headers(admin_id, tenant_id),
        json={"email": "new.seat@example.com", "role": "MEMBER"},
    )

    # Gate opened: not the 402 paywall, and the honest invite contract holds.
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["temporary_password"]
    assert body["email_sent"] is False

    # The seat actually landed under the ENTERPRISE tenant.
    row = (
        await db_session.execute(
            select(User).where(
                User.tenant_id == tenant_id,
                func.lower(User.email) == "new.seat@example.com",
            )
        )
    ).scalar_one()
    assert row.role == "MEMBER"
    assert row.is_active is True
