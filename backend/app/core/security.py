"""JWT token management and password hashing.

Handles:
- JWT access token creation and validation
- Refresh token generation (opaque + SHA-256 hash)
- Password hashing with bcrypt (direct, no passlib)
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import get_settings


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt.

    Args:
        password: Plaintext password.

    Returns:
        Bcrypt hash string.
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash.

    Args:
        plain_password: Plaintext password to check.
        hashed_password: Stored bcrypt hash.

    Returns:
        True if password matches.
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def create_access_token(
    user_id: str,
    tenant_id: str,
    role: str,
    email: str = "",
    display_name: str = "",
    profile_complete: bool = True,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a JWT access token.

    Args:
        user_id: UUID of the authenticated user.
        tenant_id: UUID of the user's tenant.
        role: User's RBAC role.
        email: User's email (included so frontend can display without extra API call).
        display_name: User's display name (same reason).
        profile_complete: Whether user has accepted terms and filled company name.
        expires_delta: Custom expiration (default from settings).

    Returns:
        Encoded JWT string.
    """
    settings = get_settings()
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)

    now = datetime.now(UTC)
    payload = {
        "sub": user_id,
        "tenant_id": tenant_id,
        "role": role,
        "email": email,
        "display_name": display_name,
        "profile_complete": profile_complete,
        "jti": str(uuid.uuid4()),
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT access token.

    Args:
        token: Encoded JWT string.

    Returns:
        Decoded payload dict.

    Raises:
        jwt.ExpiredSignatureError: Token has expired.
        jwt.InvalidTokenError: Token is malformed or invalid.
    """
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def generate_refresh_token() -> tuple[str, str]:
    """Generate a cryptographically secure refresh token.

    Returns:
        Tuple of (raw_token, token_hash).
        Store the hash in DB; return the raw token to the client.
    """
    raw_token = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash


def hash_refresh_token(raw_token: str) -> str:
    """Hash a refresh token for lookup.

    Args:
        raw_token: The raw token string sent by the client.

    Returns:
        SHA-256 hex digest for database lookup.
    """
    return hashlib.sha256(raw_token.encode()).hexdigest()
