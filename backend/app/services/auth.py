"""Authentication service: register, login, refresh, logout, password reset.

Encapsulates all auth business logic. The router layer handles
HTTP concerns (cookies, status codes); this layer handles data.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError, ConflictError, TenantNotFoundError
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models.identity import PasswordResetToken, RefreshToken, Tenant, User
from app.services._base import BaseService
from app.services.oauth import OAuthUserInfo


class AuthService(BaseService):
    """Handles user registration, login, token refresh, and logout.

    Usage::

        service = AuthService(db)
        result = await service.register(
            email="me@example.com",
            password="SecurePass123!",
            display_name="Jane",
            tenant_name="Acme Corp",
        )
    """

    async def register(
        self,
        *,
        email: str,
        password: str,
        display_name: str,
        tenant_name: str,
    ) -> dict:
        """Create a new user and tenant.

        First user in a tenant is auto-assigned Founder role.

        Args:
            email: User email (must be unique).
            password: Plaintext password (already validated by schema).
            display_name: User's display name.
            tenant_name: Name for the new tenant.

        Returns:
            Dict with user_id, email, display_name, role, tenant_id, created_at.

        Raises:
            ConflictError: If email or tenant slug already exists.
        """
        # Check duplicate email
        existing = await self.db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise ConflictError("Email already registered")

        # Create or join tenant with slugified name
        slug = re.sub(r"[^a-z0-9-]", "-", tenant_name.lower()).strip("-")
        existing_tenant_result = await self.db.execute(
            select(Tenant).where(Tenant.slug == slug)
        )
        existing_tenant = existing_tenant_result.scalar_one_or_none()

        if existing_tenant:
            # Join existing tenant as OPERATOR (non-founder)
            tenant = existing_tenant
            role = "OPERATOR"
        else:
            # Create new tenant — first user is Founder
            tenant = Tenant(name=tenant_name, slug=slug)
            self.db.add(tenant)
            await self.db.flush()
            role = "FOUNDER"

            # Seed 10 default departments + 60 agents for new tenants only
            from app.services.agents import AgentService

            agent_svc = AgentService(self.db)
            await agent_svc.seed_defaults(tenant_id=tenant.id)

        user = User(
            tenant_id=tenant.id,
            email=email,
            password_hash=hash_password(password),
            display_name=display_name,
            role=role,
            terms_accepted_at=datetime.now(UTC),
            terms_version="2026-03-22",
        )
        self.db.add(user)
        await self.db.flush()

        # Auto-login: issue tokens immediately so frontend can redirect to app
        settings = get_settings()

        access_token = create_access_token(
            user_id=str(user.id),
            tenant_id=str(tenant.id),
            role=user.role,
            email=user.email,
            display_name=user.display_name or "",
            profile_complete=True,
        )

        raw_refresh, token_hash = generate_refresh_token()
        refresh = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.jwt_refresh_token_expire_days),
        )
        self.db.add(refresh)

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
            "raw_refresh_token": raw_refresh,
            "user": {
                "user_id": str(user.id),
                "email": user.email,
                "display_name": user.display_name,
                "role": user.role,
                "tenant_id": str(tenant.id),
                "profile_complete": True,
            },
        }

    async def oauth_login_or_register(self, *, info: OAuthUserInfo) -> dict:
        """Find or create a user via OAuth provider info, then issue tokens.

        Matching logic:
          1. By (provider, provider_user_id) — returning OAuth user
          2. By email — links OAuth to existing email/password user
          3. No match — creates new user + tenant

        OAuth users get email_verified=True automatically.

        Args:
            info: Normalized user info from OAuthService.

        Returns:
            Dict with access_token, raw_refresh_token, user data (same shape as login).
        """
        settings = get_settings()

        # 1. Try provider match
        result = await self.db.execute(
            select(User).where(
                User.oauth_provider == info.provider,
                User.oauth_provider_id == info.provider_user_id,
            )
        )
        user = result.scalar_one_or_none()

        # 2. Try email match (link OAuth to existing user)
        if not user:
            result = await self.db.execute(select(User).where(User.email == info.email))
            user = result.scalar_one_or_none()
            if user:
                # Link OAuth to existing account
                user.oauth_provider = info.provider
                user.oauth_provider_id = info.provider_user_id
                user.email_verified = True
                if info.avatar_url and not user.settings.get("avatar_url"):
                    user.avatar_url = info.avatar_url

        # 3. Create new user + tenant
        if not user:
            display_name = info.name or info.email.split("@")[0]
            tenant_name = f"{display_name}'s Workspace"
            slug = re.sub(r"[^a-z0-9-]", "-", tenant_name.lower()).strip("-")

            # Ensure unique slug
            existing = await self.db.execute(select(Tenant).where(Tenant.slug == slug))
            if existing.scalar_one_or_none():
                import secrets
                slug = f"{slug}-{secrets.token_hex(3)}"

            tenant = Tenant(name=tenant_name, slug=slug)
            self.db.add(tenant)
            await self.db.flush()

            user = User(
                tenant_id=tenant.id,
                email=info.email,
                password_hash=None,  # OAuth user — no password
                display_name=display_name,
                role="FOUNDER",
                oauth_provider=info.provider,
                oauth_provider_id=info.provider_user_id,
                avatar_url=info.avatar_url,
                email_verified=True,
            )
            self.db.add(user)
            await self.db.flush()

            # Seed 10 default departments + 60 agents for the new tenant
            from app.services.agents import AgentService

            agent_svc = AgentService(self.db)
            await agent_svc.seed_defaults(tenant_id=tenant.id)

        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        # Update last login
        user.last_login = datetime.now(UTC)

        # Profile is complete only when terms have been accepted
        _profile_complete = user.terms_accepted_at is not None

        # Issue tokens
        access_token = create_access_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            role=user.role,
            email=user.email,
            display_name=user.display_name or "",
            profile_complete=_profile_complete,
        )
        raw_refresh, token_hash = generate_refresh_token()
        refresh = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.jwt_refresh_token_expire_days),
        )
        self.db.add(refresh)

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
            "raw_refresh_token": raw_refresh,
            "user": {
                "user_id": str(user.id),
                "email": user.email,
                "display_name": user.display_name,
                "role": user.role,
                "tenant_id": str(user.tenant_id),
                "profile_complete": _profile_complete,
            },
        }

    async def login(self, *, email: str, password: str) -> dict:
        """Authenticate user and generate tokens.

        Args:
            email: User email.
            password: Plaintext password.

        Returns:
            Dict with access_token, token_type, expires_in, raw_refresh_token, user data.

        Raises:
            AuthenticationError: If credentials are invalid or account deactivated.

        Stabilization 2026-04-29 -- founder login race:
            Founder accounts are seeded in the deferred startup phase
            (after the port file publishes), so the first login attempts
            during cold-start may arrive before the founder row exists.
            For founder emails configured in settings, retry the SELECT
            up to 3 times with 200ms backoff while ``startup_state`` is
            still warming. For non-founder emails the original behaviour
            (immediate "invalid email or password") is preserved.
        """
        import asyncio as _asyncio

        from app.core.startup_state import startup_state

        settings = get_settings()
        founder_emails = {
            (settings.founder_email or "").strip().lower(),
            (settings.founder_personal_email or "").strip().lower(),
        }
        founder_emails.discard("")
        is_founder_email = email.strip().lower() in founder_emails

        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        # Cold-start race: founder row is seeded by the deferred lifespan
        # task. If we got here before that task ran, retry briefly.
        if (
            user is None
            and is_founder_email
            and not startup_state.seedings_complete
        ):
            for _attempt in range(3):
                await _asyncio.sleep(0.2)
                result = await self.db.execute(select(User).where(User.email == email))
                user = result.scalar_one_or_none()
                if user is not None or startup_state.seedings_complete:
                    break

        if not user or not user.password_hash or not verify_password(password, user.password_hash):
            raise AuthenticationError("Invalid email or password")

        if not user.is_active:
            raise AuthenticationError("Account is deactivated")

        # Update last login
        user.last_login = datetime.now(UTC)

        _profile_complete = user.terms_accepted_at is not None

        # Create access token
        access_token = create_access_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            role=user.role,
            email=user.email,
            display_name=user.display_name or "",
            profile_complete=_profile_complete,
        )

        # Create refresh token
        raw_refresh, token_hash = generate_refresh_token()
        refresh = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.jwt_refresh_token_expire_days),
        )
        self.db.add(refresh)

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
            "raw_refresh_token": raw_refresh,
            "user": {
                "user_id": str(user.id),
                "email": user.email,
                "display_name": user.display_name,
                "role": user.role,
                "tenant_id": str(user.tenant_id),
                "profile_complete": _profile_complete,
            },
        }

    async def refresh_token(self, *, raw_token: str) -> dict:
        """Exchange a valid refresh token for a new access token.

        The old refresh token is revoked and a new one issued (rotation).

        Args:
            raw_token: The raw refresh token string from the cookie.

        Returns:
            Dict with new access_token, raw_refresh_token, expires_in.

        Raises:
            AuthenticationError: If token is invalid, expired, or revoked.
        """
        settings = get_settings()
        token_hash = hash_refresh_token(raw_token)

        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        stored = result.scalar_one_or_none()

        if not stored:
            raise AuthenticationError("Invalid refresh token")

        # Normalize timezone for comparison (SQLite returns naive datetimes)
        now = datetime.now(UTC)
        expires_at = stored.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at < now:
            # Clean up expired token
            await self.db.delete(stored)
            raise AuthenticationError("Refresh token has expired")

        # Load user
        user_result = await self.db.execute(
            select(User).where(User.id == stored.user_id)
        )
        user = user_result.scalar_one_or_none()

        if not user or not user.is_active:
            await self.db.delete(stored)
            raise AuthenticationError("User account is deactivated or not found")

        # Revoke old refresh token (rotation)
        await self.db.delete(stored)

        # Issue new token pair
        access_token = create_access_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            role=user.role,
            email=user.email,
            display_name=user.display_name or "",
        )

        new_raw, new_hash = generate_refresh_token()
        new_refresh = RefreshToken(
            user_id=user.id,
            token_hash=new_hash,
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.jwt_refresh_token_expire_days),
        )
        self.db.add(new_refresh)

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
            "raw_refresh_token": new_raw,
        }

    async def logout(self, *, raw_token: str) -> bool:
        """Revoke a single refresh token (logout current session).

        Args:
            raw_token: The raw refresh token from the cookie.

        Returns:
            True if token was found and revoked, False otherwise.
        """
        token_hash = hash_refresh_token(raw_token)
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        stored = result.scalar_one_or_none()

        if stored:
            await self.db.delete(stored)
            return True
        return False

    async def revoke_all_tokens(self, *, user_id: UUID) -> int:
        """Revoke all refresh tokens for a user (logout everywhere).

        Args:
            user_id: UUID of the user.

        Returns:
            Number of tokens revoked.
        """
        # Count first, then delete (SQLite doesn't support RETURNING)
        count_result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.user_id == user_id)
        )
        tokens = list(count_result.scalars().all())
        count = len(tokens)

        if count > 0:
            await self.db.execute(
                delete(RefreshToken).where(RefreshToken.user_id == user_id)
            )

        return count

    # --- Complete Profile (OAuth users who skipped terms) ---

    async def complete_profile(
        self,
        *,
        user_id: UUID,
        tenant_name: str | None = None,
        agreed_to_terms: bool,
    ) -> dict:
        """Complete an OAuth user's profile by accepting terms and optionally renaming their tenant.

        Args:
            user_id: UUID of the current user.
            tenant_name: Optional company/workspace name to rename the tenant.
            agreed_to_terms: Must be True to proceed.

        Returns:
            Dict with new access_token and updated user data.

        Raises:
            AuthenticationError: If terms not accepted or user not found.
        """
        if not agreed_to_terms:
            raise AuthenticationError("You must accept the Terms of Service and Privacy Policy")

        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise AuthenticationError("User not found or deactivated")

        # Set terms acceptance
        user.terms_accepted_at = datetime.now(UTC)
        user.terms_version = "2026-03-22"

        # Optionally rename the tenant (e.g. "John's Workspace" -> "Acme Corp")
        if tenant_name and tenant_name.strip():
            tenant_result = await self.db.execute(
                select(Tenant).where(Tenant.id == user.tenant_id)
            )
            tenant = tenant_result.scalar_one_or_none()
            if tenant is None:
                raise TenantNotFoundError(
                    f"Tenant not found for user {user.id}"
                )
            if tenant:
                tenant.name = tenant_name.strip()
                new_slug = re.sub(r"[^a-z0-9-]", "-", tenant_name.lower()).strip("-")
                # Only update slug if new one is unique
                existing_slug = await self.db.execute(
                    select(Tenant).where(Tenant.slug == new_slug, Tenant.id != tenant.id)
                )
                if not existing_slug.scalar_one_or_none():
                    tenant.slug = new_slug

        await self.db.flush()

        # Issue new tokens with profile_complete=True
        settings = get_settings()
        access_token = create_access_token(
            user_id=str(user.id),
            tenant_id=str(user.tenant_id),
            role=user.role,
            email=user.email,
            display_name=user.display_name or "",
            profile_complete=True,
        )

        raw_refresh, token_hash = generate_refresh_token()
        refresh = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC)
            + timedelta(days=settings.jwt_refresh_token_expire_days),
        )
        self.db.add(refresh)

        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.jwt_access_token_expire_minutes * 60,
            "raw_refresh_token": raw_refresh,
            "user": {
                "user_id": str(user.id),
                "email": user.email,
                "display_name": user.display_name,
                "role": user.role,
                "tenant_id": str(user.tenant_id),
                "profile_complete": True,
            },
        }

    # --- Password Reset ---

    async def request_password_reset(self, *, email: str) -> str | None:
        """Generate a password reset token for the given email.

        Returns the raw token if the email exists (caller decides
        whether to expose it in dev or send it via email).
        Returns None if no user found — caller should still return
        success to prevent email enumeration.

        Args:
            email: User email address.

        Returns:
            Raw reset token string, or None if email not found.
        """
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            return None

        # Invalidate any existing unused reset tokens
        existing = await self.db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
        )
        for old_token in existing.scalars().all():
            old_token.used_at = datetime.now(UTC)

        # Generate new token
        raw_token = secrets.token_urlsafe(64)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        reset = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        self.db.add(reset)

        return raw_token

    async def reset_password(
        self, *, token: str, new_password: str
    ) -> bool:
        """Reset user password using a valid reset token.

        The token is single-use and expires after 30 minutes.

        Args:
            token: Raw reset token from the URL.
            new_password: New plaintext password (already validated).

        Returns:
            True on success.

        Raises:
            AuthenticationError: If token is invalid, expired, or used.
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        result = await self.db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash
            )
        )
        stored = result.scalar_one_or_none()

        if not stored:
            raise AuthenticationError("Invalid reset token")

        if stored.used_at is not None:
            raise AuthenticationError("Reset token already used")

        # Timezone-aware comparison
        now = datetime.now(UTC)
        expires_at = stored.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)

        if expires_at < now:
            raise AuthenticationError("Reset token has expired")

        # Mark token as used
        stored.used_at = now

        # Update password
        user_result = await self.db.execute(
            select(User).where(User.id == stored.user_id)
        )
        user = user_result.scalar_one_or_none()

        if not user or not user.is_active:
            raise AuthenticationError("User not found or deactivated")

        user.password_hash = hash_password(new_password)

        # Revoke all refresh tokens (force re-login everywhere)
        await self.db.execute(
            delete(RefreshToken).where(
                RefreshToken.user_id == user.id
            )
        )

        return True
