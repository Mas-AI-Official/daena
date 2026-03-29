"""Vault: AES-256-GCM encryption for secrets at rest.

Encrypts sensitive data (OAuth credentials, API keys) before database
storage.  Decrypts transparently on read.  Uses the ``vault_encryption_key``
from ``config.py``.

Ciphertext format (single base64-encoded string, safe for JSONB):
    base64( 12-byte nonce || ciphertext || 16-byte GCM tag )

Key derivation: SHA-256 of the raw config value, guaranteeing exactly
32 bytes regardless of user input length.

When the key is a known placeholder (dev mode), encryption is skipped
and data is stored/read as plaintext JSON.  A warning is logged on
first use.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from functools import lru_cache

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_NONCE_BYTES = 12
_ENCRYPTED_PREFIX = "enc:v1:"
_PLACEHOLDER_VALUES = frozenset({
    "CHANGE-ME-32-byte-key-for-aes256",
    "",
})


@lru_cache(maxsize=1)
def _derive_key() -> bytes | None:
    """Derive a 32-byte AES-256 key from the configured vault secret.

    Returns ``None`` if the configured key is a placeholder, meaning
    encryption should be skipped (dev mode).
    """
    raw = get_settings().vault_encryption_key
    if raw in _PLACEHOLDER_VALUES:
        logger.warning(
            "vault.placeholder_key",
            msg="Vault encryption key is a placeholder. "
            "Credentials will be stored as plaintext. "
            "Set VAULT_ENCRYPTION_KEY in .env for production.",
        )
        return None
    return hashlib.sha256(raw.encode("utf-8")).digest()


def _get_aesgcm() -> AESGCM | None:
    """Return an AESGCM cipher, or None if in placeholder mode."""
    key = _derive_key()
    if key is None:
        return None
    return AESGCM(key)


def encrypt_dict(data: dict) -> str:
    """Encrypt a dict to a single string for database storage.

    Args:
        data: Arbitrary JSON-serializable dict (e.g. OAuth credentials).

    Returns:
        Prefixed base64 ciphertext string, or JSON string if in
        placeholder mode.
    """
    if not data:
        return ""

    cipher = _get_aesgcm()
    if cipher is None:
        # Dev mode: store as plain JSON with no prefix
        return json.dumps(data, separators=(",", ":"))

    plaintext = json.dumps(data, separators=(",", ":")).encode("utf-8")
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = cipher.encrypt(nonce, plaintext, None)
    # nonce (12) + ciphertext + tag (16, appended by GCM)
    encoded = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
    return _ENCRYPTED_PREFIX + encoded


def decrypt_dict(value: str) -> dict | None:
    """Decrypt a stored credential string back to a dict.

    Handles both encrypted (prefixed) and plaintext (legacy/dev) values.

    Args:
        value: The stored string from the database.

    Returns:
        Decrypted dict, or None if value is empty/None.
    """
    if not value:
        return None

    if not value.startswith(_ENCRYPTED_PREFIX):
        # Plaintext JSON (dev mode or legacy data)
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            logger.error("vault.decrypt_failed_plaintext", value_preview=value[:20])
            return None

    cipher = _get_aesgcm()
    if cipher is None:
        logger.error(
            "vault.cannot_decrypt_without_key",
            msg="Encrypted credentials found but vault key is placeholder. "
            "Set VAULT_ENCRYPTION_KEY to the production value.",
        )
        return None

    try:
        raw = base64.urlsafe_b64decode(value[len(_ENCRYPTED_PREFIX):])
        nonce = raw[:_NONCE_BYTES]
        ciphertext = raw[_NONCE_BYTES:]
        plaintext = cipher.decrypt(nonce, ciphertext, None)
        return json.loads(plaintext)
    except Exception:
        logger.error("vault.decrypt_failed", exc_info=True)
        return None


def is_encrypted(value: str | None) -> bool:
    """Check if a stored value is vault-encrypted."""
    return bool(value and value.startswith(_ENCRYPTED_PREFIX))


def reset_key_cache() -> None:
    """Clear the cached derived key.  Used in tests."""
    _derive_key.cache_clear()
