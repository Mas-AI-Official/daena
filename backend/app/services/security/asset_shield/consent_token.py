"""Scoped Consent Token: one-shot credential lease for pivot ops.

When an offensive op genuinely needs an operator credential to
proceed (authenticating to the target API with Masoud's dev account
to pivot into a restricted area), a ConsentToken is minted from the
vault. The token is:

    * one-shot         used exactly once, then revoked
    * destination-bound carries the destination URL/host it's
                       permitted for; mismatches raise
    * time-limited     default 30s, max 10 minutes
    * hash-referenced  audit log stores only the first 16 hex chars
                       of the token_id, never the secret

``mint_token`` returns a ConsentToken; ``use_token`` returns the
underlying secret once and flips the token to revoked. Subsequent
uses raise ``ConsentTokenRevoked``; expired tokens raise
``ConsentTokenExpired``.

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


MAX_EXPIRY_SECONDS = 600  # 10 minutes hard cap
DEFAULT_EXPIRY_SECONDS = 30


class ConsentTokenError(Exception):
    """Base for consent-token errors."""


class ConsentTokenExpired(ConsentTokenError):
    pass


class ConsentTokenRevoked(ConsentTokenError):
    pass


class ConsentTokenScopeMismatch(ConsentTokenError):
    pass


@dataclass
class ConsentToken:
    token_id: str
    asset_id: str
    destination: str
    op_type: str
    expires_at: float
    used_at: float = 0.0
    revoked: bool = False
    # Full secret lives in the mint response only; never stored on
    # the token record. This is a pointer; ``use_token`` dereferences
    # via the vault.


# ---------------------------------------------------------------------------
# Per-process token store
# ---------------------------------------------------------------------------

_tokens: dict[str, ConsentToken] = {}


def clear_tokens() -> None:
    """Test helper."""
    _tokens.clear()


def mint_token(
    asset_id: str,
    destination: str,
    op_type: str,
    *,
    expiry_seconds: int = DEFAULT_EXPIRY_SECONDS,
) -> ConsentToken:
    """Create a new one-shot token.

    The underlying secret is NOT stored on the token record; it is
    fetched at ``use_token`` time via the VaultAdapter registry.
    Audit entry ``consent_token.minted`` records destination + op_type
    + 16-char prefix, never plaintext.
    """
    if not asset_id:
        raise ValueError("asset_id is required")
    if not destination:
        raise ValueError("destination is required")
    if not op_type:
        raise ValueError("op_type is required")
    expiry = min(max(int(expiry_seconds or 0), 1), MAX_EXPIRY_SECONDS)

    token_id = uuid.uuid4().hex
    token = ConsentToken(
        token_id=token_id,
        asset_id=asset_id,
        destination=destination,
        op_type=op_type,
        expires_at=time.time() + expiry,
    )
    _tokens[token_id] = token

    logger.info(
        "consent_token.minted",
        token_prefix=token_id[:16],
        asset_id=asset_id,
        destination=destination,
        op_type=op_type,
        expiry_seconds=expiry,
    )
    return token


def use_token(
    token_id: str,
    *,
    for_destination: str | None = None,
) -> str:
    """Consume the token and return the underlying secret value.

    After a successful use, the token is flipped to ``revoked=True``.
    Every use is audit-logged with the 16-char token prefix only.

    Raises:
        KeyError: token_id unknown.
        ConsentTokenRevoked: token was already used or manually revoked.
        ConsentTokenExpired: expires_at has passed.
        ConsentTokenScopeMismatch: caller's destination does not match
            the token scope.
    """
    from app.services.security.asset_shield.vault_adapter import VaultAdapter

    token = _tokens.get(token_id)
    if token is None:
        raise KeyError(f"consent token {token_id[:16]} not found")

    if token.revoked:
        raise ConsentTokenRevoked("token already used or revoked")
    if time.time() > token.expires_at:
        token.revoked = True  # clean up
        raise ConsentTokenExpired("token expired")

    if for_destination and for_destination != token.destination:
        raise ConsentTokenScopeMismatch(
            f"expected destination={token.destination!r}, "
            f"got {for_destination!r}"
        )

    vault = VaultAdapter()
    registry = {reg.asset_id: reg for reg in vault.list_registered()}
    reg = registry.get(token.asset_id)
    if reg is None:
        raise KeyError(
            f"asset {token.asset_id!r} is not registered in the vault"
        )

    token.used_at = time.time()
    token.revoked = True

    logger.info(
        "consent_token.used",
        token_prefix=token_id[:16],
        asset_id=token.asset_id,
        destination=token.destination,
        op_type=token.op_type,
    )
    return reg.raw_value


def revoke_token(token_id: str) -> bool:
    """Manually revoke a token (e.g. on scan cancel). Returns True if
    an active token was revoked.
    """
    token = _tokens.get(token_id)
    if token is None or token.revoked:
        return False
    token.revoked = True
    logger.info("consent_token.revoked", token_prefix=token_id[:16])
    return True


def get_token(token_id: str) -> ConsentToken | None:
    """Inspect a token without consuming it."""
    return _tokens.get(token_id)
