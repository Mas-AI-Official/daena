"""Tests for backend/app/core/vault_boot.py (Phase 4a-2).

Covers KEK loading from env, refuse-to-boot in production, dev fallback,
encoding validation (hex / base64 / invalid), legacy env-var fallback,
and the sha256_prefix logging helper.

Pure-functional module; tests use ``monkeypatch.setenv`` for isolation.
"""

from __future__ import annotations

import base64

import pytest

from app.core.constants import (
    DAENA_KEK_ENV,
    KEK_BYTE_LENGTH,
    LEGACY_VAULT_KEK_ENV,
    PLACEHOLDER_KEK_VALUES,
)
from app.core.vault_boot import (
    DEV_FALLBACK_KEK,
    RefuseToBoot,
    kek_sha256_prefix,
    load_kek_from_env,
)


# ──────────────────────────────────────────────────────────────────
# Fixtures / helpers
# ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Every test starts with both env vars cleared."""
    monkeypatch.delenv(DAENA_KEK_ENV, raising=False)
    monkeypatch.delenv(LEGACY_VAULT_KEK_ENV, raising=False)
    yield


def _hex_kek() -> str:
    """64-char hex string for 32 random bytes."""
    return ("a1b2c3d4" * 8)  # deterministic 64-char hex


def _b64_kek() -> str:
    """44-char base64 string for 32 random bytes."""
    return base64.b64encode(b"k" * KEK_BYTE_LENGTH).decode("ascii")


# ──────────────────────────────────────────────────────────────────
# Production refuse-to-boot
# ──────────────────────────────────────────────────────────────────


class TestProductionRefuseToBoot:
    def test_missing_kek_in_production_raises(self):
        with pytest.raises(RefuseToBoot, match=DAENA_KEK_ENV):
            load_kek_from_env(is_production=True)

    def test_placeholder_kek_in_production_raises(self, monkeypatch):
        monkeypatch.setenv(DAENA_KEK_ENV, "CHANGE-ME-32-byte-key-for-aes256")
        with pytest.raises(RefuseToBoot):
            load_kek_from_env(is_production=True)

    def test_empty_kek_in_production_raises(self, monkeypatch):
        monkeypatch.setenv(DAENA_KEK_ENV, "")
        with pytest.raises(RefuseToBoot):
            load_kek_from_env(is_production=True)

    def test_invalid_encoding_in_production_raises(self, monkeypatch):
        monkeypatch.setenv(DAENA_KEK_ENV, "this-is-not-hex-or-base64")
        with pytest.raises(RefuseToBoot, match="invalid encoding"):
            load_kek_from_env(is_production=True)

    def test_wrong_length_hex_in_production_raises(self, monkeypatch):
        monkeypatch.setenv(DAENA_KEK_ENV, "a" * 32)  # 32 chars != 64
        with pytest.raises(RefuseToBoot, match="invalid encoding"):
            load_kek_from_env(is_production=True)

    def test_wrong_length_base64_in_production_raises(self, monkeypatch):
        # base64 encoding of 16 bytes = 24 chars, not 44
        short_b64 = base64.b64encode(b"a" * 16).decode("ascii")
        monkeypatch.setenv(DAENA_KEK_ENV, short_b64)
        with pytest.raises(RefuseToBoot, match="invalid encoding"):
            load_kek_from_env(is_production=True)


# ──────────────────────────────────────────────────────────────────
# Production happy path
# ──────────────────────────────────────────────────────────────────


class TestProductionHappyPath:
    def test_hex_kek_in_production_returns_32_bytes(self, monkeypatch):
        monkeypatch.setenv(DAENA_KEK_ENV, _hex_kek())
        result = load_kek_from_env(is_production=True)
        assert isinstance(result, bytes)
        assert len(result) == KEK_BYTE_LENGTH
        assert result == bytes.fromhex(_hex_kek())

    def test_base64_kek_in_production_returns_32_bytes(self, monkeypatch):
        monkeypatch.setenv(DAENA_KEK_ENV, _b64_kek())
        result = load_kek_from_env(is_production=True)
        assert len(result) == KEK_BYTE_LENGTH
        assert result == base64.b64decode(_b64_kek())


# ──────────────────────────────────────────────────────────────────
# Dev fallback
# ──────────────────────────────────────────────────────────────────


class TestDevFallback:
    def test_missing_kek_in_dev_returns_dev_fallback(self):
        result = load_kek_from_env(is_production=False)
        assert result == DEV_FALLBACK_KEK
        assert len(result) == KEK_BYTE_LENGTH

    def test_placeholder_kek_in_dev_returns_dev_fallback(self, monkeypatch):
        monkeypatch.setenv(DAENA_KEK_ENV, "CHANGE-ME")
        result = load_kek_from_env(is_production=False)
        assert result == DEV_FALLBACK_KEK

    def test_invalid_encoding_in_dev_returns_dev_fallback(self, monkeypatch):
        monkeypatch.setenv(DAENA_KEK_ENV, "garbage value")
        result = load_kek_from_env(is_production=False)
        assert result == DEV_FALLBACK_KEK

    def test_dev_fallback_is_deterministic(self):
        a = load_kek_from_env(is_production=False)
        b = load_kek_from_env(is_production=False)
        assert a == b

    def test_dev_fallback_is_not_a_known_real_key_pattern(self):
        # Sanity: the dev fallback must not be all zeros or any obvious
        # pattern that an attacker would try first.
        assert DEV_FALLBACK_KEK != b"\x00" * KEK_BYTE_LENGTH
        assert DEV_FALLBACK_KEK != b"\xff" * KEK_BYTE_LENGTH
        assert len(set(DEV_FALLBACK_KEK)) > 8  # at least 8 distinct byte values

    def test_valid_kek_in_dev_uses_provided_kek_not_fallback(self, monkeypatch):
        monkeypatch.setenv(DAENA_KEK_ENV, _hex_kek())
        result = load_kek_from_env(is_production=False)
        assert result == bytes.fromhex(_hex_kek())
        assert result != DEV_FALLBACK_KEK


# ──────────────────────────────────────────────────────────────────
# Legacy env var fallback
# ──────────────────────────────────────────────────────────────────


class TestLegacyEnvVar:
    def test_legacy_env_alone_is_used(self, monkeypatch):
        monkeypatch.setenv(LEGACY_VAULT_KEK_ENV, _hex_kek())
        result = load_kek_from_env(is_production=True)
        assert result == bytes.fromhex(_hex_kek())

    def test_new_env_takes_precedence_over_legacy(self, monkeypatch):
        legacy = _hex_kek()
        new = _b64_kek()
        monkeypatch.setenv(DAENA_KEK_ENV, new)
        monkeypatch.setenv(LEGACY_VAULT_KEK_ENV, legacy)
        result = load_kek_from_env(is_production=True)
        assert result == base64.b64decode(new)
        assert result != bytes.fromhex(legacy)

    def test_legacy_placeholder_in_prod_raises(self, monkeypatch):
        monkeypatch.setenv(LEGACY_VAULT_KEK_ENV, "CHANGE-ME-32-byte-key-for-aes256")
        with pytest.raises(RefuseToBoot):
            load_kek_from_env(is_production=True)


# ──────────────────────────────────────────────────────────────────
# Placeholder values
# ──────────────────────────────────────────────────────────────────


class TestPlaceholderValues:
    @pytest.mark.parametrize("placeholder", sorted(PLACEHOLDER_KEK_VALUES - {""}))
    def test_each_placeholder_treated_as_unset_in_dev(self, monkeypatch, placeholder):
        monkeypatch.setenv(DAENA_KEK_ENV, placeholder)
        result = load_kek_from_env(is_production=False)
        assert result == DEV_FALLBACK_KEK

    @pytest.mark.parametrize("placeholder", sorted(PLACEHOLDER_KEK_VALUES - {""}))
    def test_each_placeholder_refuses_boot_in_prod(self, monkeypatch, placeholder):
        monkeypatch.setenv(DAENA_KEK_ENV, placeholder)
        with pytest.raises(RefuseToBoot):
            load_kek_from_env(is_production=True)


# ──────────────────────────────────────────────────────────────────
# kek_sha256_prefix
# ──────────────────────────────────────────────────────────────────


class TestKekSha256Prefix:
    def test_returns_8_hex_chars_by_default(self):
        kek = b"x" * KEK_BYTE_LENGTH
        prefix = kek_sha256_prefix(kek)
        assert len(prefix) == 8
        assert all(c in "0123456789abcdef" for c in prefix)

    def test_deterministic(self):
        kek = b"y" * KEK_BYTE_LENGTH
        assert kek_sha256_prefix(kek) == kek_sha256_prefix(kek)

    def test_differs_per_kek(self):
        a = b"a" * KEK_BYTE_LENGTH
        b = b"b" * KEK_BYTE_LENGTH
        assert kek_sha256_prefix(a) != kek_sha256_prefix(b)

    def test_does_not_leak_kek_bytes(self):
        kek = b"sensitive-secret-do-not-leak123\x00"  # exactly 32 bytes
        prefix = kek_sha256_prefix(kek)
        # The prefix MUST NOT contain the raw KEK material in any form.
        assert "sensitive" not in prefix
        assert "secret" not in prefix

    def test_rejects_wrong_length(self):
        with pytest.raises(TypeError, match="32 bytes"):
            kek_sha256_prefix(b"too-short")

    def test_custom_prefix_length(self):
        kek = b"z" * KEK_BYTE_LENGTH
        assert len(kek_sha256_prefix(kek, hex_chars=4)) == 4
        assert len(kek_sha256_prefix(kek, hex_chars=16)) == 16
