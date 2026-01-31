"""
Simple content-addressable storage (CAS) engine backed by file system.
Part of Daena Memory System.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Optional, Union


class CAS:
    def __init__(self, root: str | Path = ".cas"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / key

    def key(self, payload: Any) -> str:
        """Generate SHA256 key for payload."""
        if isinstance(payload, bytes):
            data = payload
        else:
            data = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def has(self, key: str) -> bool:
        """Check if content exists."""
        return self._path(key).exists()

    def put(self, payload: Any) -> str:
        """Store content and return its key."""
        key = self.key(payload)
        path = self._path(key)
        if not path.exists():
            if isinstance(payload, bytes):
                with path.open("wb") as fh:
                    fh.write(payload)
            else:
                with path.open("w", encoding="utf-8") as fh:
                    json.dump(payload, fh, ensure_ascii=False)
        return key

    def get(self, key: str) -> Optional[Any]:
        """Retrieve content by key."""
        path = self._path(key)
        if not path.exists():
            return None
        
        # Try JSON first
        try:
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except (UnicodeDecodeError, json.JSONDecodeError):
            # Fallback to bytes if not valid JSON
            with path.open("rb") as fh:
                return fh.read()

    def delete(self, key: str) -> bool:
        """Delete content by key."""
        path = self._path(key)
        if path.exists():
            path.unlink()
            return True
        return False
