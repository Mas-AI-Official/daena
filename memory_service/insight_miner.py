from __future__ import annotations

import heapq
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .adapters.l2_nbmf_store import L2Store
from .crypto import read_secure_json
from .emotion5d import clamp01


class InsightMiner:
    def __init__(self, l2_root: str = ".l2_store", top_n: int = 20):
        self.store = L2Store(l2_root)
        self.top_n = top_n

    def _score(self, record: Dict[str, Any]) -> float:
        meta = record.get("meta", {})
        emo = meta.get("emotion5d", {})
        intensity = clamp01(emo.get("intensity", 0.0))
        valence = clamp01(emo.get("valence", 0.5))
        dominance = clamp01(emo.get("dominance", 0.5))
        certainty = clamp01(emo.get("certainty", 0.5))
        return 0.4 * intensity + 0.2 * abs(valence - 0.5) + 0.2 * dominance + 0.2 * certainty

    def mine(self) -> List[Tuple[str, Dict[str, Any]]]:
        bucket: List[Tuple[float, str, Dict[str, Any]]] = []
        store_path = Path(self.store.root, "records")
        if not store_path.exists():
            return []
        for file in store_path.glob("*.json"):
            try:
                record = read_secure_json(file)
            except Exception:
                continue
            score = self._score(record)
            if len(bucket) < self.top_n:
                heapq.heappush(bucket, (score, file.stem, record))
            else:
                heapq.heappushpop(bucket, (score, file.stem, record))
        bucket.sort(reverse=True)
        return [(key, rec) for _score, key, rec in bucket]

    def to_summary(self) -> Dict[str, Any]:
        insights = self.mine()
        items = []
        for key, rec in insights:
            # Handle case where rec might be a string instead of dict
            if isinstance(rec, str):
                rec = {"payload": rec, "cls": None, "meta": {}}
            elif not isinstance(rec, dict):
                rec = {"payload": str(rec), "cls": None, "meta": {}}
            
            # Safely extract values
            payload = rec.get("payload", {})
            if isinstance(payload, str):
                preview = payload[:256]
            else:
                preview = (payload.get("summary") if isinstance(payload, dict) else str(payload))[:256] if payload else ""
            
            items.append({
                "key": key,
                "class": rec.get("cls"),
                "emotion5d": rec.get("meta", {}).get("emotion5d") if isinstance(rec.get("meta"), dict) else None,
                "preview": preview,
            })
        
        return {
            "count": len(insights),
            "items": items,
        }
