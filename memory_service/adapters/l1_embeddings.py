"""
Deterministic in-memory embedding index used for L1 hot cache.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Dict, List, Tuple


class L1Index:
    def __init__(self) -> None:
        self._store: Dict[str, Tuple[List[float], Dict[str, str]]] = {}

    def _embed(self, text: str, dim: int = 128) -> List[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values = [(digest[i % len(digest)] - 127.5) / 127.5 for i in range(dim)]
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    def index(self, key: str, payload: object, meta: Dict[str, str] | None = None) -> None:
        text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False, sort_keys=True)
        self._store[key] = (self._embed(text), meta or {})

    def upsert(self, key: str, text: str, meta: Dict[str, str]) -> None:
        self._store[key] = (self._embed(text), meta)

    def search(self, query: str, top_k: int = 5) -> List[str]:
        if not self._store:
            return []
        query_vec = self._embed(query)

        def cosine(a: List[float], b: List[float]) -> float:
            return sum(x * y for x, y in zip(a, b))

        scored = [
            (key, cosine(query_vec, vec), meta) for key, (vec, meta) in self._store.items()
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        return [key for key, _score, _meta in scored[:top_k]]

    def meta(self, key: str) -> Dict[str, str]:
        entry = self._store.get(key)
        return entry[1] if entry else {}


