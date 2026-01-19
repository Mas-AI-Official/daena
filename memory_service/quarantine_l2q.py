"""
Simple JSON-backed quarantine store for untrusted memory items.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


class L2Quarantine:
    def __init__(self, root: str | Path = ".l2q"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, item_id: str, tenant_id: Optional[str] = None) -> Path:
        """Generate path with tenant isolation."""
        # Prefix with tenant_id for isolation if provided
        safe_item_id = item_id.replace('/', '_')
        if tenant_id and tenant_id != "default":
            safe_item_id = f"{tenant_id}_{safe_item_id}"
        return self.root / f"{safe_item_id}.json"

    def write(self, item_id: str, nbmf: Dict[str, Any], meta: Dict[str, Any]) -> str:
        """Write to quarantine with tenant isolation."""
        # Extract tenant_id from meta for isolation
        tenant_id = meta.get("tenant_id") or meta.get("tenant")
        record = {"nbmf": nbmf, "meta": meta, "trust": 0.0, "tenant_id": tenant_id}
        path = self._path(item_id, tenant_id)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False)
        return str(path)

    def read(self, item_id: str, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Read from quarantine with tenant isolation."""
        # Try with tenant_id first if provided
        if tenant_id:
            path = self._path(item_id, tenant_id)
            if path.exists():
                with path.open("r", encoding="utf-8") as fh:
                    record = json.load(fh)
                    # Verify tenant_id matches
                    if record.get("tenant_id") == tenant_id:
                        return record
        
        # Fallback: try without tenant_id (for backward compatibility)
        path = self._path(item_id)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as fh:
            record = json.load(fh)
            # If tenant_id provided, verify match
            if tenant_id and record.get("tenant_id") and record.get("tenant_id") != tenant_id:
                return None  # Tenant mismatch - don't return
            return record

    def update_trust(self, item_id: str, score: float, tenant_id: Optional[str] = None) -> None:
        """Update trust score with tenant isolation."""
        record = self.read(item_id, tenant_id)
        if record is None:
            return
        record["trust"] = max(0.0, min(1.0, score))
        # Use tenant_id from record or parameter
        effective_tenant_id = record.get("tenant_id") or tenant_id
        with self._path(item_id, effective_tenant_id).open("w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False)

