"""Vault V2: envelope-encrypted secret storage (Phase 4a foundation).

This module is the isolated NET-NEW vault foundation per ADR-002 D-003.
It is NOT yet wired into the live application. The legacy single-key
vault at ``backend/app/core/vault.py`` remains the production path
until Phase 4b's registry rewrite migrates secret storage onto V2.

Design (per V2 spec §6 + ADR-002 D-003)::

    DAENA_KEK (env, 32B)
        -> per-tenant KEK = HKDF-SHA256(KEK, salt=tenant_id, info="daena-v2-kek")
        -> per-tenant DEK = 32B random, stored in tenants.dek_wrapped
                            (AES-GCM under per-tenant KEK)
        -> secret_blob   = AES-256-GCM(plaintext, key=DEK,
                                       nonce=random_96b,
                                       aad=class || tenant_id || bound_to)

Why envelope encryption:
    Splits authorize-to-decrypt (KEK in process memory) from
    actually-encrypting-each-row (DEK in DB). Rotating the KEK does
    not require re-touching every secret -- you just re-wrap the DEK.
    Critical for multi-tenant systems where one DB compromise should
    not yield plaintext without also compromising process memory.

Why AAD bound_to:
    AES-GCM authenticates AAD without encrypting it. By binding
    class || tenant_id || bound_to, a ciphertext stolen from tenant
    A's connection_id=X cannot be replayed under tenant B or under a
    different connection_id -- the GCM tag verification fails on AAD
    change.

Why per-tenant HKDF:
    No new column needed on the KEK side; given the same DAENA_KEK
    seed and tenant_id, the per-tenant KEK is deterministic. Custody
    simplifies to one env var.

This module:
    - Pure functions; no module-level state
    - No env-var reads at import time
    - No singleton; each function takes its KEK seed / DEK explicitly
    - No imports from app.main / app.core.database / app.core.constants
    - Safe to import from tests without side effects

Module API surface (intentionally minimal for Phase 4a-1):
    derive_tenant_kek, generate_dek, wrap_dek, unwrap_dek,
    encrypt_secret, decrypt_secret, SecretClass, plus the error
    hierarchy below.
"""

from __future__ import annotations

import base64
import os
import secrets
from enum import Enum
from typing import Any
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

# Format constants
VAULT_FORMAT_VERSION = 2
KEK_SEED_BYTES = 32
DEK_BYTES = 32
NONCE_BYTES = 12
TAG_BYTES = 16

# Current code understands these versions. Older versions raise
# KEKVersionError / DEKVersionError on unwrap. New versions are
# additive and require a code update.
SUPPORTED_KEK_VERSIONS = frozenset({1})
SUPPORTED_DEK_VERSIONS = frozenset({1})

# AAD field separator -- ASCII unit separator (0x1F) cannot appear in
# any user-provided text under our schema (we only pass slugs / UUIDs
# / enum values), so it is safe as a delimiter without escaping.
_AAD_SEP = b"\x1f"

# HKDF derivation context -- bumping this string invalidates every
# previously derived per-tenant KEK; treat as part of the format
# version contract.
_HKDF_INFO = b"daena-v2-kek"


class SecretClass(str, Enum):
    """Class of secret -- bound into AAD so a ciphertext for one class
    cannot be decrypted as a different class even with the same DEK."""

    OAUTH_TOKEN = "oauth_token"
    OAUTH_CLIENT_SECRET = "oauth_client_secret"
    API_KEY = "api_key"
    MCP_ENV_VAR = "mcp_env_var"
    BRIDGE_BEARER = "bridge_bearer"


class VaultV2Error(Exception):
    """Base class for vault_v2 errors."""


class TenantMismatchError(VaultV2Error):
    """Decrypt called with a tenant_id that doesn't match the AAD."""


class AADMismatchError(VaultV2Error):
    """Decrypt called with class / bound_to / tenant_id that don't match
    the original AAD. The cipher MAC fails before we can tell which
    field changed; this error wraps the underlying InvalidTag."""


class MalformedCiphertextError(VaultV2Error):
    """Record dict is missing required fields, or fields have the wrong
    type / length, or the format_version is unsupported."""


class KEKVersionError(VaultV2Error):
    """The wrapped DEK uses a kek_version this code does not understand."""


class DEKVersionError(VaultV2Error):
    """The encrypted record uses a dek_version this code does not understand."""


def _normalize_tenant_id(tenant_id: str | UUID) -> bytes:
    """Canonicalize a tenant_id for AAD + HKDF salt purposes."""
    if isinstance(tenant_id, UUID):
        return str(tenant_id).encode("utf-8")
    if not isinstance(tenant_id, str) or not tenant_id:
        raise TypeError("tenant_id must be a non-empty str or UUID")
    return tenant_id.encode("utf-8")


def _build_aad(secret_class: SecretClass, tenant_id: str | UUID, bound_to: str) -> bytes:
    """Construct the AES-GCM AAD: class || 0x1f || tenant_id || 0x1f || bound_to.

    AAD is authenticated but not encrypted. Any change in any field
    causes the MAC to fail at decrypt time, raising AADMismatchError.
    """
    if not isinstance(secret_class, SecretClass):
        raise TypeError(f"secret_class must be SecretClass, got {type(secret_class).__name__}")
    if not isinstance(bound_to, str) or not bound_to:
        raise TypeError("bound_to must be a non-empty str")
    return _AAD_SEP.join([
        secret_class.value.encode("utf-8"),
        _normalize_tenant_id(tenant_id),
        bound_to.encode("utf-8"),
    ])


def derive_tenant_kek(kek_seed: bytes, tenant_id: str | UUID) -> bytes:
    """Derive a per-tenant 32-byte KEK from the master KEK seed and tenant_id.

    Pure function. Deterministic for the same (seed, tenant_id).

    Raises:
        TypeError if kek_seed is not bytes of length KEK_SEED_BYTES (32).
    """
    if not isinstance(kek_seed, (bytes, bytearray)) or len(kek_seed) != KEK_SEED_BYTES:
        raise TypeError(f"kek_seed must be exactly {KEK_SEED_BYTES} bytes")
    salt = _normalize_tenant_id(tenant_id)
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=_HKDF_INFO,
    ).derive(bytes(kek_seed))


def generate_dek() -> bytes:
    """Generate a fresh 32-byte DEK from os.urandom (CSPRNG).

    Each call returns independent random bytes. The caller is
    responsible for wrapping it under the per-tenant KEK and persisting
    the wrapped form (see wrap_dek).
    """
    return secrets.token_bytes(DEK_BYTES)


def wrap_dek(
    dek: bytes,
    tenant_kek: bytes,
    *,
    kek_version: int = 1,
    dek_version: int = 1,
) -> dict[str, Any]:
    """Wrap a DEK under a per-tenant KEK using AES-256-GCM.

    Returns the wire-format dict suitable for storage in
    ``tenants.dek_wrapped``. Roundtrip via ``unwrap_dek``.
    """
    if not isinstance(dek, (bytes, bytearray)) or len(dek) != DEK_BYTES:
        raise TypeError(f"dek must be exactly {DEK_BYTES} bytes")
    if not isinstance(tenant_kek, (bytes, bytearray)) or len(tenant_kek) != KEK_SEED_BYTES:
        raise TypeError(f"tenant_kek must be exactly {KEK_SEED_BYTES} bytes")
    if kek_version not in SUPPORTED_KEK_VERSIONS:
        raise KEKVersionError(f"kek_version {kek_version} not in supported {SUPPORTED_KEK_VERSIONS}")
    if dek_version not in SUPPORTED_DEK_VERSIONS:
        raise DEKVersionError(f"dek_version {dek_version} not in supported {SUPPORTED_DEK_VERSIONS}")

    nonce = os.urandom(NONCE_BYTES)
    cipher = AESGCM(bytes(tenant_kek))
    # AES-GCM appends the 16-byte tag at the end of the ciphertext.
    ct_with_tag = cipher.encrypt(nonce, bytes(dek), associated_data=None)
    ciphertext, tag = ct_with_tag[:-TAG_BYTES], ct_with_tag[-TAG_BYTES:]
    return {
        "wrapped_dek": base64.b64encode(ciphertext).decode("ascii"),
        "wrap_nonce": base64.b64encode(nonce).decode("ascii"),
        "wrap_tag": base64.b64encode(tag).decode("ascii"),
        "kek_version": kek_version,
        "dek_version": dek_version,
        "format_version": VAULT_FORMAT_VERSION,
    }


def unwrap_dek(wrapped: dict[str, Any], tenant_kek: bytes) -> bytes:
    """Unwrap a DEK from its wire form using the per-tenant KEK.

    Raises:
        MalformedCiphertextError if the dict is missing fields / wrong shapes.
        KEKVersionError if kek_version is not in SUPPORTED_KEK_VERSIONS.
        DEKVersionError if dek_version is not in SUPPORTED_DEK_VERSIONS.
        VaultV2Error (with InvalidTag chained) if the KEK is wrong.
    """
    if not isinstance(wrapped, dict):
        raise MalformedCiphertextError("wrapped must be a dict")
    if not isinstance(tenant_kek, (bytes, bytearray)) or len(tenant_kek) != KEK_SEED_BYTES:
        raise TypeError(f"tenant_kek must be exactly {KEK_SEED_BYTES} bytes")
    required = {"wrapped_dek", "wrap_nonce", "wrap_tag", "kek_version", "dek_version", "format_version"}
    missing = required - wrapped.keys()
    if missing:
        raise MalformedCiphertextError(f"wrapped missing fields: {sorted(missing)}")
    if wrapped["format_version"] != VAULT_FORMAT_VERSION:
        raise MalformedCiphertextError(
            f"unsupported format_version {wrapped['format_version']!r}; expected {VAULT_FORMAT_VERSION}"
        )
    if wrapped["kek_version"] not in SUPPORTED_KEK_VERSIONS:
        raise KEKVersionError(
            f"unsupported kek_version {wrapped['kek_version']!r}; supported: {sorted(SUPPORTED_KEK_VERSIONS)}"
        )
    if wrapped["dek_version"] not in SUPPORTED_DEK_VERSIONS:
        raise DEKVersionError(
            f"unsupported dek_version {wrapped['dek_version']!r}; supported: {sorted(SUPPORTED_DEK_VERSIONS)}"
        )

    try:
        ciphertext = base64.b64decode(wrapped["wrapped_dek"], validate=True)
        nonce = base64.b64decode(wrapped["wrap_nonce"], validate=True)
        tag = base64.b64decode(wrapped["wrap_tag"], validate=True)
    except (TypeError, ValueError, base64.binascii.Error) as exc:
        raise MalformedCiphertextError(f"invalid base64 in wrapped DEK: {exc}") from exc
    if len(nonce) != NONCE_BYTES or len(tag) != TAG_BYTES:
        raise MalformedCiphertextError(
            f"wrong nonce/tag length (got {len(nonce)}/{len(tag)}, want {NONCE_BYTES}/{TAG_BYTES})"
        )

    cipher = AESGCM(bytes(tenant_kek))
    try:
        return cipher.decrypt(nonce, ciphertext + tag, associated_data=None)
    except InvalidTag as exc:
        raise VaultV2Error("DEK unwrap failed: invalid tag (wrong KEK or tampered ciphertext)") from exc


def encrypt_secret(
    plaintext: bytes,
    *,
    dek: bytes,
    secret_class: SecretClass,
    tenant_id: str | UUID,
    bound_to: str,
    dek_version: int = 1,
    kek_version: int = 1,
) -> dict[str, Any]:
    """Encrypt a secret under a tenant's DEK, binding (class, tenant_id, bound_to) into AAD.

    The returned dict is the wire shape (matching the eventual ``secrets``
    table columns per V2 spec §6).

    AAD = class || 0x1f || tenant_id || 0x1f || bound_to.

    Note: tenant_id and class are also stored as plain fields on the
    record, but the AAD binding makes them tamper-evident -- changing
    either field on the record without re-encrypting will cause
    decrypt to fail.
    """
    if not isinstance(plaintext, (bytes, bytearray)):
        raise TypeError("plaintext must be bytes (caller should encode str -> utf-8)")
    if not isinstance(dek, (bytes, bytearray)) or len(dek) != DEK_BYTES:
        raise TypeError(f"dek must be exactly {DEK_BYTES} bytes")
    if dek_version not in SUPPORTED_DEK_VERSIONS:
        raise DEKVersionError(f"dek_version {dek_version} not supported")
    if kek_version not in SUPPORTED_KEK_VERSIONS:
        raise KEKVersionError(f"kek_version {kek_version} not supported")

    aad = _build_aad(secret_class, tenant_id, bound_to)
    nonce = os.urandom(NONCE_BYTES)
    cipher = AESGCM(bytes(dek))
    ct_with_tag = cipher.encrypt(nonce, bytes(plaintext), associated_data=aad)
    ciphertext, tag = ct_with_tag[:-TAG_BYTES], ct_with_tag[-TAG_BYTES:]
    return {
        "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "tag": base64.b64encode(tag).decode("ascii"),
        "dek_version": dek_version,
        "kek_version": kek_version,
        "tenant_id": _normalize_tenant_id(tenant_id).decode("utf-8"),
        "class": secret_class.value,
        "bound_to": bound_to,
        "format_version": VAULT_FORMAT_VERSION,
    }


def decrypt_secret(
    record: dict[str, Any],
    *,
    dek: bytes,
    secret_class: SecretClass,
    tenant_id: str | UUID,
    bound_to: str,
) -> bytes:
    """Decrypt and AAD-verify a secret record.

    The caller passes (class, tenant_id, bound_to) explicitly. They MUST
    match what the record was encrypted with -- otherwise InvalidTag
    raises (wrapped as AADMismatchError or TenantMismatchError).

    Sanity-checks are also done against the plaintext fields on the
    record (record["tenant_id"], record["class"], record["bound_to"]).
    A mismatch there raises TenantMismatchError / AADMismatchError before
    even attempting cipher work, which gives a clearer error than the
    raw InvalidTag.
    """
    if not isinstance(record, dict):
        raise MalformedCiphertextError("record must be a dict")
    if not isinstance(dek, (bytes, bytearray)) or len(dek) != DEK_BYTES:
        raise TypeError(f"dek must be exactly {DEK_BYTES} bytes")
    required = {
        "ciphertext", "nonce", "tag", "dek_version", "kek_version",
        "tenant_id", "class", "bound_to", "format_version",
    }
    missing = required - record.keys()
    if missing:
        raise MalformedCiphertextError(f"record missing fields: {sorted(missing)}")
    if record["format_version"] != VAULT_FORMAT_VERSION:
        raise MalformedCiphertextError(
            f"unsupported format_version {record['format_version']!r}; expected {VAULT_FORMAT_VERSION}"
        )
    if record["dek_version"] not in SUPPORTED_DEK_VERSIONS:
        raise DEKVersionError(
            f"unsupported dek_version {record['dek_version']!r}; supported: {sorted(SUPPORTED_DEK_VERSIONS)}"
        )
    if record["kek_version"] not in SUPPORTED_KEK_VERSIONS:
        raise KEKVersionError(
            f"unsupported kek_version {record['kek_version']!r}; supported: {sorted(SUPPORTED_KEK_VERSIONS)}"
        )

    expected_tenant = _normalize_tenant_id(tenant_id).decode("utf-8")
    if record["tenant_id"] != expected_tenant:
        raise TenantMismatchError(
            f"record tenant_id {record['tenant_id']!r} != requested {expected_tenant!r}"
        )
    if record["class"] != secret_class.value:
        raise AADMismatchError(
            f"record class {record['class']!r} != requested {secret_class.value!r}"
        )
    if record["bound_to"] != bound_to:
        raise AADMismatchError(
            f"record bound_to {record['bound_to']!r} != requested {bound_to!r}"
        )

    try:
        ciphertext = base64.b64decode(record["ciphertext"], validate=True)
        nonce = base64.b64decode(record["nonce"], validate=True)
        tag = base64.b64decode(record["tag"], validate=True)
    except (TypeError, ValueError, base64.binascii.Error) as exc:
        raise MalformedCiphertextError(f"invalid base64 in record: {exc}") from exc
    if len(nonce) != NONCE_BYTES or len(tag) != TAG_BYTES:
        raise MalformedCiphertextError(
            f"wrong nonce/tag length (got {len(nonce)}/{len(tag)}, want {NONCE_BYTES}/{TAG_BYTES})"
        )

    aad = _build_aad(secret_class, tenant_id, bound_to)
    cipher = AESGCM(bytes(dek))
    try:
        return cipher.decrypt(nonce, ciphertext + tag, associated_data=aad)
    except InvalidTag as exc:
        # Plaintext sanity-checks above already caught the obvious
        # AAD field mismatches; if we reach here the GCM tag failed
        # for a less obvious reason (wrong DEK, ciphertext tamper, or
        # an AAD field that matches the record but was changed during
        # encryption -- caller bug).
        raise AADMismatchError(
            "secret decrypt failed: invalid tag (wrong DEK, tampered ciphertext, or AAD/record drift)"
        ) from exc
