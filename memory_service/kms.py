from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

MANIFEST_DIR_NAME = "manifests"


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _hash_key_material(key_material: str) -> str:
    return _sha256_bytes(key_material.encode("utf-8"))


def _compute_manifest_hash(payload: Dict[str, Any]) -> str:
    return _sha256_bytes(_json_dumps(payload).encode("utf-8"))


def _normalize_signing_key(signing_key: str) -> bytes:
    cleaned = signing_key.strip()
    for decoder in (base64.urlsafe_b64decode, base64.b64decode):
        try:
            return decoder(cleaned + "=" * (-len(cleaned) % 4))
        except (binascii.Error, ValueError):
            continue
    return cleaned.encode("utf-8")


def _sign_manifest(manifest_hash: str, signing_key: str) -> str:
    key_bytes = _normalize_signing_key(signing_key)
    digest = hmac.new(key_bytes, manifest_hash.encode("utf-8"), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _manifest_payload(manifest: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(manifest)
    payload.pop("manifest_hash", None)
    payload.pop("signature", None)
    return payload


class KeyManagementService:
    """
    Record key rotations, emit manifests, and optionally forward events to an external endpoint.
    Supports integration with cloud KMS providers (AWS, Azure, GCP).
    """

    def __init__(
        self,
        *,
        log_path: str | Path = ".kms/kms_log.jsonl",
        manifest_dir: str | Path | None = None,
        endpoint: Optional[str] = None,
        cloud_kms_provider: Optional[str] = None,
    ) -> None:
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_dir = (
            Path(manifest_dir)
            if manifest_dir is not None
            else self.log_path.parent / MANIFEST_DIR_NAME
        )
        self.manifest_dir.mkdir(parents=True, exist_ok=True)
        self.endpoint = endpoint or os.getenv("DAENA_KMS_ENDPOINT")
        
        # Initialize cloud KMS adapter if configured
        self.cloud_kms = None
        try:
            from .cloud_kms import get_cloud_kms_adapter
            self.cloud_kms = get_cloud_kms_adapter(cloud_kms_provider)
            if self.cloud_kms:
                import logging
                logger = logging.getLogger(__name__)
                logger.info("✅ Cloud KMS adapter initialized")
        except ImportError:
            pass

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def _write_log(self, entry: Dict[str, Any]) -> None:
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _post_to_endpoint(self, entry: Dict[str, Any]) -> Optional[str]:
        if not self.endpoint:
            return None
        payload = json.dumps(entry).encode("utf-8")
        request = urllib.request.Request(
            self.endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        # Retry logic with exponential backoff
        max_retries = 3
        for attempt in range(max_retries):
            try:
                timeout = 5 * (2 ** attempt)  # Exponential backoff: 5s, 10s, 20s
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    return response.read().decode("utf-8")
            except urllib.error.URLError as exc:
                if attempt == max_retries - 1:
                    # Last attempt failed - return error
                    return str(exc)
                # Wait before retry (simple sleep, could use time.sleep in production)
                import time
                time.sleep(0.5 * (2 ** attempt))  # 0.5s, 1s, 2s
        return None

    def record_rotation(
        self,
        key_material: str,
        *,
        key_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        store_in_cloud: bool = True,
    ) -> Dict[str, Any]:
        """
        Record key rotation.
        
        Args:
            key_material: The encryption key material
            key_id: Key identifier
            metadata: Optional metadata
            store_in_cloud: If True and cloud KMS is configured, store key in cloud KMS
        """
        entry: Dict[str, Any] = {
            "timestamp": time.time(),
            "key_id": key_id,
            "key_material": key_material,
            "metadata": metadata or {},
        }
        self._write_log(entry)
        
        # Store in cloud KMS if configured
        if store_in_cloud and self.cloud_kms:
            try:
                # Create or update key in cloud KMS
                self.cloud_kms.create_key(key_id, key_material)
                entry["cloud_kms_stored"] = True
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to store key in cloud KMS: {e}")
                entry["cloud_kms_error"] = str(e)
        
        error = self._post_to_endpoint(entry)
        if error:
            entry["forward_error"] = error
        return entry
    
    def get_key_from_cloud(self, key_id: str) -> Optional[str]:
        """
        Retrieve key from cloud KMS if configured.
        
        Args:
            key_id: Key identifier
            
        Returns:
            Key material or None if not found/not configured
        """
        if not self.cloud_kms:
            return None
        
        try:
            return self.cloud_kms.get_key(key_id)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to get key from cloud KMS: {e}")
            return None

    # ------------------------------------------------------------------
    # Manifest helpers
    # ------------------------------------------------------------------
    def _manifest_files(self) -> Iterable[Path]:
        return sorted(self.manifest_dir.glob("*.json"))

    def load_last_manifest(self) -> Optional[Dict[str, Any]]:
        files = list(self._manifest_files())
        if not files:
            return None
        return json.loads(files[-1].read_text(encoding="utf-8"))

    def _write_manifest(self, manifest: Dict[str, Any]) -> Path:
        ts = int(manifest.get("timestamp", time.time()))
        manifest_id = manifest.get("manifest_id", "unknown")
        path = self.manifest_dir / f"{ts}_{manifest_id}.json"
        path.write_text(_json_dumps(manifest), encoding="utf-8")
        return path

    def create_manifest(
        self,
        *,
        key_material: str,
        key_id: str,
        operator: Optional[str],
        signing_key: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], Path]:
        key_hash = _hash_key_material(key_material)
        prev_manifest = self.load_last_manifest()
        payload = {
            "manifest_id": str(uuid.uuid4()),
            "timestamp": time.time(),
            "key_id": key_id,
            "key_hash": key_hash,
            "operator": operator or os.getenv("DAENA_OPERATOR", "unknown"),
            "prev_manifest_hash": prev_manifest.get("manifest_hash") if prev_manifest else None,
            "metadata": metadata or {},
        }
        manifest_hash = _compute_manifest_hash(payload)
        manifest = dict(payload)
        manifest["manifest_hash"] = manifest_hash
        if signing_key:
            manifest["signature"] = _sign_manifest(manifest_hash, signing_key)
        path = self._write_manifest(manifest)
        return manifest, path

    # ------------------------------------------------------------------
    # Verification helpers (used by CLI)
    # ------------------------------------------------------------------
    def iter_manifests(self) -> Iterable[Dict[str, Any]]:
        for path in self._manifest_files():
            yield json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def verify_manifest(manifest: Dict[str, Any], signing_key: Optional[str]) -> bool:
        expected_hash = _compute_manifest_hash(_manifest_payload(manifest))
        if expected_hash != manifest.get("manifest_hash"):
            return False
        signature = manifest.get("signature")
        if signature and signing_key:
            expected_sig = _sign_manifest(expected_hash, signing_key)
            return hmac.compare_digest(signature, expected_sig)
        if signature and not signing_key:
            return False
        return True


def default_kms() -> KeyManagementService:
    return KeyManagementService()

