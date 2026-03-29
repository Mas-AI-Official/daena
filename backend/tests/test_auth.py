"""Tests for authentication endpoints."""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_new_user(client: AsyncClient) -> None:
    """Registration creates user and tenant, returns tokens + user with Founder role."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "SecurePass123!",
            "display_name": "Test User",
            "tenant_name": "Test Org",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    # Register now returns tokens (auto-login) with user nested
    assert "access_token" in data["data"]
    assert data["data"]["token_type"] == "bearer"
    assert data["data"]["user"]["role"] == "FOUNDER"
    assert data["data"]["user"]["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient) -> None:
    """Registration with existing email returns 409."""
    payload = {
        "email": "duplicate@example.com",
        "password": "SecurePass123!",
        "display_name": "First User",
        "tenant_name": "First Org",
    }
    # First registration
    await client.post("/api/v1/auth/register", json=payload)

    # Duplicate
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient) -> None:
    """Registration with weak password returns 422."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "weak@example.com",
            "password": "short",
            "display_name": "Weak",
            "tenant_name": "Weak Org",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_valid_credentials(client: AsyncClient) -> None:
    """Login with valid credentials returns JWT and refresh cookie."""
    # Register first
    await client.post(
        "/api/v1/auth/register",
        json={
            "email": "login@example.com",
            "password": "SecurePass123!",
            "display_name": "Login User",
            "tenant_name": "Login Org",
        },
    )

    # Login
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "login@example.com",
            "password": "SecurePass123!",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "access_token" in data["data"]
    assert data["data"]["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient) -> None:
    """Login with wrong password returns 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "nobody@example.com",
            "password": "WrongPass123!",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_rate_limiting(client: AsyncClient) -> None:
    """After 5 failed login attempts, the 6th returns 429."""
    # Clear the rate limiter state before this test
    from app.api.v1.auth import _login_attempts
    _login_attempts.clear()

    payload = {"email": "bruteforce@example.com", "password": "WrongPass123!"}

    # First 5 attempts should return 401 (invalid creds)
    for i in range(5):
        resp = await client.post("/api/v1/auth/login", json=payload)
        assert resp.status_code == 401, f"Attempt {i+1} should be 401, got {resp.status_code}"

    # 6th attempt should be rate-limited (429)
    resp = await client.post("/api/v1/auth/login", json=payload)
    assert resp.status_code == 429
    body = resp.json()
    assert body["success"] is False
    assert body["error"]["code"] == "RATE_LIMITED"
    assert "60 seconds" in body["error"]["message"]

    # Clean up for other tests
    _login_attempts.clear()
