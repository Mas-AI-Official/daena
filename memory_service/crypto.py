from __future__ import annotations

import base64
import binascii
import json
import logging
import os
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Dict, Optional

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:  # pragma: no cover - optional dependency
    AESGCM = None  # type: ignore

LOGGER = logging.getLogger(__name__)
_KEY_ENV = "DAENA_MEMORY_AES_KEY"
_CACHE_SENTINEL = object()
_cached_env_value: object | None = _CACHE_SENTINEL
_cached_encryptor: "Encryptor" | None = None
_ENVELOPE_FIELD = "__encrypted__"


def _decode_key(raw: str) -> Optional[bytes]:
    raw = raw.strip()
    candidates = (base64.urlsafe_b64decode, base64.b64decode)
    for decoder in candidates:
        try:
            key = decoder(raw + "=" * (-len(raw) % 4))
            if key:
                return sha256(key).digest()
        except (ValueError, binascii.Error):
            continue
    try:
        key = bytes.fromhex(raw)
        if key:
            return sha256(key).digest()
    except ValueError:
        pass
    if raw:
        return sha256(raw.encode("utf-8")).digest()
    return None


@dataclass
class Encryptor:
    key: Optional[bytes]

    @property
    def enabled(self) -> bool:
        return bool(self.key and AESGCM)

    def encrypt(self, payload: bytes) -> Dict[str, str]:
        if not self.enabled:  # pragma: no cover - guard
            raise RuntimeError("Encryption requested but AES-256 is unavailable")
        aesgcm = AESGCM(self.key)  # type: ignore[arg-type]
        nonce = os.urandom(12)
        token = aesgcm.encrypt(nonce, payload, None)
        return {
            "alg": "AESGCM",
            "nonce": base64.urlsafe_b64encode(nonce).decode("ascii"),
            "ciphertext": base64.urlsafe_b64encode(token).decode("ascii"),
        }

    def decrypt(self, envelope: Dict[str, str]) -> bytes:
        if not self.enabled:
            raise RuntimeError("Encrypted payload encountered but AES-256 is unavailable")
        if envelope.get("alg") != "AESGCM":
            raise ValueError(f"Unsupported envelope algorithm: {envelope.get('alg')}")
        aesgcm = AESGCM(self.key)  # type: ignore[arg-type]
        nonce = base64.urlsafe_b64decode(envelope["nonce"])
        ciphertext = base64.urlsafe_b64decode(envelope["ciphertext"])
        return aesgcm.decrypt(nonce, ciphertext, None)


def _load_encryptor() -> Encryptor:
    global _cached_env_value, _cached_encryptor
    env_value = os.getenv(_KEY_ENV)
    if env_value == _cached_env_value and _cached_encryptor is not None:
        return _cached_encryptor
    _cached_env_value = env_value
    key = _decode_key(env_value) if env_value else None
    if key and AESGCM is None:
        LOGGER.warning("AES key provided but cryptography library is unavailable; storing plaintext.")
        key = None
    _cached_encryptor = Encryptor(key)
    return _cached_encryptor


def refresh() -> None:
    """Reset cached encryption state (mainly for tests)."""
    global _cached_env_value, _cached_encryptor
    _cached_env_value = _CACHE_SENTINEL
    _cached_encryptor = None


def refresh_key_from_kms(kms_service=None) -> bool:
    """
    Refresh encryption key from KMS manifest if available.
    
    Args:
        kms_service: Optional KMS service instance. If None, uses default.
    
    Returns:
        True if key was refreshed, False otherwise.
    """
    try:
        from .kms import default_kms
        kms = kms_service or default_kms()
        manifest = kms.load_last_manifest()
        if manifest and manifest.get("key_material"):
            # Update environment variable (would need to be set externally)
            # For now, just refresh the cache to pick up any env changes
            refresh()
            LOGGER.info("KMS manifest loaded, encryption key cache refreshed")
            return True
    except Exception as e:
        LOGGER.warning(f"Failed to refresh key from KMS: {e}")
    return False


def encryption_enabled() -> bool:
    return _load_encryptor().enabled


def write_secure_json(path, obj: Any) -> None:
    encryptor = _load_encryptor()
    if encryptor.enabled:
        payload = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        envelope = encryptor.encrypt(payload)
        baked: Dict[str, Any] = {_ENVELOPE_FIELD: envelope}
    else:
        baked = obj
    path.write_text(json.dumps(baked, ensure_ascii=False), encoding="utf-8")


def read_secure_json(path) -> Any:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if isinstance(data, dict) and _ENVELOPE_FIELD in data:
        encryptor = _load_encryptor()
        payload = encryptor.decrypt(data[_ENVELOPE_FIELD])
        return json.loads(payload.decode("utf-8"))
    return data


