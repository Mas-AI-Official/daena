"""Tests for password reset flow.

Covers:
- Forgot password (valid email, unknown email — no enumeration)
- Reset with valid token
- Reset with expired token
- Reset with already-used token
- Reset with invalid token
- Password policy enforcement on reset
- Session revocation on password reset
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.identity import PasswordResetToken, User

# Reusable test password
VALID_PASSWORD = "SecurePass123!"
NEW_PASSWORD = "NewSecure456!"


async def _register_user(client: AsyncClient, email: str = "reset@example.com") -> dict:
    """Helper: register a user and return the response data."""
    resp = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": VALID_PASSWORD,
            "display_name": "Reset User",
            "tenant_name": f"Org-{email.split('@')[0]}",
        },
    )
    assert resp.status_code == 201
    return resp.json()["data"]


# ── Forgot Password ──


@pytest.mark.asyncio
async def test_forgot_password_valid_email(client: AsyncClient) -> None:
    """Forgot password with existing email returns success and dev token."""
    await _register_user(client, "forgot-valid@example.com")

    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "forgot-valid@example.com"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "message" in body["data"]

    # Dev mode: token should be in response
    assert "dev_reset_token" in body["data"]
    assert "dev_reset_url" in body["data"]


@pytest.mark.asyncio
async def test_forgot_password_unknown_email(client: AsyncClient) -> None:
    """Forgot password with unknown email still returns success (no enumeration)."""
    response = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nobody@doesnotexist.com"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    # Should NOT leak dev token for non-existent user
    assert "dev_reset_token" not in body["data"]


@pytest.mark.asyncio
async def test_forgot_password_invalidates_previous_tokens(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Requesting a new reset token invalidates the previous unused one."""
    await _register_user(client, "multi-reset@example.com")

    # First request
    resp1 = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "multi-reset@example.com"},
    )
    token1 = resp1.json()["data"]["dev_reset_token"]

    # Second request
    resp2 = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "multi-reset@example.com"},
    )
    token2 = resp2.json()["data"]["dev_reset_token"]

    assert token1 != token2

    # First token should now be used/invalidated — reset should fail
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": token1,
            "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )
    assert response.status_code == 401


# ── Reset Password ──


@pytest.mark.asyncio
async def test_reset_password_valid_token(client: AsyncClient) -> None:
    """Reset password with valid token succeeds."""
    await _register_user(client, "reset-valid@example.com")

    # Get reset token
    forgot_resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "reset-valid@example.com"},
    )
    token = forgot_resp.json()["data"]["dev_reset_token"]

    # Reset
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": token,
            "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True

    # Login with new password should work
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "reset-valid@example.com", "password": NEW_PASSWORD},
    )
    assert login_resp.status_code == 200

    # Login with old password should fail
    login_old = await client.post(
        "/api/v1/auth/login",
        json={"email": "reset-valid@example.com", "password": VALID_PASSWORD},
    )
    assert login_old.status_code == 401


@pytest.mark.asyncio
async def test_reset_password_invalid_token(client: AsyncClient) -> None:
    """Reset with an invalid token returns 401."""
    response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": "definitely-not-a-valid-token",
            "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_reset_password_used_token(client: AsyncClient) -> None:
    """Reset token cannot be reused (single-use)."""
    await _register_user(client, "used-token@example.com")

    forgot_resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "used-token@example.com"},
    )
    token = forgot_resp.json()["data"]["dev_reset_token"]

    # First reset — succeeds
    first = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": token,
            "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )
    assert first.status_code == 200

    # Second reset — fails (token already used)
    second = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": token,
            "password": "AnotherPass789!",
            "confirm_password": "AnotherPass789!",
        },
    )
    assert second.status_code == 401


@pytest.mark.asyncio
async def test_reset_password_expired_token(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """Reset with an expired token returns 401."""
    await _register_user(client, "expired@example.com")

    # Find user
    result = await db_session.execute(
        select(User).where(User.email == "expired@example.com")
    )
    user = result.scalar_one()

    # Manually create an expired token
    raw = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(raw.encode()).hexdigest()
    expired_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=datetime.now(UTC) - timedelta(hours=1),  # expired
    )
    db_session.add(expired_token)
    await db_session.flush()

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": raw,
            "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_reset_password_weak_password(client: AsyncClient) -> None:
    """Reset with a weak password returns 422 (Pydantic validation)."""
    await _register_user(client, "weak-reset@example.com")

    forgot_resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "weak-reset@example.com"},
    )
    token = forgot_resp.json()["data"]["dev_reset_token"]

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": token,
            "password": "short",
            "confirm_password": "short",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reset_password_mismatch(client: AsyncClient) -> None:
    """Reset with mismatched passwords returns 422."""
    await _register_user(client, "mismatch@example.com")

    forgot_resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "mismatch@example.com"},
    )
    token = forgot_resp.json()["data"]["dev_reset_token"]

    response = await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": token,
            "password": NEW_PASSWORD,
            "confirm_password": "DifferentPass789!",
        },
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_reset_revokes_all_sessions(client: AsyncClient) -> None:
    """Password reset revokes all existing refresh tokens (force re-login)."""
    await _register_user(client, "revoke-sessions@example.com")

    # Login to create a session
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "revoke-sessions@example.com", "password": VALID_PASSWORD},
    )
    assert login_resp.status_code == 200

    # Get reset token
    forgot_resp = await client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "revoke-sessions@example.com"},
    )
    token = forgot_resp.json()["data"]["dev_reset_token"]

    # Reset password
    await client.post(
        "/api/v1/auth/reset-password",
        json={
            "token": token,
            "password": NEW_PASSWORD,
            "confirm_password": NEW_PASSWORD,
        },
    )

    # Old refresh token should be invalid now
    refresh_resp = await client.post("/api/v1/auth/refresh")
    assert refresh_resp.status_code == 401
