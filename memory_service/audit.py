from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Dict

from .ledger import Ledger


def ledger_audit(path: str | Path = ".ledger/ledger.jsonl", recent: int = 10) -> Dict[str, Any]:
    ledger = Ledger(path)
    records = ledger.read_all()
    by_action: Counter[str] = Counter()
    by_store: Counter[str] = Counter()
    by_route: Counter[str] = Counter()
    for record in records:
        action = str(record.get("action", "unknown"))
        meta = record.get("meta") or {}
        store = str(meta.get("store", "unknown"))
        route = str(meta.get("route", "unknown"))
        by_action[action] += 1
        by_store[store] += 1
        by_route[route] += 1
    tail = records[-recent:] if recent and recent > 0 else records
    return {
        "entries": len(records),
        "actions": dict(by_action),
        "stores": dict(by_store),
        "routes": dict(by_route),
        "recent": tail,
        "merkle_root": ledger.merkle_root(records),
        "first_txid": records[0].get("txid") if records else None,
        "last_txid": records[-1].get("txid") if records else None,
    }
