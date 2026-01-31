"""
L1 Hot Storage - Vector Memory.
Part of Daena Memory System.

Current implementation: In-memory/JSON mock.
Future Roadmap: ChromaDB or Milvus integration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import settings

class L1Index:
    def __init__(self):
        self.root = settings.L1_PATH
        self.index_file = self.root / "l1_index.json"
        
        # Simple in-memory cache
        self._cache = {}
        self._dirty = False
        
        self._load()

    def _load(self):
        if self.index_file.exists():
            try:
                with self.index_file.open("r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except Exception:
                self._cache = {}

    def _save(self):
        if self._dirty:
            with self.index_file.open("w", encoding="utf-8") as f:
                json.dump(self._cache, f, ensure_ascii=False)
            self._dirty = False

    def index(self, key: str, payload: Any, meta: Dict[str, Any]) -> None:
        """Add item to L1 index."""
        self._cache[key] = {
            "payload": payload,  # In real L1, payload might not be stored here
            "meta": meta
        }
        self._dirty = True
        self._save()

    def get(self, key: str) -> Optional[Any]:
        """Get payload by key."""
        item = self._cache.get(key)
        return item["payload"] if item else None

    def meta(self, key: str) -> Dict[str, Any]:
        """Get metadata by key."""
        item = self._cache.get(key)
        return item["meta"] if item else {}
    
    def search(self, query: str, top_k: int = 5) -> List[str]:
        """
        Mock search.
        In real implementation, this uses vector similarity.
        """
        # Simple substring match for now
        results = []
        q = query.lower()
        for key, item in self._cache.items():
            # Search in key or text payload
            payload_str = str(item.get("payload", "")).lower()
            if q in key.lower() or q in payload_str:
                results.append(key)
                if len(results) >= top_k:
                    break
        return results
