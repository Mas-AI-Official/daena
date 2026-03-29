"""OAuth service: handles provider-specific authorization flows.

Supports Google and GitHub. Each provider follows the same pattern:
  1. Generate authorization URL with state for CSRF protection
  2. Exchange authorization code for access token
  3. Fetch user profile to get email, name, avatar

Uses httpx (already in deps) for all HTTP calls — no authlib needed.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config import get_settings

# Google OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# GitHub OAuth endpoints
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"


@dataclass(frozen=True)
class OAuthUserInfo:
    """Normalized user info returned by any OAuth provider."""

    email: str
    name: str | None
    avatar_url: str | None
    provider: str  # "google" or "github"
    provider_user_id: str


class OAuthService:
    """Handles OAuth authorization flows for Google and GitHub.

    Stateless — does not interact with the database.
    The AuthService handles user creation/linking.
    """

    @staticmethod
    def get_google_auth_url(state: str) -> str:
        """Build Google OAuth consent screen URL.

        Args:
            state: CSRF token to validate on callback.

        Returns:
            Full Google authorization URL.
        """
        settings = get_settings()
        redirect_uri = f"{settings.oauth_redirect_base_url}/api/v1/auth/oauth/google/callback"
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "offline",
            "prompt": "select_account",
        }
        return str(httpx.URL(GOOGLE_AUTH_URL, params=params))

    @staticmethod
    async def exchange_google_code(code: str) -> OAuthUserInfo:
        """Exchange Google authorization code for user info.

        Args:
            code: Authorization code from Google callback.

        Returns:
            Normalized OAuthUserInfo with email, name, avatar.

        Raises:
            httpx.HTTPStatusError: If Google API returns an error.
            ValueError: If token exchange fails.
        """
        settings = get_settings()
        redirect_uri = f"{settings.oauth_redirect_base_url}/api/v1/auth/oauth/google/callback"

        async with httpx.AsyncClient() as client:
            # Exchange code for tokens
            token_resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.google_client_id,
                    "client_secret": settings.google_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": redirect_uri,
                },
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()

            access_token = token_data.get("access_token")
            if not access_token:
                raise ValueError("No access_token in Google token response")

            # Fetch user info
            user_resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_resp.raise_for_status()
            user_data = user_resp.json()

        return OAuthUserInfo(
            email=user_data["email"],
            name=user_data.get("name"),
            avatar_url=user_data.get("picture"),
            provider="google",
            provider_user_id=str(user_data["id"]),
        )

    @staticmethod
    def get_github_auth_url(state: str) -> str:
        """Build GitHub OAuth authorization URL.

        Args:
            state: CSRF token to validate on callback.

        Returns:
            Full GitHub authorization URL.
        """
        settings = get_settings()
        redirect_uri = f"{settings.oauth_redirect_base_url}/api/v1/auth/oauth/github/callback"
        params = {
            "client_id": settings.github_client_id,
            "redirect_uri": redirect_uri,
            "scope": "read:user user:email",
            "state": state,
        }
        return str(httpx.URL(GITHUB_AUTH_URL, params=params))

    @staticmethod
    async def exchange_github_code(code: str) -> OAuthUserInfo:
        """Exchange GitHub authorization code for user info.

        Args:
            code: Authorization code from GitHub callback.

        Returns:
            Normalized OAuthUserInfo with email, name, avatar.

        Raises:
            httpx.HTTPStatusError: If GitHub API returns an error.
            ValueError: If token exchange fails or no verified email found.
        """
        settings = get_settings()
        redirect_uri = f"{settings.oauth_redirect_base_url}/api/v1/auth/oauth/github/callback"

        async with httpx.AsyncClient() as client:
            # Exchange code for access token
            token_resp = await client.post(
                GITHUB_TOKEN_URL,
                data={
                    "client_id": settings.github_client_id,
                    "client_secret": settings.github_client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()

            access_token = token_data.get("access_token")
            if not access_token:
                err = token_data.get("error_description", "unknown")
                raise ValueError(f"GitHub token error: {err}")

            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            }

            # Fetch user profile
            user_resp = await client.get(GITHUB_USER_URL, headers=headers)
            user_resp.raise_for_status()
            user_data = user_resp.json()

            # Fetch emails (primary verified email)
            email_resp = await client.get(GITHUB_EMAILS_URL, headers=headers)
            email_resp.raise_for_status()
            emails = email_resp.json()

        # Find primary verified email
        email = None
        for entry in emails:
            if entry.get("primary") and entry.get("verified"):
                email = entry["email"]
                break
        if not email:
            # Fallback: any verified email
            for entry in emails:
                if entry.get("verified"):
                    email = entry["email"]
                    break
        if not email:
            raise ValueError("No verified email found on GitHub account")

        return OAuthUserInfo(
            email=email,
            name=user_data.get("name") or user_data.get("login"),
            avatar_url=user_data.get("avatar_url"),
            provider="github",
            provider_user_id=str(user_data["id"]),
        )
