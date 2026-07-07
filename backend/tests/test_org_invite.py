"""Integration tests for the org seat-invite endpoint.

POST /api/v1/org/members (invite_member): an ADMIN+ creates a new tenant
member. Daena has no transactional email path yet, so the endpoint returns a
one-time temporary password and email_sent=False (Rule 17 honesty: no dead
"invitation sent" button). Email is unique per tenant; a duplicate is a 409.

Covered:
    201  success           -- member row created, temp password returned
    409  duplicate email   -- case-insensitive, up-front count + DB UNIQUE
    403  non-admin caller   -- VIEWER (valid role, below ADMIN) is rejected
    422  invalid role       -- body role outside ^(MEMBER|ADMIN)$

These exercise the real router + DB via the integration fixtures in
conftest.py (in-memory SQLite, FK pragma ON). seed_auth_principal is required
on the success/duplicate paths because User.tenant_id is an FK to Tenant.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.models.identity import User


@pytest.mark.asyncio
async def test_invite_member_success(
    client, auth_headers, seed_auth_principal, db_session, test_tenant_id
):
    """ADMIN+ creates a member -> 201 with a one-time temp password, no email."""
    resp = await client.post(
        "/api/v1/org/members",
        headers=auth_headers,
        json={"email": "new.member@example.com", "role": "MEMBER"},
    )

    assert resp.status_code == 201, resp.text
    body = resp.json()

    # Honest invite contract: a usable temp password + an explicit "no email" flag.
    assert body["temporary_password"], "expected a non-empty temporary password"
    assert body["email_sent"] is False
    assert "email" in body["message"].lower()

    member = body["member"]
    assert member["email"] == "new.member@example.com"
    assert member["role"] == "MEMBER"
    assert member["is_active"] is True

    # The row actually landed in the tenant, active, email unverified.
    row = (
        await db_session.execute(
            select(User).where(
                User.tenant_id == test_tenant_id,
                func.lower(User.email) == "new.member@example.com",
            )
        )
    ).scalar_one()
    assert row.role == "MEMBER"
    assert row.is_active is True
    assert row.email_verified is False
    # The stored hash is not the plaintext temp password.
    assert row.password_hash != body["temporary_password"]


@pytest.mark.asyncio
async def test_invite_member_duplicate_is_conflict(
    client, auth_headers, seed_auth_principal
):
    """Re-inviting the same email (different case) -> 409, not a second row."""
    first = await client.post(
        "/api/v1/org/members",
        headers=auth_headers,
        json={"email": "Dup@Example.com", "role": "MEMBER"},
    )
    assert first.status_code == 201, first.text

    second = await client.post(
        "/api/v1/org/members",
        headers=auth_headers,
        json={"email": "dup@example.com", "role": "MEMBER"},
    )
    assert second.status_code == 409, second.text
    assert "exist" in second.json()["detail"].lower()


@pytest.mark.asyncio
async def test_invite_member_non_admin_forbidden(
    client, test_user_id, test_tenant_id
):
    """A VIEWER (valid role, below ADMIN) is rejected by require_role -> 403."""
    token = create_access_token(
        user_id=str(test_user_id),
        tenant_id=str(test_tenant_id),
        role="VIEWER",
    )
    resp = await client.post(
        "/api/v1/org/members",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": "denied@example.com", "role": "MEMBER"},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_invite_member_invalid_role_rejected(
    client, auth_headers, seed_auth_principal
):
    """A role outside ^(MEMBER|ADMIN)$ fails request validation -> 422."""
    resp = await client.post(
        "/api/v1/org/members",
        headers=auth_headers,
        json={"email": "weird@example.com", "role": "OWNER"},
    )
    assert resp.status_code == 422, resp.text
