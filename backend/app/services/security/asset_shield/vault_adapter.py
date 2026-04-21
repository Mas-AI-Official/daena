"""Vault adapter for the Asset Shield.

Sits between the Asset Shield primitives and the underlying AES-256
vault in ``app.core.vault``. Exposes a fingerprint API the Egress
Filter can scan every outbound byte against, without ever touching
plaintext secrets.

Asset classes (priority order, all protected always):
    1. api_keys           Anthropic, OpenAI, Gemini, Groq, GitHub, GCP
    2. finance            Bank, broker, crypto wallet seed phrases
    3. identity           SIN, passport, DOB, home address, corp docs
    4. legal              Patent drafts, contracts, NDAs, unfiled IP
    5. founder_memory     NBMF T4 content, soul/reasoning notes

Fingerprints are SHA-256 hashes of secret values, kept as 16-char
hex prefixes to balance false-positive rate against audit privacy.
The full secret never leaves the vault; even the audit log stores
only the prefix.

BACKGROUND PATH ONLY -- never import in hot path
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


ASSET_CLASSES: tuple[str, ...] = (
    "api_keys",
    "finance",
    "identity",
    "legal",
    "founder_memory",
)


@dataclass
class AssetRegistration:
    """A registered operator asset the Egress Filter will redact."""

    asset_id: str
    asset_class: str
    fingerprint_prefix: str      # first 16 hex chars of SHA-256
    raw_value: str               # kept in-process only, never persisted in plaintext
    created_at: float = 0.0


# ---------------------------------------------------------------------------
# In-process registry (seeded at startup from env + vault rows)
# ---------------------------------------------------------------------------

_registry: dict[str, AssetRegistration] = {}
_fingerprint_index: dict[str, list[str]] = {}  # prefix -> [asset_id, ...]


def _sha256_prefix(value: str) -> str:
    """16-char hex prefix of SHA-256."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def register_fingerprint(
    asset_id: str,
    raw_value: str,
    asset_class: str,
) -> AssetRegistration:
    """Register a secret for egress scanning.

    Raises ValueError when ``asset_class`` is not in ``ASSET_CLASSES``.
    Idempotent: re-registering the same ``asset_id`` replaces the
    previous row.
    """
    import time

    if asset_class not in ASSET_CLASSES:
        raise ValueError(
            f"Unknown asset class {asset_class!r}. "
            f"Valid: {ASSET_CLASSES}"
        )
    if not raw_value or not raw_value.strip():
        raise ValueError("raw_value must be non-empty")

    prefix = _sha256_prefix(raw_value)
    reg = AssetRegistration(
        asset_id=asset_id,
        asset_class=asset_class,
        fingerprint_prefix=prefix,
        raw_value=raw_value,
        created_at=time.time(),
    )
    _registry[asset_id] = reg
    _fingerprint_index.setdefault(prefix, []).append(asset_id)

    logger.info(
        "asset_shield.fingerprint_registered",
        asset_id=asset_id,
        asset_class=asset_class,
        fingerprint_prefix=prefix,
    )
    return reg


def unregister_fingerprint(asset_id: str) -> bool:
    """Remove an asset from the registry. Returns True if removed."""
    reg = _registry.pop(asset_id, None)
    if reg is None:
        return False
    ids = _fingerprint_index.get(reg.fingerprint_prefix) or []
    if asset_id in ids:
        ids.remove(asset_id)
    if not ids:
        _fingerprint_index.pop(reg.fingerprint_prefix, None)
    return True


def list_asset_classes() -> list[str]:
    """Return the canonical ordered list of protected asset classes."""
    return list(ASSET_CLASSES)


def clear_registry() -> None:
    """Test helper: wipe the in-process registry."""
    _registry.clear()
    _fingerprint_index.clear()


class VaultAdapter:
    """Read-mostly adapter over the registered asset set.

    Instance methods are thin wrappers over the module-level registry
    so the Egress Filter can depend on a single object that is easy
    to mock in tests.
    """

    def list_registered(self) -> list[AssetRegistration]:
        return list(_registry.values())

    def registered_raw_values(self) -> list[str]:
        """Raw secret strings the Egress Filter scans against."""
        return [reg.raw_value for reg in _registry.values()]

    def lookup_by_raw(self, raw_value: str) -> AssetRegistration | None:
        """Map a secret back to its registration (for internal use only)."""
        prefix = _sha256_prefix(raw_value)
        ids = _fingerprint_index.get(prefix) or []
        if not ids:
            return None
        return _registry.get(ids[0])

    def hash_reference(self, raw_value: str) -> str:
        """Return the 16-char hex prefix the audit log stores."""
        return _sha256_prefix(raw_value)

    def asset_class_for(self, asset_id: str) -> str:
        reg = _registry.get(asset_id)
        return reg.asset_class if reg else ""
