"""
Baseline NBMF encoder stub.

Corsur will extend/replace this with a production-grade neural encoder during
later phases. For now, it offers deterministic behaviour so bootstrap/tests can
exercise imports and simple round-trips.
"""

from __future__ import annotations

import hashlib
import json
import zlib
from typing import Any, Dict, Literal

Fidelity = Literal["lossless", "semantic"]


def _sha256(obj: Any) -> str:
    data = json.dumps(obj, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def encode(payload: Any, fidelity: Fidelity = "semantic") -> Dict[str, Any]:
    meta: Dict[str, Any] = {"fidelity": fidelity, "type": type(payload).__name__}
    if fidelity == "lossless":
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        compressed = zlib.compress(raw, level=9)
        meta.update({"length_bytes": len(compressed)})
        return {"meta": meta, "code": compressed.hex(), "sig": _sha256(payload)}

    if isinstance(payload, str):
        canonical = " ".join(payload.split())
    else:
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    preview = canonical[:2048]
    meta.update({"preview_length": len(preview)})
    return {"meta": meta, "code": preview.encode("utf-8").hex(), "sig": _sha256(canonical)}

