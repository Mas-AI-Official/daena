"""
Helpers for lightweight latent quantisation stubs.
"""

from __future__ import annotations

from typing import Iterable, List


def fp16_pack(values: Iterable[float]) -> List[float]:
    # Placeholder: pass-through. Production code can convert to float16/array.
    return list(values)


def int8_pack(values: Iterable[float]) -> bytes:
    data = list(values)
    if not data:
        return b""
    scale = max(1e-6, max(abs(v) for v in data))
    quantised = []
    for v in data:
        scaled = int(round((v / scale) * 127))
        quantised.append(max(-127, min(127, scaled)) & 0xFF)
    return bytes(quantised)

