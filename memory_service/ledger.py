"""
Append-only JSON lines ledger for memory operations.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


class AppendOnlyLedger:
    def __init__(self, path: str | Path = ".ledger/ledger.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _tx_hash(self, record: Dict[str, Any]) -> str:
        payload = json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def write(self, action: str, ref_id: str, sha256: str, meta: Dict[str, Any]) -> str:
        # Ensure tenant_id is in meta if provided (CRITICAL for multi-tenant isolation)
        if "tenant_id" not in meta and "tenant" in meta:
            meta["tenant_id"] = meta["tenant"]
        
        # Add timestamp for immutability verification
        if "timestamp" not in meta:
            from datetime import datetime, timezone
            meta["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        # Add previous hash for chain integrity (if available)
        if "prev_hash" not in meta:
            try:
                last_record = list(self.iter_records())
                if last_record:
                    meta["prev_hash"] = last_record[-1].get("txid", "")
            except:
                meta["prev_hash"] = ""
        
        record = {
            "action": action,
            "ref_id": ref_id,
            "sha256": sha256,
            "meta": meta,
        }
        record["txid"] = self._tx_hash(record)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            # Fallback: try to log to stderr or memory (best effort)
            import sys
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to create ledger directory {self.path.parent}: {e}")
            # Still return txid for consistency, but operation may not be logged
            return record["txid"]
        
        try:
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except (OSError, PermissionError, IOError) as e:
            # Log error but don't crash - ledger is best-effort audit trail
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to write ledger entry {record['txid']}: {e}")
            # Return txid anyway - caller may have other logging mechanisms
        return record["txid"]

    def log_event(self, action: str, meta: Dict[str, Any]) -> str:
        return self.write(action, ref_id=str(meta.get("ref", action)), sha256="event", meta=meta)

    # ------------------------------------------------------------------
    # Read helpers & integrity utilities
    # ------------------------------------------------------------------
    def iter_records(self) -> Iterable[Dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if "txid" not in record:
                    record["txid"] = self._tx_hash(record)
                yield record

    def read_all(self) -> List[Dict[str, Any]]:
        return list(self.iter_records())

    @staticmethod
    def merkle_root(records: List[Dict[str, Any]]) -> Optional[str]:
        hashes: List[str] = []
        for record in records:
            txid = record.get("txid")
            if not txid:
                txid = hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
                record["txid"] = txid
            hashes.append(txid)
        if not hashes:
            return None
        layer = hashes
        while len(layer) > 1:
            next_layer: List[str] = []
            for i in range(0, len(layer), 2):
                left = layer[i]
                right = layer[i + 1] if i + 1 < len(layer) else layer[i]
                combined = hashlib.sha256((left + right).encode("utf-8")).hexdigest()
                next_layer.append(combined)
            layer = next_layer
        return layer[0]

    def generate_manifest(self, note: Optional[str] = None, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        records = self.read_all()
        manifest: Dict[str, Any] = {
            "ledger_path": str(self.path),
            "entries": len(records),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "merkle_root": self.merkle_root(records),
            "first_txid": records[0].get("txid") if records else None,
            "last_txid": records[-1].get("txid") if records else None,
        }
        if note:
            manifest["note"] = note
        if extra:
            manifest["extra"] = extra
        return manifest


class Ledger(AppendOnlyLedger):
    def __init__(self, path: str | Path = ".ledger/ledger.jsonl"):
        super().__init__(path=path)


_GLOBAL_LEDGER: Optional[Ledger] = None


def _get_global_ledger() -> Ledger:
    global _GLOBAL_LEDGER
    if _GLOBAL_LEDGER is None:
        _GLOBAL_LEDGER = Ledger()
    return _GLOBAL_LEDGER


def log_event(*, action: str, ref: str, store: str, route: str, extra: Optional[Dict[str, Any]] = None) -> str:
    meta = {"ref": ref, "store": store, "route": route}
    if extra:
        meta.update(extra)
    return _get_global_ledger().log_event(action, meta)


def ledger_summary(path: str | Path = ".ledger/ledger.jsonl") -> Dict[str, Any]:
    ledger = Ledger(path)
    records = ledger.read_all()
    summary: Dict[str, Any] = {
        "entries": len(records),
        "merkle_root": ledger.merkle_root(records),
        "first_txid": records[0].get("txid") if records else None,
        "last_txid": records[-1].get("txid") if records else None,
        "by_action": {},
        "by_store": {},
    }
    actions: Dict[str, int] = {}
    stores: Dict[str, int] = {}
    for record in records:
        action = str(record.get("action", "unknown"))
        meta = record.get("meta") or {}
        store = str(meta.get("store", "unknown"))
        actions[action] = actions.get(action, 0) + 1
        stores[store] = stores.get(store, 0) + 1
    summary["by_action"] = actions
    summary["by_store"] = stores
    return summary

