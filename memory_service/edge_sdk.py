from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from .crypto import read_secure_json, write_secure_json
from .delta_encoding import apply_text_diff, text_diff
from .nbmf_encoder import encode as nbmf_encode


@dataclass
class EdgeUpdatePackage:
    tenant_id: str
    edge_id: str
    key: str
    fidelity: str
    nbmf: Dict[str, Any]
    delta: Optional[str]
    base_hash: Optional[str]
    meta: Dict[str, Any]


class EdgeNBMFClient:
    """Lightweight helper for on-device NBMF encoding and delta packaging."""

    def __init__(self, root: str | Path = ".edge_cache", edge_id: str = "edge-0") -> None:
        self.root = Path(root)
        self.edge_id = edge_id
        (self.root / "records").mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Local helpers
    # ------------------------------------------------------------------
    def _record_path(self, key: str) -> Path:
        safe = key.replace("/", "_")
        return self.root / "records" / f"{safe}.json"

    def _normalize_payload(self, payload: Any) -> str:
        if isinstance(payload, str):
            return payload
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)

    def _load_record(self, key: str) -> Optional[Dict[str, Any]]:
        path = self._record_path(key)
        if not path.exists():
            return None
        try:
            return read_secure_json(path)
        except Exception:  # pragma: no cover - corrupted cache should not break edge client
            return None

    def _store_record(self, key: str, record: Dict[str, Any]) -> None:
        path = self._record_path(key)
        write_secure_json(path, record)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def encode_payload(
        self,
        key: str,
        payload: Any,
        fidelity: str = "semantic",
        meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        encoded = nbmf_encode(payload, fidelity=fidelity)  # type: ignore[arg-type]
        if meta:
            encoded.setdefault("meta", {}).update(meta)
        return encoded

    def prepare_update(
        self,
        key: str,
        payload: Any,
        *,
        tenant_id: str,
        fidelity: str = "semantic",
        meta: Optional[Dict[str, Any]] = None,
    ) -> EdgeUpdatePackage:
        meta = meta or {}
        previous = self._load_record(key)
        previous_raw = previous.get("raw") if previous else None
        previous_hash = previous.get("raw_hash") if previous else None

        normalized = self._normalize_payload(payload)
        nbmf_obj = self.encode_payload(key, payload, fidelity=fidelity, meta=meta)

        delta = None
        if previous_raw is not None:
            delta = text_diff(previous_raw, normalized)

        record = {
            "raw": normalized,
            "raw_hash": nbmf_obj.get("sig"),
            "nbmf": nbmf_obj,
            "meta": meta,
            "updated_at": time.time(),
            "fidelity": fidelity,
        }
        self._store_record(key, record)

        return EdgeUpdatePackage(
            tenant_id=tenant_id,
            edge_id=self.edge_id,
            key=key,
            fidelity=fidelity,
            nbmf=nbmf_obj,
            delta=delta,
            base_hash=previous_hash,
            meta=meta,
        )

    def apply_delta(self, base: Any, delta: Optional[str]) -> Any:
        if delta is None:
            return base
        base_str = self._normalize_payload(base)
        patched = apply_text_diff(base_str, delta)
        try:
            return json.loads(patched)
        except json.JSONDecodeError:
            return patched

    def load_cached(self, key: str) -> Optional[Dict[str, Any]]:
        return self._load_record(key)
