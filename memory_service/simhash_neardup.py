"""
Minimal SimHash-based near-duplicate detection.
"""

from __future__ import annotations

import hashlib
from typing import Iterable


def _tokens(text: str) -> Iterable[str]:
    for token in text.lower().split():
        t = token.strip()
        if t:
            yield t


def simhash(text: str, bits: int = 64) -> int:
    accum = [0] * bits
    for tok in _tokens(text):
        digest = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        for i in range(bits):
            accum[i] += 1 if (digest >> i) & 1 else -1
    value = 0
    for i, weight in enumerate(accum):
        if weight >= 0:
            value |= 1 << i
    return value


def hamming_distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def near_duplicate(a: str, b: str, threshold: int = 10) -> bool:
    return hamming_distance(simhash(a), simhash(b)) <= threshold

