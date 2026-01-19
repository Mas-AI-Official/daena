"""
JSON-backed warm store for NBMF payloads.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from ..crypto import read_secure_json, write_secure_json


class L2Store:
    def __init__(self, root: str | Path = ".l2_store"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "records").mkdir(exist_ok=True)
        (self.root / "blobs").mkdir(exist_ok=True)

    def _record_path(self, key: str, cls: str) -> Path:
        safe_key = key.replace("/", "_")
        safe_cls = cls.replace("/", "_")
        return self.root / "records" / f"{safe_key}__{safe_cls}.json"

    def _find_any_record(self, key: str) -> Optional[Path]:
        safe_key = key.replace("/", "_")
        matches = list((self.root / "records").glob(f"{safe_key}__*.json"))
        return matches[0] if matches else None

    def put_record(self, key: str, cls: str, payload: Any, meta: Dict[str, Any] | None = None) -> str:
        data = {"payload": payload, "meta": meta or {}, "cls": cls}
        path = self._record_path(key, cls)
        try:
            write_secure_json(path, data)
        except (OSError, PermissionError) as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to write L2 record {key}:{cls} to {path}: {e}")
            raise RuntimeError(f"L2 store write failed: {e}") from e
        return path.name

    def get_record(self, key: str, cls: str, tenant_id: Optional[str] = None) -> Optional[Any]:
        """
        Get record with tenant isolation enforcement.
        
        CRITICAL: If tenant_id is provided, verify it matches record metadata.
        This prevents cross-tenant data leakage.
        """
        path = self._record_path(key, cls)
        if not path.exists():
            if cls != "*":
                return self.get_record(key, "*", tenant_id)
            path = self._find_any_record(key)
            if path is None:
                return None
        data = read_secure_json(path)
        
        # SECURITY: Verify tenant_id matches if provided
        if tenant_id and tenant_id != "default":
            record_tenant = data.get("meta", {}).get("tenant_id")
            if record_tenant and record_tenant != tenant_id:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Tenant mismatch: requested {tenant_id}, record has {record_tenant} - rejecting access")
                return None  # SECURITY: Reject cross-tenant access
        
        return data.get("payload")

    def get_full_record(self, key: str, cls: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get full record with tenant isolation enforcement.
        
        CRITICAL: If tenant_id is provided, verify it matches record metadata.
        This prevents cross-tenant data leakage.
        """
        path = self._record_path(key, cls)
        if not path.exists():
            if cls != "*":
                return self.get_full_record(key, "*", tenant_id)
            path = self._find_any_record(key)
            if path is None:
                return None
        try:
            data = read_secure_json(path)
            
            # SECURITY: Verify tenant_id matches if provided
            if tenant_id and tenant_id != "default":
                record_tenant = data.get("meta", {}).get("tenant_id")
                if record_tenant and record_tenant != tenant_id:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"Tenant mismatch: requested {tenant_id}, record has {record_tenant} - rejecting access")
                    return None  # SECURITY: Reject cross-tenant access
            
            return data
        except (OSError, PermissionError, json.JSONDecodeError) as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to read L2 record {key}:{cls} from {path}: {e}")
            return None

    def exists(self, key: str, cls: str) -> bool:
        path = self._record_path(key, cls)
        if path.exists():
            return True
        if cls == "*":
            return self._find_any_record(key) is not None
        return self.exists(key, "*")

    def list_ids(self) -> list[str]:
        ids = set()
        for path in (self.root / "records").glob("*.json"):
            stem = path.stem.split("__")[0]
            ids.add(stem)
        return list(ids)

    def iter_records(self):
        """Iterate over all records, yielding (item_id, cls, full_record)."""
        for path in (self.root / "records").glob("*.json"):
            try:
                parts = path.stem.split("__")
                if len(parts) == 2:
                    item_id, cls = parts
                    record = read_secure_json(path)
                    if record:
                        yield item_id, cls, record
            except Exception:
                # Skip corrupted files
                continue

    def put(self, payload: Dict[str, Any]) -> str:
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        name = str(abs(hash(data)))
        path = self.root / "blobs" / f"{name}.json"
        path.write_bytes(data)
        return name

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        path = self.root / "blobs" / f"{key}.json"
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))


class L2NBMFStore(L2Store):
    """Alias used by bridge/client helpers."""

    pass

