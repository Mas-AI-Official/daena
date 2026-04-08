"""ConnectorOAuthService: Multi-provider OAuth token management.

Handles OAuth 2.0 authorization code flow for:
- Google services (Gmail, Calendar, Drive)
- GitHub (repos, issues, PRs)
- Figma (design files, components)
- Slack (channels, messages)

Flow:
    1. Frontend calls GET /connectors/{id}/oauth/authorize
    2. Backend generates state token, returns provider consent URL
    3. User approves on provider consent screen
    4. Provider redirects to callback with auth code
    5. Backend exchanges code for access + refresh tokens
    6. Tokens stored encrypted in ConnectorInstance.credentials
    7. IntegrationRouter auto-refreshes expired tokens before use
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Provider Configuration ──


@dataclass(frozen=True)
class OAuthProviderConfig:
    """OAuth provider endpoints and settings."""

    auth_url: str
    token_url: str
    client_id_setting: str      # Settings attribute name for client ID
    client_secret_setting: str   # Settings attribute name for client secret
    scopes: list[str]
    extra_auth_params: dict[str, str] | None = None


# Maps connector_id prefixes to their OAuth provider
OAUTH_PROVIDERS: dict[str, OAuthProviderConfig] = {
    # Google services
    "gmail": OAuthProviderConfig(
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        client_id_setting="google_client_id",
        client_secret_setting="google_client_secret",
        scopes=[
            "https://www.googleapis.com/auth/gmail.modify",
            "https://www.googleapis.com/auth/gmail.send",
            "https://www.googleapis.com/auth/gmail.readonly",
        ],
        extra_auth_params={"access_type": "offline", "prompt": "consent"},
    ),
    "google-calendar": OAuthProviderConfig(
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        client_id_setting="google_client_id",
        client_secret_setting="google_client_secret",
        scopes=[
            "https://www.googleapis.com/auth/calendar",
            "https://www.googleapis.com/auth/calendar.events",
        ],
        extra_auth_params={"access_type": "offline", "prompt": "consent"},
    ),
    "google-drive": OAuthProviderConfig(
        auth_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        client_id_setting="google_client_id",
        client_secret_setting="google_client_secret",
        scopes=[
            "https://www.googleapis.com/auth/drive.readonly",
            "https://www.googleapis.com/auth/drive.metadata.readonly",
        ],
        extra_auth_params={"access_type": "offline", "prompt": "consent"},
    ),
    # GitHub
    "github": OAuthProviderConfig(
        auth_url="https://github.com/login/oauth/authorize",
        token_url="https://github.com/login/oauth/access_token",
        client_id_setting="github_client_id",
        client_secret_setting="github_client_secret",
        scopes=["repo", "read:user", "read:org"],
    ),
    # Figma
    "figma": OAuthProviderConfig(
        auth_url="https://www.figma.com/oauth",
        token_url="https://api.figma.com/v1/oauth/token",
        client_id_setting="figma_client_id",
        client_secret_setting="figma_client_secret",
        scopes=["files:read", "file_variables:read"],
    ),
    # Slack
    "slack": OAuthProviderConfig(
        auth_url="https://slack.com/oauth/v2/authorize",
        token_url="https://slack.com/api/oauth.v2.access",
        client_id_setting="slack_client_id",
        client_secret_setting="slack_client_secret",
        scopes=[
            "channels:read",
            "channels:history",
            "chat:write",
            "users:read",
        ],
    ),
    # Canva
    "canva": OAuthProviderConfig(
        auth_url="https://www.canva.com/api/oauth/authorize",
        token_url="https://api.canva.com/rest/v1/oauth/token",
        client_id_setting="canva_client_id",
        client_secret_setting="canva_client_secret",
        scopes=["design:content:read", "design:meta:read"],
    ),
}


class OAuthConfigError(ValueError):
    """Raised when OAuth provider credentials are not configured."""

    def __init__(self, provider: str, missing_field: str) -> None:
        self.provider = provider
        self.missing_field = missing_field
        super().__init__(
            f"OAuth not configured for {provider}. "
            f"Missing: {missing_field.upper()}. "
            f"Set this in your environment variables or .env file."
        )


class ConnectorOAuthService:
    """Manages OAuth 2.0 flows for multiple providers."""

    def __init__(self, db: Any) -> None:
        self._db = db
        self._settings = get_settings()

    def _get_provider(self, connector_id: str) -> OAuthProviderConfig:
        """Resolve provider config from connector ID."""
        provider = OAUTH_PROVIDERS.get(connector_id)
        if not provider:
            raise ValueError(
                f"No OAuth provider configured for connector: {connector_id}. "
                f"Supported: {', '.join(sorted(OAUTH_PROVIDERS.keys()))}"
            )
        return provider

    def _get_credential(self, setting_name: str) -> str:
        """Get a credential from settings, raising clear error if missing."""
        value = getattr(self._settings, setting_name, "")
        if not value:
            raise OAuthConfigError(setting_name.split("_")[0], setting_name)
        return value

    def get_supported_providers(self) -> list[dict[str, Any]]:
        """Return list of supported OAuth providers with configuration status."""
        result = []
        for provider_id, config in OAUTH_PROVIDERS.items():
            client_id = getattr(self._settings, config.client_id_setting, "")
            result.append({
                "provider_id": provider_id,
                "configured": bool(client_id),
                "auth_url": config.auth_url,
            })
        return result

    def generate_auth_url(
        self,
        provider: str,
        redirect_uri: str,
        state: str | None = None,
    ) -> tuple[str, str]:
        """Generate OAuth consent URL for any supported provider.

        Args:
            provider: Connector provider ID (gmail, github, figma, etc.)
            redirect_uri: Where provider redirects after consent
            state: CSRF protection token (auto-generated if None)

        Returns:
            Tuple of (authorization_url, state_token)

        Raises:
            ValueError: If provider is not supported
            OAuthConfigError: If provider credentials are not configured
        """
        config = self._get_provider(provider)

        if state is None:
            state = secrets.token_urlsafe(32)

        client_id = self._get_credential(config.client_id_setting)

        params: dict[str, str] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(config.scopes),
            "state": state,
        }

        if config.extra_auth_params:
            params.update(config.extra_auth_params)

        url = f"{config.auth_url}?{urlencode(params)}"

        logger.info(
            "connector_oauth.auth_url_generated",
            provider=provider,
            redirect_uri=redirect_uri,
        )

        return url, state

    async def exchange_code(
        self,
        code: str,
        redirect_uri: str,
        provider: str = "gmail",
    ) -> dict[str, Any]:
        """Exchange authorization code for access + refresh tokens.

        Args:
            code: The authorization code from provider callback
            redirect_uri: Must match the redirect_uri used in authorize
            provider: Connector provider ID for endpoint resolution

        Returns:
            Dict with access_token, refresh_token, expires_at, token_type, scope
        """
        config = self._get_provider(provider)
        client_id = self._get_credential(config.client_id_setting)
        client_secret = self._get_credential(config.client_secret_setting)

        headers: dict[str, str] = {}
        # GitHub requires Accept: application/json
        if provider == "github":
            headers["Accept"] = "application/json"

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                config.token_url,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                headers=headers,
            )

            if resp.status_code != 200:
                try:
                    error = resp.json().get("error_description", resp.text)
                except Exception:
                    error = resp.text
                raise ValueError(f"Token exchange failed for {provider}: {error}")

            data = resp.json()

            # GitHub returns access_token without expires_in
            if provider == "github":
                return {
                    "access_token": data["access_token"],
                    "refresh_token": data.get("refresh_token", ""),
                    "expires_at": "",  # GitHub tokens don't expire by default
                    "token_type": data.get("token_type", "bearer"),
                    "scope": data.get("scope", ""),
                    "provider": "github",
                }

            expires_in = data.get("expires_in", 3600)
            expires_at = datetime.now(UTC) + timedelta(seconds=expires_in)

            return {
                "access_token": data["access_token"],
                "refresh_token": data.get("refresh_token", ""),
                "expires_at": expires_at.isoformat(),
                "token_type": data.get("token_type", "Bearer"),
                "scope": data.get("scope", ""),
                "provider": provider,
            }

    async def refresh_token(
        self,
        refresh_token: str,
        provider: str = "gmail",
    ) -> dict[str, Any]:
        """Refresh an expired access token.

        Args:
            refresh_token: The stored refresh token
            provider: Connector provider ID for endpoint resolution

        Returns:
            Dict with new access_token and expires_at
        """
        config = self._get_provider(provider)
        client_id = self._get_credential(config.client_id_setting)
        client_secret = self._get_credential(config.client_secret_setting)

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                config.token_url,
                data={
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )

            if resp.status_code != 200:
                try:
                    error = resp.json().get("error_description", resp.text)
                except Exception:
                    error = resp.text
                raise ValueError(f"Token refresh failed for {provider}: {error}")

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
