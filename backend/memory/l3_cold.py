"""
L3 Cold Storage - Archival Memory.
Part of Daena Memory System.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

from .config import settings
from .cas_engine import CAS

class L3Store:
    def __init__(self):
        self.root = settings.L3_PATH
        self.cas = CAS(settings.CAS_ROOT) if settings.CAS_ENABLED else None
        
    def _path(self, key: str, cls: str) -> Path:
        """Get path for metadata file."""
        safe_key = "".join(c for c in key if c.isalnum() or c in "._-")
        safe_cls = "".join(c for c in cls if c.isalnum() or c in "._-")
        
        cls_dir = self.root / safe_cls
        cls_dir.mkdir(parents=True, exist_ok=True)
        return cls_dir / f"{safe_key}.json"

    def put_record(self, key: str, cls: str, payload: Any, meta: Dict[str, Any]) -> str:
        """Store a record in L3 memory (Cold)."""
        meta = meta or {}
        meta["store"] = "l3"
        meta["archived_at"] = datetime.utcnow().isoformat()
        
        # In real L3, we would compress here.
        # For now, we use CAS for deduplication.
        
        if self.cas:
            content_key = self.cas.put(payload)
            meta["cas_key"] = content_key
            record = {
                "key": key,
                "cls": cls,
                "meta": meta,
                "cas_pointer": content_key
            }
        else:
            record = {
                "key": key,
                "cls": cls,
                "meta": meta,
                "payload": payload
            }
            
        path = self._path(key, cls)
        with path.open("w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False)
            
        return f"tx_l3_{key}_{int(datetime.utcnow().timestamp())}"

    def get_full_record(self, key: str, cls: str) -> Optional[Dict[str, Any]]:
        """Retrieve full record including payload."""
        path = self._path(key, cls)
        if not path.exists():
            return None
            
        try:
            with path.open("r", encoding="utf-8") as f:
                record = json.load(f)
                
            if "cas_pointer" in record and self.cas:
                payload = self.cas.get(record["cas_pointer"])
                if payload is not None:
                    record["payload"] = payload
                    
            return record
        except Exception:
            return None
