"""
Baseline NBMF decoder stub matching the encoder in this directory.
"""

from __future__ import annotations

import json
import zlib
from typing import Any, Dict


def decode(blob: Dict[str, Any]) -> Any:
    meta = blob.get("meta", {})
    code_hex = blob.get("code", "")
    fidelity = meta.get("fidelity")
    if fidelity == "lossless":
        raw = zlib.decompress(bytes.fromhex(code_hex))
        return json.loads(raw.decode("utf-8"))
    # Semantic mode returns preview text; production version will expand via decoder.
    return bytes.fromhex(code_hex).decode("utf-8")

