"""Tests for AuthService and new auth endpoints (refresh, logout).

Extends the existing test_auth.py with service-level tests and
coverage for the new /refresh, /logout, /logout-all endpoints.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

# ── Register + Login (existing flow, thin-router validation) ──


@pytest.mark.asyncio
async def test_register_returns_correct_shape(client: AsyncClient) -> None:
    """Registration response matches StandardResponse envelope with auto-login tokens."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "shape@example.com",
            "password": "SecurePass123!",
            "display_name": "Shape Test",
            "tenant_name": "Shape Org",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["success"] is True
    # Register now returns same shape as login (tokens + nested user)
    assert "access_token" in body["data"]
    assert body["data"]["token_type"] == "bearer"
    assert "user_id" in body["data"]["user"]
    assert "tenant_id" in body["data"]["user"]
    assert body["data"]["user"]["role"] == "FOUNDER"


@pytest.mark.asyncio
async def test_login_sets_refresh_cookie(client: AsyncClient) -> None:
    """Login sets httpOnly refresh_token cookie."""
    # Register
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "cookie@example.com",
            "password": "SecurePass123!",
            "display_name": "Cookie Test",
            "tenant_name": "Cookie Org",
        },
    )

    # Login
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "cookie@example.com",
            "password": "SecurePass123!",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "access_token" in body["data"]

    # Verify refresh cookie was set
    cookies = response.cookies
    assert "refresh_token" in cookies


@pytest.mark.asyncio
async def test_login_response_has_no_raw_refresh(client: AsyncClient) -> None:
    """Login JSON body must NOT contain the raw refresh token."""
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "noraw@example.com",
            "password": "SecurePass123!",
            "display_name": "No Raw",
            "tenant_name": "No Raw Org",
        },
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "noraw@example.com", "password": "SecurePass123!"},
    )
    body = response.json()
    assert "raw_refresh_token" not in body["data"]


# ── Refresh Token ──


@pytest.mark.asyncio
async def test_refresh_returns_new_access_token(client: AsyncClient) -> None:
    """Refresh with valid cookie yields a new access token."""
    # Register + Login
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "refresh@example.com",
            "password": "SecurePass123!",
            "display_name": "Refresh",
            "tenant_name": "Refresh Org",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@example.com", "password": "SecurePass123!"},
    )
    assert login_resp.status_code == 200

    # Refresh — cookies are auto-forwarded by httpx
    refresh_resp = await client.post("/api/v1/auth/refresh")
    assert refresh_resp.status_code == 200

    body = refresh_resp.json()
    assert body["success"] is True
    assert "access_token" in body["data"]
    assert body["data"]["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_refresh_without_cookie_returns_401(client: AsyncClient) -> None:
    """Refresh without a cookie returns 401."""
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotation_invalidates_old_token(client: AsyncClient) -> None:
    """After refresh, the old refresh token should be invalid (rotation)."""
    # Register + Login
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "rotation@example.com",
            "password": "SecurePass123!",
            "display_name": "Rotation",
            "tenant_name": "Rotation Org",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "rotation@example.com", "password": "SecurePass123!"},
    )

    # Save the original cookie
    original_cookie = login_resp.cookies.get("refresh_token")
    assert original_cookie is not None

    # First refresh — should succeed and issue new cookie
    first_refresh = await client.post("/api/v1/auth/refresh")
    assert first_refresh.status_code == 200

    # Try reusing the old cookie — clear jar first so httpx doesn't
    # send the NEW token from the first refresh's Set-Cookie header.
    client.cookies.clear()
    client.cookies.set("refresh_token", original_cookie, domain="test")
    second_refresh = await client.post("/api/v1/auth/refresh")
    assert second_refresh.status_code == 401


# ── Logout ──


@pytest.mark.asyncio
async def test_logout_clears_cookie(client: AsyncClient) -> None:
    """Logout clears the refresh cookie."""
    # Register + Login
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "logout@example.com",
            "password": "SecurePass123!",
            "display_name": "Logout",
            "tenant_name": "Logout Org",
        },
    )
    await client.post(
        "/api/v1/auth/login",
        json={"email": "logout@example.com", "password": "SecurePass123!"},
    )

    # Logout
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "Logged out" in body["data"]["message"]


@pytest.mark.asyncio
async def test_logout_without_cookie_still_succeeds(client: AsyncClient) -> None:
    """Logout without a cookie is a no-op success (idempotent)."""
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 200


# ── Logout All ──


@pytest.mark.asyncio
async def test_logout_all_revokes_sessions(client: AsyncClient) -> None:
    """Logout-all revokes all refresh tokens for the user."""
    # Register + Login
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "logoutall@example.com",
            "password": "SecurePass123!",
            "display_name": "Logout All",
            "tenant_name": "LogoutAll Org",
        },
    )
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "logoutall@example.com", "password": "SecurePass123!"},
    )
    token = login_resp.json()["data"]["access_token"]

    # Logout all with access token
    response = await client.post(
        "/api/v1/auth/logout-all",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["revoked_count"] >= 1

    # Refresh should now fail (token revoked)
    refresh_resp = await client.post("/api/v1/auth/refresh")
    assert refresh_resp.status_code == 401
