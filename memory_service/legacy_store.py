"""
Lightweight legacy storage shim used during the hybrid migration phase.

In production, callers may supply their own implementation wired to the
pre-existing storage backend. For tests and bootstrap usage we ship an
in-memory dictionary store so the hybrid router can exercise dual-write and
read-through flows without external dependencies.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class LegacyStore:
    """Simple dictionary-backed legacy storage."""

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, Any]] = {}

    def write(self, key: str, payload: Any, cls: Optional[str] = None, meta: Optional[Dict[str, Any]] = None) -> None:
        self._store[key] = {"payload": payload, "cls": cls or "*", "meta": meta or {}}

    put = write  # alias for migration helpers

    def read(self, key: str) -> Optional[Any]:
        record = self._store.get(key)
        if record is None:
            return None
        return record.get("payload")

    def get_record(self, key: str) -> Optional[Dict[str, Any]]:
        return self._store.get(key)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def list_ids(self) -> list[str]:
        return list(self._store.keys())

