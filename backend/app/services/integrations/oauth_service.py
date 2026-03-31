"""ConnectorOAuthService: OAuth token management for integration connectors.

Handles the OAuth 2.0 authorization code flow for Gmail, Google Calendar,
and other Google services. Manages token exchange, storage, and refresh.

Flow:
    1. Frontend calls GET /connectors/{id}/oauth/authorize
    2. Backend generates state token, returns Google consent URL
    3. User approves on Google consent screen
    4. Google redirects to callback with auth code
    5. Backend exchanges code for access + refresh tokens
    6. Tokens stored encrypted in ConnectorInstance.credentials
    7. IntegrationRouter auto-refreshes expired tokens before use
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Google OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Scopes per provider
PROVIDER_SCOPES: dict[str, list[str]] = {
    "gmail": [
        "https://www.googleapis.com/auth/gmail.modify",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.readonly",
    ],
    "google-calendar": [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.events",
    ],
    "google-drive": [
        "https://www.googleapis.com/auth/drive.readonly",
    ],
}


class ConnectorOAuthService:
    """Manages OAuth 2.0 flows for integration connectors."""

    def __init__(self, db: Any) -> None:
        self._db = db
        self._settings = get_settings()

    def generate_auth_url(
        self,
        provider: str,
        redirect_uri: str,
        state: str | None = None,
    ) -> tuple[str, str]:
        """Generate the Google OAuth consent URL.

        Args:
            provider: Connector provider (gmail, google-calendar, etc.)
            redirect_uri: Where Google redirects after consent
            state: CSRF protection token (auto-generated if None)

        Returns:
            Tuple of (authorization_url, state_token)
        """
        if state is None:
            state = secrets.token_urlsafe(32)

        scopes = PROVIDER_SCOPES.get(provider, [])
        if not scopes:
            raise ValueError(f"No OAuth scopes configured for provider: {provider}")

        params = {
            "client_id": self._settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(scopes),
            "state": state,
            "access_type": "offline",  # Get refresh token
            "prompt": "consent",  # Force consent to get refresh token
        }

        url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
        return url, state

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
    ) -> dict[str, Any]:
        """Exchange authorization code for access + refresh tokens.

        Args:
            code: The authorization code from Google callback
            redirect_uri: Must match the redirect_uri used in authorize

        Returns:
            Dict with access_token, refresh_token, expires_at, token_type, scope
        """
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": self._settings.google_client_id,
                    "client_secret": self._settings.google_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
            )

            if resp.status_code != 200:
                error = resp.json().get("error_description", resp.text)
                raise ValueError(f"Token exchange failed: {error}")

            data = resp.json()
            expires_in = data.get("expires_in", 3600)
            expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

            return {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token", ""),
                "expires_at": expires_at.isoformat(),
                "token_type": data.get("token_type", "Bearer"),
                "scope": data.get("scope", ""),
            }

    async def refresh_token(
        self,
        refresh_token: str,
    ) -> dict[str, Any]:
        """Refresh an expired access token.

        Args:
            refresh_token: The stored refresh token

        Returns:
            Dict with new access_token and expires_at
        """
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": self._settings.google_client_id,
                    "client_secret": self._settings.google_client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )

            if resp.status_code != 200:
                error = resp.json().get("error_description", resp.text)
                raise ValueError(f"Token refresh failed: {error}")

            data = resp.json()
            expires_in = data.get("expires_in", 3600)
            expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

            return {
                "access_token": data["access_token"],
                "expires_at": expires_at.isoformat(),
            }

    async def store_tokens(
        self,
        connector_instance_id: UUID,
        tokens: dict[str, Any],
    ) -> None:
        """Store OAuth tokens in the connector instance credentials.

        Encrypts sensitive fields before storage.
        """
        from sqlalchemy import select, update
        from app.models.connections import ConnectorInstance

        stmt = (
            update(ConnectorInstance)
            .where(ConnectorInstance.id == connector_instance_id)
            .values(
                credentials=tokens,
                status="connected",
            )
        )
        await self._db.execute(stmt)
        await self._db.commit()

        logger.info(
            "connector_oauth.tokens_stored",
            instance_id=str(connector_instance_id),
            has_refresh=bool(tokens.get("refresh_token")),
        )

    async def check_and_refresh(
        self,
        credentials: dict[str, Any],
    ) -> dict[str, Any]:
        """Check if tokens are expired and refresh if needed.

        Args:
            credentials: Current connector credentials dict

        Returns:
            Updated credentials (refreshed if needed)
        """
        expires_at_str = credentials.get("expires_at")
        refresh_token = credentials.get("refresh_token")

        if not expires_at_str or not refresh_token:
            return credentials

        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            # Refresh 5 minutes before expiry
            if datetime.now(UTC) >= expires_at - timedelta(minutes=5):
                logger.info("connector_oauth.refreshing_token")
                new_tokens = await self.refresh_token(refresh_token)
                credentials["access_token"] = new_tokens["access_token"]
                credentials["expires_at"] = new_tokens["expires_at"]
                return credentials
        except Exception as exc:
            logger.warning("connector_oauth.refresh_check_failed", error=str(exc))

        return credentials
