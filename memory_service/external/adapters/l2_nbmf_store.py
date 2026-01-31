"""
JSON-backed warm store for NBMF payloads with encode/decode helpers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from .. import nbmf_decoder, nbmf_encoder
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

    # ------------------------------------------------------------------
    # NBMF persistence
    # ------------------------------------------------------------------
    def _resolve_fidelity(self, meta: Optional[Dict[str, Any]]) -> str:
        if not meta:
            return "semantic"
        if meta.get("fidelity"):
            return str(meta["fidelity"])
        compression = meta.get("compression")
        if isinstance(compression, dict):
            mode = compression.get("mode")
            if mode:
                return str(mode)
        return "semantic"

    def put_record(self, key: str, cls: str, payload: Any, meta: Optional[Dict[str, Any]] = None) -> str:
        meta = dict(meta or {})
        fidelity = self._resolve_fidelity(meta)
        meta.setdefault("fidelity", fidelity)

        nbmf_blob = nbmf_encoder.encode(payload, fidelity=fidelity)  # type: ignore[arg-type]
        retain_raw = bool(meta.get("retain_raw"))
        if fidelity == "lossless":
            retain_raw = retain_raw or bool(meta.get("store_raw_json_zstd"))

        record: Dict[str, Any] = {"cls": cls, "meta": meta, "nbmf": nbmf_blob}
        if retain_raw:
            record["payload"] = payload

        path = self._record_path(key, cls)
        write_secure_json(path, record)
        return path.name

    def _load_record(self, key: str, cls: str) -> Optional[Dict[str, Any]]:
        path = self._record_path(key, cls)
        if not path.exists():
            if cls != "*":
                return self._load_record(key, "*")
            path = self._find_any_record(key)
            if path is None:
                return None
        return read_secure_json(path)

    def get_record(self, key: str, cls: str) -> Optional[Any]:
        full = self.get_full_record(key, cls)
        if full is None:
            return None
        payload = full.get("payload")
        if payload is not None:
            return payload
        nbmf_blob = full.get("nbmf")
        if nbmf_blob is None:
            return None
        return nbmf_decoder.decode(nbmf_blob)

    def get_full_record(self, key: str, cls: str) -> Optional[Dict[str, Any]]:
        record = self._load_record(key, cls)
        if record is None:
            return None
        if "payload" not in record or record["payload"] is None:
            nbmf_blob = record.get("nbmf")
            if nbmf_blob is not None:
                record["payload"] = nbmf_decoder.decode(nbmf_blob)
        return record

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
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
        for path in (self.root / "records").glob("*.json"):
            record = read_secure_json(path)
            if record is None:
                continue
            item_id, _sep, _cls = path.stem.partition("__")
            cls = record.get("cls", _cls or "*")
            if "payload" not in record or record["payload"] is None:
                nbmf_blob = record.get("nbmf")
                if nbmf_blob is not None:
                    record["payload"] = nbmf_decoder.decode(nbmf_blob)
            yield item_id, str(cls), record

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
