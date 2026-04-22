"""Tests for the emotional awareness layer.

Covers:
- Heuristic read on obvious positive / negative / urgent / mixed inputs.
- Confidence gating (high-confidence heuristic skips LLM; low-confidence
  heuristic invokes LLM and takes its result).
- Tone-overlay string shape (must name the emotion, include the
  do-not-announce clause, and stay brief).
- Graceful degradation when LLM fails or returns garbage.
- Always returns an EmotionalSignal -- never raises.
"""

from __future__ import annotations

import json

import pytest

from app.services.emotional_intelligence import (
    EmotionalSignal,
    PrimaryEmotion,
    _heuristic_read,
    analyze_message,
    build_tone_overlay,
)


def test_heuristic_neutral_short_message_low_confidence() -> None:
    sig = _heuristic_read("ok")
    assert sig.primary_emotion == PrimaryEmotion.NEUTRAL
    assert sig.confidence < 0.6


def test_heuristic_detects_frustration() -> None:
    sig = _heuristic_read("this is still broken and keeps failing again")
    assert sig.primary_emotion == PrimaryEmotion.FRUSTRATED
    assert sig.valence < 0
    assert "still" in sig.cues or "again" in sig.cues or "keeps failing" in sig.cues


def test_heuristic_detects_enthusiasm_and_positive_valence() -> None:
    sig = _heuristic_read("this is absolutely amazing, I love it!")
    assert sig.primary_emotion == PrimaryEmotion.ENTHUSIASTIC
    assert sig.valence > 0


def test_heuristic_detects_urgency() -> None:
    sig = _heuristic_read("we need this right now, production is down")
    assert sig.urgency >= 0.8
    assert sig.energy >= 0.7
    # Urgency promotes to URGENT when the message was otherwise neutral
    assert sig.primary_emotion in {PrimaryEmotion.URGENT, PrimaryEmotion.FRUSTRATED}


def test_heuristic_all_caps_bumps_energy() -> None:
    sig = _heuristic_read("WHY ISNT THIS WORKING")
    assert sig.energy >= 0.85


def test_heuristic_formality_high_and_low() -> None:
    formal = _heuristic_read(
        "Would you kindly review the proposal and respond at your convenience? Best regards.",
    )
    assert formal.formality >= 0.7
    casual = _heuristic_read("yo dude gonna just ship it lol")
    assert casual.formality <= 0.3


def test_heuristic_reflective_long_message() -> None:
    # Must be >400 chars AND contain no cue words from POSITIVE_CUES or
    # NEGATIVE_CUES so the "long calm message" branch triggers cleanly.
    # The heuristic promotes NEUTRAL -> REFLECTIVE only when neither
    # bucket fires.
    long_msg = (
        "I have been turning over the positioning problem in my head. "
        "We say governance is the moat, and maybe that is the hook for "
        "buyers who already know the pain of unattended automation. But "
        "for founders who have not yet been burned, the idea of ten "
        "specialized departmental minds collaborating may land with more "
        "weight than the abstract language of governance. "
        "The question is which frame opens a conversation faster in the "
        "mid-market segment we care about."
    )
    assert len(long_msg) > 400
    sig = _heuristic_read(long_msg)
    assert sig.primary_emotion == PrimaryEmotion.REFLECTIVE
    assert sig.energy <= 0.4
    assert sig.formality >= 0.5


def test_heuristic_mixed_signal_yields_low_confidence() -> None:
    sig = _heuristic_read("thanks but this is still broken")
    # Both positive (thanks) and negative (still broken) cues present
    assert sig.confidence < 0.4
    assert sig.primary_emotion == PrimaryEmotion.NEUTRAL


@pytest.mark.asyncio
async def test_analyze_empty_message_returns_disabled_signal() -> None:
    sig = await analyze_message("")
    assert sig.source == "disabled"
    assert sig.confidence == 0.0


@pytest.mark.asyncio
async def test_analyze_high_confidence_skips_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """High-confidence heuristic must not invoke the LLM path."""
    from app.services import emotional_intelligence as ei

    async def _explode(*_a, **_kw):
        pytest.fail("LLM refine should not be called when heuristic is confident")

    monkeypatch.setattr(ei, "_llm_refine", _explode)
    sig = await analyze_message("this is broken again keeps failing")
    assert sig.source == "heuristic"
    assert sig.confidence >= 0.5


@pytest.mark.asyncio
async def test_analyze_low_confidence_uses_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    """Low-confidence heuristic defers to the LLM refiner."""
    from app.services import emotional_intelligence as ei

    refined = EmotionalSignal(
        valence=-0.2,
        energy=0.6,
        primary_emotion=PrimaryEmotion.DISAPPOINTED,
        formality=0.5,
        urgency=0.4,
        confidence=0.8,
        cues=["thanks", "still broken"],
        source="llm",
    )
    async def fake_refine(_msg: str, timeout_s: float = 3.0) -> EmotionalSignal:
        return refined
    monkeypatch.setattr(ei, "_llm_refine", fake_refine)
    sig = await analyze_message("thanks but it is still kinda broken")
    assert sig.source == "llm"
    assert sig.primary_emotion == PrimaryEmotion.DISAPPOINTED


@pytest.mark.asyncio
async def test_analyze_llm_failure_keeps_heuristic(monkeypatch: pytest.MonkeyPatch) -> None:
    """If the LLM raises, the heuristic result is returned (no crash)."""
    from app.services import emotional_intelligence as ei

    async def bomb(_msg: str, timeout_s: float = 3.0) -> EmotionalSignal | None:
        raise RuntimeError("simulated LLM outage")
    monkeypatch.setattr(ei, "_llm_refine", bomb)
    sig = await analyze_message("hmm not sure about this")
    # Heuristic produced it; never raised
    assert sig.source == "heuristic"


def test_build_tone_overlay_contains_guidance_and_do_not_announce() -> None:
    sig = EmotionalSignal(
        valence=-0.6,
        energy=0.7,
        primary_emotion=PrimaryEmotion.FRUSTRATED,
        formality=0.4,
        urgency=0.8,
        confidence=0.7,
    )
    overlay = build_tone_overlay(sig)
    assert "EMOTIONAL AWARENESS" in overlay
    assert "frustrated" in overlay.lower()
    # Hard rule: never let the LLM announce that it's doing tonal analysis
    assert "Do NOT mention" in overlay
    # Urgency high must emit the urgency-specific line
    assert "Time pressure" in overlay or "lead with the answer" in overlay.lower()


def test_build_tone_overlay_respects_formality_extremes() -> None:
    formal = build_tone_overlay(EmotionalSignal(formality=0.85, primary_emotion=PrimaryEmotion.REFLECTIVE))
    casual = build_tone_overlay(EmotionalSignal(formality=0.15, primary_emotion=PrimaryEmotion.PLAYFUL))
    assert "formal" in formal.lower()
    assert "casual" in casual.lower()


def test_signal_to_dict_is_serializable() -> None:
    sig = _heuristic_read("this is broken again")
    d = sig.to_dict()
    # Round-trip through JSON must work so we can log + send over SSE
    assert json.loads(json.dumps(d))["primary_emotion"] in {e.value for e in PrimaryEmotion}
