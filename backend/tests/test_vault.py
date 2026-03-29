"""Tests for the vault encryption module (AES-256-GCM).

Unit tests for encrypt/decrypt round-trips, edge cases,
tamper detection, and placeholder key behavior.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.core.vault import (
    _ENCRYPTED_PREFIX,
    decrypt_dict,
    encrypt_dict,
    is_encrypted,
    reset_key_cache,
)


@pytest.fixture(autouse=True)
def _clear_key_cache():
    """Clear the derived key cache before and after each test."""
    reset_key_cache()
    yield
    reset_key_cache()


# ── Round-trip with real key ──


class TestVaultWithRealKey:
    """Tests with a non-placeholder vault key."""

    @pytest.fixture(autouse=True)
    def _set_real_key(self):
        with patch("app.core.vault.get_settings") as mock:
            mock.return_value.vault_encryption_key = (
                "test-vault-key-for-unit-tests-32b"
            )
            yield

    def test_encrypt_decrypt_round_trip(self) -> None:
        data = {"api_key": "sk-test-123", "secret": "hunter2"}
        encrypted = encrypt_dict(data)
        assert encrypted.startswith(_ENCRYPTED_PREFIX)
        assert "sk-test-123" not in encrypted
        decrypted = decrypt_dict(encrypted)
        assert decrypted == data

    def test_encrypt_produces_different_ciphertext_each_time(self) -> None:
        data = {"token": "same-value"}
        enc1 = encrypt_dict(data)
        reset_key_cache()
        enc2 = encrypt_dict(data)
        # Different nonces produce different ciphertexts
        assert enc1 != enc2

    def test_decrypt_detects_tampered_ciphertext(self) -> None:
        data = {"key": "value"}
        encrypted = encrypt_dict(data)
        # Flip a byte in the ciphertext body
        parts = encrypted.split(":", 2)
        raw = parts[2]
        tampered = raw[:-2] + ("AA" if raw[-2:] != "AA" else "BB")
        tampered_str = f"{_ENCRYPTED_PREFIX}{tampered}"
        result = decrypt_dict(tampered_str)
        assert result is None

    def test_encrypt_empty_dict_returns_empty_string(self) -> None:
        assert encrypt_dict({}) == ""

    def test_decrypt_empty_string_returns_none(self) -> None:
        assert decrypt_dict("") is None
        assert decrypt_dict(None) is None

    def test_encrypt_nested_dict(self) -> None:
        data = {
            "oauth": {
                "access_token": "at-123",
                "refresh_token": "rt-456",
                "scopes": ["read", "write"],
            },
            "expires_in": 3600,
        }
        encrypted = encrypt_dict(data)
        decrypted = decrypt_dict(encrypted)
        assert decrypted == data

    def test_is_encrypted_detects_prefix(self) -> None:
        assert is_encrypted(f"{_ENCRYPTED_PREFIX}somedata") is True
        assert is_encrypted('{"key": "val"}') is False
        assert is_encrypted(None) is False
        assert is_encrypted("") is False


# ── Placeholder key behavior ──


class TestVaultPlaceholderKey:
    """Tests with the placeholder vault key (dev mode)."""

    @pytest.fixture(autouse=True)
    def _set_placeholder_key(self):
        with patch("app.core.vault.get_settings") as mock:
            mock.return_value.vault_encryption_key = (
                "CHANGE-ME-32-byte-key-for-aes256"
            )
            yield

    def test_placeholder_stores_plaintext_json(self) -> None:
        data = {"api_key": "sk-dev-123"}
        result = encrypt_dict(data)
        # No encryption prefix -- stored as plain JSON
        assert not result.startswith(_ENCRYPTED_PREFIX)
        parsed = json.loads(result)
        assert parsed == data

    def test_placeholder_decrypts_plaintext_json(self) -> None:
        plain = json.dumps({"api_key": "sk-dev-123"})
        result = decrypt_dict(plain)
        assert result == {"api_key": "sk-dev-123"}

    def test_placeholder_cannot_decrypt_encrypted_data(self) -> None:
        # Simulate encrypted data from production
        fake_encrypted = f"{_ENCRYPTED_PREFIX}dGVzdGRhdGE="
        result = decrypt_dict(fake_encrypted)
        assert result is None


# ── Legacy / backward compat ──


class TestVaultLegacyData:
    """Tests for reading legacy unencrypted data."""

    @pytest.fixture(autouse=True)
    def _set_real_key(self):
        with patch("app.core.vault.get_settings") as mock:
            mock.return_value.vault_encryption_key = (
                "production-vault-key-for-test"
            )
            yield

    def test_decrypt_legacy_json_string(self) -> None:
        legacy = '{"api_key":"sk-old-123","scope":"read"}'
        result = decrypt_dict(legacy)
        assert result == {"api_key": "sk-old-123", "scope": "read"}

    def test_decrypt_invalid_json_returns_none(self) -> None:
        result = decrypt_dict("not-valid-json{{{")
        assert result is None
