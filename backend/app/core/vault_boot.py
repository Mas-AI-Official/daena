"""Vault boot validation: load DAENA_KEK from env, refuse-to-boot in production.

Phase 4a-2 component. Lives outside vault_v2.py so vault_v2 stays
pure-functional with no env reads at import time.

Boot semantics::

    settings.is_production  AND  no DAENA_KEK   -> RefuseToBoot
    settings.is_production  AND  KEK present    -> return validated 32B
    not is_production       AND  no DAENA_KEK   -> return DEV_FALLBACK + WARN
    not is_production       AND  KEK present    -> return validated 32B

Env var precedence: DAENA_KEK > VAULT_ENCRYPTION_KEY (legacy fallback).
A deprecation warning fires when only the legacy var is set.

Encoding accepted: 64-char hex OR 44-char base64. Anything else raises
RefuseToBoot with a precise error so a typo cannot silently downgrade
to the dev fallback.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import os

from app.core.constants import (
    DAENA_KEK_ENV,
    KEK_BYTE_LENGTH,
    LEGACY_VAULT_KEK_ENV,
    PLACEHOLDER_KEK_VALUES,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

# Deterministic dev fallback. SHA256 of a stable string -- never a real
# secret. Used ONLY when not is_production AND no env KEK is set, with a
# loud warning. Anything decrypted under this key in prod is a bug.
_DEV_FALLBACK_SEED = b"daena-vault-v2-dev-fallback-do-not-use-in-prod"
DEV_FALLBACK_KEK: bytes = hashlib.sha256(_DEV_FALLBACK_SEED).digest()


class RefuseToBoot(RuntimeError):
    """Production boot aborted because DAENA_KEK is missing or invalid."""


def _try_decode(raw: str) -> bytes | None:
    """Try hex first (64 chars), then base64 (44 chars). Return 32 bytes or None."""
    raw = raw.strip()
    if len(raw) == 64:
        try:
            decoded = bytes.fromhex(raw)
        except ValueError:
            return None
        if len(decoded) == KEK_BYTE_LENGTH:
            return decoded
    if len(raw) == 44:
        try:
            decoded = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError):
            return None
        if len(decoded) == KEK_BYTE_LENGTH:
            return decoded
    return None


def load_kek_from_env(*, is_production: bool) -> bytes:
    """Load and validate the master KEK from env vars.

    Args:
        is_production: True if running in cloud / prod mode. When True,
            a missing or invalid KEK aborts boot. When False, missing
            KEK falls back to a deterministic DEV key with a warning.

    Returns:
        Exactly 32 bytes of KEK material.

    Raises:
        RefuseToBoot: if is_production and KEK is missing / invalid /
            still set to a known placeholder.
    """
    raw_new = os.environ.get(DAENA_KEK_ENV, "")
    raw_legacy = os.environ.get(LEGACY_VAULT_KEK_ENV, "")
    raw = raw_new or raw_legacy

    if raw_new and raw_legacy:
        logger.warning(
            "vault.kek_both_envs_set",
            using=DAENA_KEK_ENV,
            ignored=LEGACY_VAULT_KEK_ENV,
            hint="Remove the legacy env var; both are set.",
        )
    elif raw_legacy and not raw_new:
        logger.warning(
            "vault.kek_legacy_env_in_use",
            using=LEGACY_VAULT_KEK_ENV,
            target=DAENA_KEK_ENV,
            hint=f"Migrate to {DAENA_KEK_ENV} (hex 64-char or base64 44-char). "
            f"{LEGACY_VAULT_KEK_ENV} fallback will be removed post-V2.",
        )

    if not raw or raw in PLACEHOLDER_KEK_VALUES:
        if is_production:
            raise RefuseToBoot(
                f"{DAENA_KEK_ENV} is required in production "
                f"(legacy {LEGACY_VAULT_KEK_ENV} accepted but also missing or placeholder). "
                f"Set a 64-char hex or 44-char base64 value."
            )
        logger.warning(
            "vault.kek_dev_fallback",
            impact="DEV-ONLY deterministic KEK in use; never deploy this state",
            sha256_prefix=kek_sha256_prefix(DEV_FALLBACK_KEK),
        )
        return DEV_FALLBACK_KEK

    decoded = _try_decode(raw)
    if decoded is None:
        if is_production:
            raise RefuseToBoot(
                f"{DAENA_KEK_ENV} value has invalid encoding. "
                f"Expected 64-char hex or 44-char base64 yielding {KEK_BYTE_LENGTH} bytes."
            )
        logger.warning(
            "vault.kek_invalid_encoding_dev_fallback",
            impact="KEK env value rejected; using DEV fallback. NEVER deploy this.",
            hint="Use 64-char hex or 44-char base64.",
        )
        return DEV_FALLBACK_KEK

    return decoded


def kek_sha256_prefix(kek: bytes, *, hex_chars: int = 8) -> str:
    """Return first ``hex_chars`` of sha256(kek). Never returns the KEK itself.

    Used as a boot-time identity fingerprint so the operator can verify
    'the same KEK loaded today as yesterday' without leaking material.
    8 hex chars = 32 bits of identity (1-in-4B collision space).
    """
    if not isinstance(kek, (bytes, bytearray)) or len(kek) != KEK_BYTE_LENGTH:
        raise TypeError(f"kek must be exactly {KEK_BYTE_LENGTH} bytes")
    return hashlib.sha256(bytes(kek)).hexdigest()[:hex_chars]
