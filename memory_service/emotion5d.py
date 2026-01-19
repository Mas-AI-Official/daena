"""
Utility helpers for 5D emotion metadata representation.
"""

from __future__ import annotations

from typing import Dict, Iterable, List


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def clamp01(value: float) -> float:
    return _clamp01(value)


def pack(
    valence: float,
    arousal: float,
    dominance: float,
    social: float,
    certainty: float,
    intensity: float,
    tags: Iterable[str] | None = None,
) -> Dict[str, float | List[str]]:
    return {
        "valence": _clamp01(valence),
        "arousal": _clamp01(arousal),
        "dominance": _clamp01(dominance),
        "social": _clamp01(social),
        "certainty": _clamp01(certainty),
        "intensity": _clamp01(intensity),
        "tags": list(tags or []),
    }

