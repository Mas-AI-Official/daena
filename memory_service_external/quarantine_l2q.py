"""
Simple JSON-backed quarantine store for untrusted memory items.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class L2Quarantine:
    def __init__(self, root: str | Path = ".l2q"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, item_id: str) -> Path:
        return self.root / f"{item_id.replace('/', '_')}.json"

    def write(self, item_id: str, nbmf: Dict[str, Any], meta: Dict[str, Any]) -> str:
        record = {"nbmf": nbmf, "meta": meta, "trust": 0.0}
        path = self._path(item_id)
        with path.open("w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False)
        return str(path)

    def read(self, item_id: str) -> Optional[Dict[str, Any]]:
        path = self._path(item_id)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def update_trust(self, item_id: str, score: float) -> None:
        record = self.read(item_id)
        if record is None:
            return
        record["trust"] = max(0.0, min(1.0, score))
        with self._path(item_id).open("w", encoding="utf-8") as fh:
            json.dump(record, fh, ensure_ascii=False)

    def delete(self, item_id: str) -> None:
        path = self._path(item_id)
        if path.exists():
            path.unlink()

    def list_items(self) -> List[str]:
        return [p.stem for p in self.root.glob("*.json")]
