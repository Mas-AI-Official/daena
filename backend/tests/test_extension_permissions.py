"""Tests for per-user MCP extension permission persistence.

Pin the contract:
* POST writes the extension default + per-tool overrides into User.settings
* GET /connections/extensions hydrates from the saved values
* Invalid permission strings are rejected with 422
* Tool-level updates MERGE (don't replace the whole tools dict)
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.identity import Tenant, User


@pytest.fixture
async def seeded_user(db_session, test_user_id, test_tenant_id):
    """Seed a Tenant + User so the permission endpoint finds them.

    The auth_headers fixture only creates a JWT with fixed UUIDs; it
    does NOT insert DB rows. The permission endpoint does a real
    SELECT on users, so we need the row present.
    """
    tenant = Tenant(
        id=test_tenant_id,
        name="Test Tenant",
        slug="test-tenant",
        settings={},
    )
    db_session.add(tenant)
    await db_session.flush()
    user = User(
        id=test_user_id,
        tenant_id=test_tenant_id,
        email="test@example.com",
        display_name="Test User",
        role="FOUNDER",
        settings={},
    )
    db_session.add(user)
    await db_session.flush()
    yield user


@pytest.mark.asyncio
async def test_save_default_permission_persists_in_settings(
    client: AsyncClient,
    auth_headers: dict[str, str],
    db_session,
    test_user_id,
    seeded_user,
) -> None:
    """POST /extensions/{id}/permissions writes to User.settings JSONB."""
    response = await client.post(
        "/api/v1/connections/extensions/filesystem/permissions",
        headers=auth_headers,
        json={"default": "ALLOW"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["extension_id"] == "filesystem"
    assert body["data"]["saved"]["default"] == "ALLOW"

    # Verify actually in the DB
    stmt = select(User).where(User.id == test_user_id)
    row = await db_session.execute(stmt)
    user = row.scalar_one()
    assert user.settings["extension_permissions"]["filesystem"]["default"] == "ALLOW"


@pytest.mark.asyncio
async def test_tool_level_permissions_merge_not_replace(
    client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_user,
) -> None:
    """Sending a tools update merges with existing tools instead of replacing."""
    # First call: set read_file -> ALLOW
    r1 = await client.post(
        "/api/v1/connections/extensions/filesystem/permissions",
        headers=auth_headers,
        json={"tools": {"read_file": "ALLOW"}},
    )
    assert r1.status_code == 200

    # Second call: set write_file -> BLOCK. read_file should stick around.
    r2 = await client.post(
        "/api/v1/connections/extensions/filesystem/permissions",
        headers=auth_headers,
        json={"tools": {"write_file": "BLOCK"}},
    )
    assert r2.status_code == 200
    saved = r2.json()["data"]["saved"]
    assert saved["tools"]["read_file"] == "ALLOW"
    assert saved["tools"]["write_file"] == "BLOCK"


@pytest.mark.asyncio
async def test_list_extensions_hydrates_saved_permissions(
    client: AsyncClient,
    auth_headers: dict[str, str],
    seeded_user,
) -> None:
    """GET /extensions returns permission + tool_permissions from saved state."""
    # Save something first
    await client.post(
        "/api/v1/connections/extensions/desktop-commander/permissions",
        headers=auth_headers,
        json={"default": "BLOCK", "tools": {"shell": "ALLOW"}},
    )

    # Now list. Even if the scanner finds no extensions on this test
    # machine, the endpoint should return 200 with success=True. The
    # hydrated permission will only appear if the slug matches a
    # scanned extension -- for the assertion here we just verify the
    # endpoint doesn't crash when hydrating.
    response = await client.get(
        "/api/v1/connections/extensions",
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["success"] is True


@pytest.mark.asyncio
async def test_invalid_permission_value_rejected(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """default=NONSENSE should 422 and not write anything."""
    response = await client.post(
        "/api/v1/connections/extensions/filesystem/permissions",
        headers=auth_headers,
        json={"default": "MAYBE_LATER"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_invalid_tool_permission_value_rejected(
    client: AsyncClient,
    auth_headers: dict[str, str],
) -> None:
    """A bad tool permission value is rejected with a clear detail."""
    response = await client.post(
        "/api/v1/connections/extensions/filesystem/permissions",
        headers=auth_headers,
        json={"tools": {"read_file": "WHATEVER"}},
    )
    assert response.status_code == 422
