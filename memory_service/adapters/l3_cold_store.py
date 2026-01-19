"""
Compressed cold-storage helper for archival artifacts.
"""

from __future__ import annotations

import base64
import json
import zlib
from pathlib import Path
from typing import Any, Dict, Optional

from ..crypto import read_secure_json, write_secure_json


class L3Store:
    def __init__(self, root: str | Path = ".l3_store"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "records").mkdir(exist_ok=True)

    def _record_path(self, key: str, cls: str) -> Path:
        safe_key = key.replace("/", "_")
        safe_cls = cls.replace("/", "_")
        return self.root / "records" / f"{safe_key}__{safe_cls}.json"

    def put_record(self, key: str, cls: str, payload: Any, meta: Optional[Dict[str, Any]] = None) -> str:
        data = {"payload": payload, "cls": cls, "meta": meta or {}}
        path = self._record_path(key, cls)
        write_secure_json(path, data)
        return path.name

    def get_record(self, key: str, cls: str) -> Optional[Any]:
        full = self.get_full_record(key, cls)
        if full is None:
            return None
        return full.get("payload")

    def get_full_record(self, key: str, cls: str) -> Optional[Dict[str, Any]]:
        path = self._record_path(key, cls)
        if not path.exists():
            return None
        return read_secure_json(path)

    def put_json_artifact(self, artifact: Any) -> str:
        raw = json.dumps(artifact, ensure_ascii=False).encode("utf-8")
        encoded = base64.b64encode(zlib.compress(raw, level=9)).decode("ascii")
        key = f"a_{abs(hash(encoded))}"
        write_secure_json(self.root / f"{key}.json", {"blob": encoded})
        return key

    def get_json_artifact(self, key: str) -> Optional[Any]:
        path = self.root / f"{key}.json"
        if not path.exists():
            return None
        payload = read_secure_json(path)
        blob = payload.get("blob") if isinstance(payload, dict) else None
        if not blob:
            return None
        compressed = base64.b64decode(blob.encode("ascii"))
        raw = zlib.decompress(compressed).decode("utf-8")
        return json.loads(raw)


class L3ColdStore(L3Store):
    """Alias used by bridge/client helpers."""

    pass

