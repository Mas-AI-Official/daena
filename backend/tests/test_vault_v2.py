"""Tests for backend/app/core/vault_v2.py (Phase 4a foundation).

Covers per-task requirement set:
    1. encrypt/decrypt roundtrip
    2. wrong-tenant / wrong-AAD failure (every AAD field tested)
    3. key-version handling (KEK + DEK)
    4. malformed-ciphertext handling

Plus a few extra invariants: HKDF determinism, DEK uniqueness,
isolation across tenants, JSON-roundtrip-friendly wire format,
explicit InvalidTag wrapping.

Module is pure-functional with no side effects; tests do not need any
fixture machinery.
"""

from __future__ import annotations

import base64
import json
import os
from uuid import uuid4

import pytest

from app.core.vault_v2 import (
    DEK_BYTES,
    KEK_SEED_BYTES,
    NONCE_BYTES,
    SUPPORTED_DEK_VERSIONS,
    SUPPORTED_KEK_VERSIONS,
    TAG_BYTES,
    VAULT_FORMAT_VERSION,
    AADMismatchError,
    DEKVersionError,
    KEKVersionError,
    MalformedCiphertextError,
    SecretClass,
    TenantMismatchError,
    VaultV2Error,
    decrypt_secret,
    derive_tenant_kek,
    encrypt_secret,
    generate_dek,
    unwrap_dek,
    wrap_dek,
)


# ──────────────────────────────────────────────────────────────────
# Helpers / fixtures
# ──────────────────────────────────────────────────────────────────


def _kek_seed() -> bytes:
    return os.urandom(KEK_SEED_BYTES)


def _tenant() -> str:
    return str(uuid4())


def _make_dek_for_tenant(seed: bytes, tenant_id: str) -> bytes:
    """Generate a DEK and round-trip it through wrap/unwrap to confirm
    we have the on-the-wire form working before testing higher layers."""
    kek = derive_tenant_kek(seed, tenant_id)
    dek = generate_dek()
    wrapped = wrap_dek(dek, kek)
    return unwrap_dek(wrapped, kek)


# ──────────────────────────────────────────────────────────────────
# 1. Encrypt / decrypt roundtrip
# ──────────────────────────────────────────────────────────────────


class TestRoundtrip:
    def test_basic_roundtrip(self):
        seed = _kek_seed()
        tid = _tenant()
        dek = _make_dek_for_tenant(seed, tid)

        plaintext = b"sk-fake-anthropic-token-do-not-use"
        record = encrypt_secret(
            plaintext,
            dek=dek,
            secret_class=SecretClass.API_KEY,
            tenant_id=tid,
            bound_to="connection_v2:01926e7f-1234",
        )
        assert decrypt_secret(
            record,
            dek=dek,
            secret_class=SecretClass.API_KEY,
            tenant_id=tid,
            bound_to="connection_v2:01926e7f-1234",
        ) == plaintext

    def test_roundtrip_empty_plaintext(self):
        seed = _kek_seed()
        tid = _tenant()
        dek = _make_dek_for_tenant(seed, tid)
        record = encrypt_secret(
            b"",
            dek=dek,
            secret_class=SecretClass.OAUTH_TOKEN,
            tenant_id=tid,
            bound_to="x:1",
        )
        assert decrypt_secret(
            record,
            dek=dek,
            secret_class=SecretClass.OAUTH_TOKEN,
            tenant_id=tid,
            bound_to="x:1",
        ) == b""

    def test_roundtrip_long_plaintext(self):
        seed = _kek_seed()
        tid = _tenant()
        dek = _make_dek_for_tenant(seed, tid)
        plaintext = os.urandom(64 * 1024)  # 64 KiB
        record = encrypt_secret(
            plaintext,
            dek=dek,
            secret_class=SecretClass.MCP_ENV_VAR,
            tenant_id=tid,
            bound_to="mcp:test",
        )
        assert decrypt_secret(
            record,
            dek=dek,
            secret_class=SecretClass.MCP_ENV_VAR,
            tenant_id=tid,
            bound_to="mcp:test",
        ) == plaintext

    def test_each_class_roundtrips(self):
        seed = _kek_seed()
        tid = _tenant()
        dek = _make_dek_for_tenant(seed, tid)
        for cls in SecretClass:
            record = encrypt_secret(
                b"x" * 16,
                dek=dek,
                secret_class=cls,
                tenant_id=tid,
                bound_to=f"bound:{cls.value}",
            )
            assert decrypt_secret(
                record,
                dek=dek,
                secret_class=cls,
                tenant_id=tid,
                bound_to=f"bound:{cls.value}",
            ) == b"x" * 16


# ──────────────────────────────────────────────────────────────────
# 2. AAD / wrong-tenant failures
# ──────────────────────────────────────────────────────────────────


class TestAADFailure:
    def _record(self, tid: str, dek: bytes) -> dict:
        return encrypt_secret(
            b"secret-payload",
            dek=dek,
            secret_class=SecretClass.API_KEY,
            tenant_id=tid,
            bound_to="connection_v2:abc",
        )

    def test_wrong_tenant_id_at_decrypt(self):
        seed = _kek_seed()
        tid_a, tid_b = _tenant(), _tenant()
        dek = _make_dek_for_tenant(seed, tid_a)
        rec = self._record(tid_a, dek)
        with pytest.raises(TenantMismatchError):
            decrypt_secret(
                rec, dek=dek, secret_class=SecretClass.API_KEY,
                tenant_id=tid_b, bound_to="connection_v2:abc",
            )

    def test_wrong_class_at_decrypt(self):
        seed = _kek_seed()
        tid = _tenant()
        dek = _make_dek_for_tenant(seed, tid)
        rec = self._record(tid, dek)
        with pytest.raises(AADMismatchError):
            decrypt_secret(
                rec, dek=dek, secret_class=SecretClass.OAUTH_TOKEN,
                tenant_id=tid, bound_to="connection_v2:abc",
            )

    def test_wrong_bound_to_at_decrypt(self):
        seed = _kek_seed()
        tid = _tenant()
        dek = _make_dek_for_tenant(seed, tid)
        rec = self._record(tid, dek)
        with pytest.raises(AADMismatchError):
            decrypt_secret(
                rec, dek=dek, secret_class=SecretClass.API_KEY,
                tenant_id=tid, bound_to="connection_v2:DIFFERENT",
            )

    def test_wrong_dek_fails_with_aad_mismatch(self):
        # Using a different DEK (random) should fail GCM tag verification.
        seed = _kek_seed()
        tid = _tenant()
        dek = _make_dek_for_tenant(seed, tid)
        rec = self._record(tid, dek)
        rogue_dek = generate_dek()
        with pytest.raises(AADMismatchError):
            decrypt_secret(
                rec, dek=rogue_dek, secret_class=SecretClass.API_KEY,
                tenant_id=tid, bound_to="connection_v2:abc",
            )

    def test_record_field_tamper_caught_before_cipher(self):
        # Mutating record["tenant_id"] in place trips the plaintext
        # sanity-check before we even attempt the GCM decrypt -- gives
        # a clearer error than raw InvalidTag.
        seed = _kek_seed()
        tid = _tenant()
        dek = _make_dek_for_tenant(seed, tid)
        rec = self._record(tid, dek)
        rec["tenant_id"] = _tenant()  # tamper
        with pytest.raises(TenantMismatchError):
            decrypt_secret(
                rec, dek=dek, secret_class=SecretClass.API_KEY,
                tenant_id=tid, bound_to="connection_v2:abc",
            )


# ──────────────────────────────────────────────────────────────────
# 3. Key version handling (KEK + DEK)
# ──────────────────────────────────────────────────────────────────


class TestVersionHandling:
    def test_unsupported_kek_version_at_wrap(self):
        seed = _kek_seed()
        kek = derive_tenant_kek(seed, _tenant())
        dek = generate_dek()
        with pytest.raises(KEKVersionError):
            wrap_dek(dek, kek, kek_version=99)

    def test_unsupported_dek_version_at_wrap(self):
        seed = _kek_seed()
        kek = derive_tenant_kek(seed, _tenant())
        dek = generate_dek()
        with pytest.raises(DEKVersionError):
            wrap_dek(dek, kek, dek_version=99)

    def test_unsupported_kek_version_at_unwrap(self):
        seed = _kek_seed()
        kek = derive_tenant_kek(seed, _tenant())
        dek = generate_dek()
        wrapped = wrap_dek(dek, kek)
        wrapped["kek_version"] = 99
        with pytest.raises(KEKVersionError):
            unwrap_dek(wrapped, kek)

    def test_unsupported_dek_version_at_unwrap(self):
        seed = _kek_seed()
        kek = derive_tenant_kek(seed, _tenant())
        dek = generate_dek()
        wrapped = wrap_dek(dek, kek)
        wrapped["dek_version"] = 99
        with pytest.raises(DEKVersionError):
            unwrap_dek(wrapped, kek)

    def test_unsupported_dek_version_at_decrypt(self):
        seed = _kek_seed()
        tid = _tenant()
        dek = _make_dek_for_tenant(seed, tid)
        rec = encrypt_secret(
            b"x", dek=dek, secret_class=SecretClass.API_KEY,
            tenant_id=tid, bound_to="bound:1",
        )
        rec["dek_version"] = 99
        with pytest.raises(DEKVersionError):
            decrypt_secret(
                rec, dek=dek, secret_class=SecretClass.API_KEY,
                tenant_id=tid, bound_to="bound:1",
            )

    def test_supported_versions_are_what_we_documented(self):
        # Phase-4a-1 ships v1 only. New versions are explicit code
        # changes, not silent additions.
        assert SUPPORTED_KEK_VERSIONS == frozenset({1})
        assert SUPPORTED_DEK_VERSIONS == frozenset({1})
        assert VAULT_FORMAT_VERSION == 2


# ──────────────────────────────────────────────────────────────────
# 4. Malformed ciphertext handling
# ──────────────────────────────────────────────────────────────────


class TestMalformedCiphertext:
    def test_decrypt_missing_required_field(self):
        seed = _kek_seed()
        tid = _tenant()
        dek = _make_dek_for_tenant(seed, tid)
        rec = encrypt_secret(
            b"x", dek=dek, secret_class=SecretClass.API_KEY,
            tenant_id=tid, bound_to="b:1",
        )
        del rec["nonce"]
        with pytest.raises(MalformedCiphertextError, match="missing fields"):
            decrypt_secret(
                rec, dek=dek, secret_class=SecretClass.API_KEY,
                tenant_id=tid, bound_to="b:1",
            )

    def test_decrypt_bad_format_version(self):
        seed = _kek_seed()
        tid = _tenant()
        dek = _make_dek_for_tenant(seed, tid)
        rec = encrypt_secret(
            b"x", dek=dek, secret_class=SecretClass.API_KEY,
            tenant_id=tid, bound_to="b:1",
        )
        rec["format_version"] = 99
        with pytest.raises(MalformedCiphertextError, match="format_version"):
            decrypt_secret(
                rec, dek=dek, secret_class=SecretClass.API_KEY,
                tenant_id=tid, bound_to="b:1",
            )

    def test_decrypt_bad_base64(self):
        seed = _kek_seed()
        tid = _tenant()
        dek = _make_dek_for_tenant(seed, tid)
        rec = encrypt_secret(
            b"x", dek=dek, secret_class=SecretClass.API_KEY,
            tenant_id=tid, bound_to="b:1",
        )
        rec["ciphertext"] = "this-is-not-base64!!"
        with pytest.raises(MalformedCiphertextError, match="invalid base64"):
            decrypt_secret(
                rec, dek=dek, secret_class=SecretClass.API_KEY,
                tenant_id=tid, bound_to="b:1",
            )

    def test_decrypt_truncated_nonce(self):
        seed = _kek_seed()
        tid = _tenant()
        dek = _make_dek_for_tenant(seed, tid)
        rec = encrypt_secret(
            b"x", dek=dek, secret_class=SecretClass.API_KEY,
            tenant_id=tid, bound_to="b:1",
        )
        # Replace nonce with a 4-byte one (legal base64, wrong length)
        rec["nonce"] = base64.b64encode(b"abcd").decode("ascii")
        with pytest.raises(MalformedCiphertextError, match="nonce/tag length"):
            decrypt_secret(
                rec, dek=dek, secret_class=SecretClass.API_KEY,
                tenant_id=tid, bound_to="b:1",
            )

    def test_unwrap_dek_missing_field(self):
        seed = _kek_seed()
        kek = derive_tenant_kek(seed, _tenant())
        wrapped = wrap_dek(generate_dek(), kek)
        del wrapped["wrap_tag"]
        with pytest.raises(MalformedCiphertextError, match="missing fields"):
            unwrap_dek(wrapped, kek)

    def test_unwrap_dek_truncated_tag(self):
        seed = _kek_seed()
        kek = derive_tenant_kek(seed, _tenant())
        wrapped = wrap_dek(generate_dek(), kek)
        wrapped["wrap_tag"] = base64.b64encode(b"abc").decode("ascii")
        with pytest.raises(MalformedCiphertextError, match="nonce/tag length"):
            unwrap_dek(wrapped, kek)

    def test_unwrap_dek_wrong_kek_raises_vault_error(self):
        seed_a, seed_b = _kek_seed(), _kek_seed()
        kek_a = derive_tenant_kek(seed_a, "tenant-x")
        kek_b = derive_tenant_kek(seed_b, "tenant-x")
        wrapped = wrap_dek(generate_dek(), kek_a)
        with pytest.raises(VaultV2Error, match="invalid tag"):
            unwrap_dek(wrapped, kek_b)


# ──────────────────────────────────────────────────────────────────
# Additional invariants
# ──────────────────────────────────────────────────────────────────


class TestInvariants:
    def test_hkdf_deterministic_for_same_tenant(self):
        seed = _kek_seed()
        tid = _tenant()
        assert derive_tenant_kek(seed, tid) == derive_tenant_kek(seed, tid)

    def test_hkdf_differs_per_tenant(self):
        seed = _kek_seed()
        a = derive_tenant_kek(seed, "tenant-A")
        b = derive_tenant_kek(seed, "tenant-B")
        assert a != b
        assert len(a) == KEK_SEED_BYTES
        assert len(b) == KEK_SEED_BYTES

    def test_hkdf_differs_per_seed(self):
        tid = _tenant()
        a = derive_tenant_kek(_kek_seed(), tid)
        b = derive_tenant_kek(_kek_seed(), tid)
        assert a != b

    def test_generate_dek_is_unique(self):
        deks = {generate_dek() for _ in range(64)}
        assert len(deks) == 64
        for dek in deks:
            assert len(dek) == DEK_BYTES

    def test_ciphertext_is_unique_per_call(self):
        # Same plaintext + same DEK + same AAD -> different ciphertext
        # (because nonce is random per encrypt). This is the GCM
        # invariant we rely on; if it ever fails, key-reuse is silent.
        seed = _kek_seed()
        tid = _tenant()
        dek = _make_dek_for_tenant(seed, tid)
        rec_a = encrypt_secret(
            b"identical", dek=dek, secret_class=SecretClass.API_KEY,
            tenant_id=tid, bound_to="x",
        )
        rec_b = encrypt_secret(
            b"identical", dek=dek, secret_class=SecretClass.API_KEY,
            tenant_id=tid, bound_to="x",
        )
        assert rec_a["ciphertext"] != rec_b["ciphertext"]
        assert rec_a["nonce"] != rec_b["nonce"]

    def test_record_is_json_roundtrippable(self):
        seed = _kek_seed()
        tid = _tenant()
        dek = _make_dek_for_tenant(seed, tid)
        rec = encrypt_secret(
            b"secret", dek=dek, secret_class=SecretClass.API_KEY,
            tenant_id=tid, bound_to="b:1",
        )
        round_tripped = json.loads(json.dumps(rec))
        assert decrypt_secret(
            round_tripped, dek=dek, secret_class=SecretClass.API_KEY,
            tenant_id=tid, bound_to="b:1",
        ) == b"secret"

    def test_uuid_tenant_normalizes_consistently(self):
        seed = _kek_seed()
        tid = uuid4()
        dek = _make_dek_for_tenant(seed, str(tid))
        rec = encrypt_secret(
            b"x", dek=dek, secret_class=SecretClass.API_KEY,
            tenant_id=tid, bound_to="b",
        )
        # Decrypt accepts both UUID and str forms of the same tenant id.
        assert decrypt_secret(
            rec, dek=dek, secret_class=SecretClass.API_KEY,
            tenant_id=tid, bound_to="b",
        ) == b"x"
        assert decrypt_secret(
            rec, dek=dek, secret_class=SecretClass.API_KEY,
            tenant_id=str(tid), bound_to="b",
        ) == b"x"

    def test_invalid_kek_seed_length_rejected(self):
        with pytest.raises(TypeError, match="32 bytes"):
            derive_tenant_kek(b"too-short", "tenant-x")

    def test_invalid_dek_length_rejected(self):
        seed = _kek_seed()
        kek = derive_tenant_kek(seed, _tenant())
        with pytest.raises(TypeError, match="32 bytes"):
            wrap_dek(b"too-short", kek)

    def test_secret_class_must_be_enum(self):
        seed = _kek_seed()
        tid = _tenant()
        dek = _make_dek_for_tenant(seed, tid)
        with pytest.raises(TypeError, match="SecretClass"):
            encrypt_secret(
                b"x", dek=dek, secret_class="api_key",  # str instead of enum
                tenant_id=tid, bound_to="b",
            )

    def test_tenant_isolation_end_to_end(self):
        # Two tenants share a KEK seed (same prod env). Tenant A's
        # secret cannot be decrypted under tenant B's DEK or KEK.
        seed = _kek_seed()
        tid_a, tid_b = _tenant(), _tenant()
        dek_a = _make_dek_for_tenant(seed, tid_a)
        dek_b = _make_dek_for_tenant(seed, tid_b)

        rec = encrypt_secret(
            b"tenant-A-only", dek=dek_a, secret_class=SecretClass.API_KEY,
            tenant_id=tid_a, bound_to="x",
        )
        # Wrong DEK -> AAD/InvalidTag
        with pytest.raises(AADMismatchError):
            decrypt_secret(
                rec, dek=dek_b, secret_class=SecretClass.API_KEY,
                tenant_id=tid_a, bound_to="x",
            )
        # Wrong tenant_id -> caught before cipher
        with pytest.raises(TenantMismatchError):
            decrypt_secret(
                rec, dek=dek_a, secret_class=SecretClass.API_KEY,
                tenant_id=tid_b, bound_to="x",
            )
