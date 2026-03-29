"""Tests for OAuth authentication flow.

Covers:
- OAuth authorize URL generation
- OAuth callback state validation
- OAuth exchange for JWT tokens
- OAuth user creation and linking
- Unsupported provider handling
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

# ── OAuth Authorize ──


@pytest.mark.asyncio
async def test_oauth_authorize_google_returns_url(client: AsyncClient) -> None:
    """GET /oauth/google/authorize returns an auth URL and state token."""
    with patch("app.api.v1.auth.get_settings") as mock_settings:
        mock_settings.return_value.google_client_id = "test-google-id"
        mock_settings.return_value.google_client_secret = "test-secret"
        mock_settings.return_value.github_client_id = ""
        mock_settings.return_value.github_client_secret = ""
        mock_settings.return_value.oauth_redirect_base_url = "http://localhost:5173"
        mock_settings.return_value.is_production = False

        response = await client.get("/api/v1/auth/oauth/google/authorize")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "url" in body["data"]
    assert "state" in body["data"]
    assert "accounts.google.com" in body["data"]["url"]


@pytest.mark.asyncio
async def test_oauth_authorize_github_returns_url(client: AsyncClient) -> None:
    """GET /oauth/github/authorize returns a GitHub auth URL."""
    with patch("app.api.v1.auth.get_settings") as mock_settings:
        mock_settings.return_value.google_client_id = ""
        mock_settings.return_value.google_client_secret = ""
        mock_settings.return_value.github_client_id = "test-github-id"
        mock_settings.return_value.github_client_secret = "test-secret"
        mock_settings.return_value.oauth_redirect_base_url = "http://localhost:5173"
        mock_settings.return_value.is_production = False

        response = await client.get("/api/v1/auth/oauth/github/authorize")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert "github.com" in body["data"]["url"]


@pytest.mark.asyncio
async def test_oauth_authorize_unsupported_provider(client: AsyncClient) -> None:
    """Unsupported provider returns 401."""
    response = await client.get("/api/v1/auth/oauth/yahoo/authorize")
    assert response.status_code == 401


# ── OAuth Callback ──


@pytest.mark.asyncio
async def test_oauth_callback_invalid_state(client: AsyncClient) -> None:
    """Callback with invalid CSRF state returns 401."""
    response = await client.get(
        "/api/v1/auth/oauth/google/callback",
        params={"code": "fake-code", "state": "invalid-state"},
        follow_redirects=False,
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_oauth_callback_unsupported_provider(client: AsyncClient) -> None:
    """Callback for unsupported provider returns 401."""
    response = await client.get(
        "/api/v1/auth/oauth/yahoo/callback",
        params={"code": "fake-code", "state": "fake-state"},
        follow_redirects=False,
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_oauth_full_flow_google(client: AsyncClient) -> None:
    """Full OAuth flow: authorize → callback → exchange → JWT.

    Mocks the Google token exchange to avoid real HTTP calls.
    """
    from app.services.oauth import OAuthUserInfo

    mock_user_info = OAuthUserInfo(
        email="oauth-google@example.com",
        name="Google User",
        avatar_url="https://example.com/avatar.jpg",
        provider="google",
        provider_user_id="google-12345",
    )

    # Step 1: Get authorize URL + state
    with patch("app.api.v1.auth.get_settings") as mock_settings:
        mock_settings.return_value.google_client_id = "test-google-id"
        mock_settings.return_value.google_client_secret = "test-secret"
        mock_settings.return_value.oauth_redirect_base_url = "http://localhost:5173"
        mock_settings.return_value.is_production = False

        auth_resp = await client.get("/api/v1/auth/oauth/google/authorize")

    assert auth_resp.status_code == 200
    state = auth_resp.json()["data"]["state"]

    # Step 2: Simulate callback (mock the Google code exchange)
    with (
        patch("app.api.v1.auth.OAuthService.exchange_google_code", new_callable=AsyncMock) as mock_exchange,
        patch("app.api.v1.auth.get_settings") as mock_settings2,
    ):
        mock_exchange.return_value = mock_user_info
        mock_settings2.return_value.google_client_id = "test-google-id"
        mock_settings2.return_value.google_client_secret = "test-secret"
        mock_settings2.return_value.oauth_redirect_base_url = "http://localhost:5173"
        mock_settings2.return_value.is_production = False
        mock_settings2.return_value.jwt_access_token_expire_minutes = 15
        mock_settings2.return_value.jwt_refresh_token_expire_days = 7
        mock_settings2.return_value.jwt_secret_key = "test-secret-key"

        callback_resp = await client.get(
            "/api/v1/auth/oauth/google/callback",
            params={"code": "auth-code-from-google", "state": state},
            follow_redirects=False,
        )

    # Callback should redirect to frontend with exchange code
    assert callback_resp.status_code == 302
    location = callback_resp.headers["location"]
    assert "/auth/callback" in location
    assert "code=" in location

    # Extract exchange code from redirect URL
    from urllib.parse import parse_qs, urlparse
    parsed = urlparse(location)
    exchange_code = parse_qs(parsed.query)["code"][0]

    # Step 3: Exchange one-time code for JWT
    with patch("app.api.v1.auth.get_settings") as mock_settings3:
        mock_settings3.return_value.is_production = False
        mock_settings3.return_value.jwt_refresh_token_expire_days = 7

        exchange_resp = await client.post(
            "/api/v1/auth/oauth/exchange",
            json={"code": exchange_code},
        )

    assert exchange_resp.status_code == 200
    body = exchange_resp.json()
    assert body["success"] is True
    assert "access_token" in body["data"]
    assert body["data"]["user"]["email"] == "oauth-google@example.com"


# ── OAuth Exchange ──


@pytest.mark.asyncio
async def test_oauth_exchange_invalid_code(client: AsyncClient) -> None:
    """Exchange with invalid one-time code returns 401."""
    response = await client.post(
        "/api/v1/auth/oauth/exchange",
        json={"code": "nonexistent-code"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_oauth_exchange_code_single_use(client: AsyncClient) -> None:
    """One-time exchange code cannot be reused."""
    from app.services.oauth import OAuthUserInfo

    mock_user_info = OAuthUserInfo(
        email="singleuse@example.com",
        name="Single Use",
        avatar_url=None,
        provider="google",
        provider_user_id="google-single",
    )

    # Authorize
    with patch("app.api.v1.auth.get_settings") as mock_settings:
        mock_settings.return_value.google_client_id = "test-id"
        mock_settings.return_value.google_client_secret = "test-secret"
        mock_settings.return_value.oauth_redirect_base_url = "http://localhost:5173"
        mock_settings.return_value.is_production = False

        auth_resp = await client.get("/api/v1/auth/oauth/google/authorize")
    state = auth_resp.json()["data"]["state"]

    # Callback
    with (
        patch("app.api.v1.auth.OAuthService.exchange_google_code", new_callable=AsyncMock) as mock_ex,
        patch("app.api.v1.auth.get_settings") as mock_s2,
    ):
        mock_ex.return_value = mock_user_info
        mock_s2.return_value.google_client_id = "test-id"
        mock_s2.return_value.oauth_redirect_base_url = "http://localhost:5173"
        mock_s2.return_value.is_production = False
        mock_s2.return_value.jwt_access_token_expire_minutes = 15
        mock_s2.return_value.jwt_refresh_token_expire_days = 7
        mock_s2.return_value.jwt_secret_key = "test-secret-key"

        callback_resp = await client.get(
            "/api/v1/auth/oauth/google/callback",
            params={"code": "code", "state": state},
            follow_redirects=False,
        )

    from urllib.parse import parse_qs, urlparse
    exchange_code = parse_qs(urlparse(callback_resp.headers["location"]).query)["code"][0]

    # First exchange — succeeds
    with patch("app.api.v1.auth.get_settings") as mock_s3:
        mock_s3.return_value.is_production = False
        mock_s3.return_value.jwt_refresh_token_expire_days = 7
        first = await client.post("/api/v1/auth/oauth/exchange", json={"code": exchange_code})
    assert first.status_code == 200

    # Second exchange — fails (code consumed)
    second = await client.post("/api/v1/auth/oauth/exchange", json={"code": exchange_code})
    assert second.status_code == 401
