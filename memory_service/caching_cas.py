"""
Simple content-addressable storage helper backed by JSON files.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Optional


class CAS:
    def __init__(self, root: str | Path = ".cas"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / key

    def key(self, payload: Any) -> str:
        data = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def has(self, key: str) -> bool:
        return self._path(key).exists()

    def put(self, key: str, payload: Any) -> str:
        path = self._path(key)
        if not path.exists():
            with path.open("w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False)
        return str(path)

    def get(self, key: str) -> Optional[Any]:
        path = self._path(key)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

