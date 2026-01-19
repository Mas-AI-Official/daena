"""
Simple tone adapter stub that reshapes output text according to emotion metadata.
"""

from __future__ import annotations

from typing import Dict


def choose_style(emotion: Dict[str, float]) -> str:
    valence = emotion.get("valence", 0.5)
    arousal = emotion.get("arousal", 0.5)
    dominance = emotion.get("dominance", 0.5)
    certainty = emotion.get("certainty", 0.5)

    if valence < 0.4 and arousal > 0.6:
        return "supportive"
    if dominance > 0.7 and certainty > 0.6:
        return "professional"
    if valence > 0.7 and arousal > 0.5:
        return "playful"
    return "warm"


def render(text: str, emotion: Dict[str, float]) -> str:
    style = choose_style(emotion)
    if style == "professional":
        return text
    if style == "supportive":
        return f"I hear you. {text}"
    if style == "playful":
        return f"🙂 {text}"
    return text

