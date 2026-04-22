"""Emotional Intelligence layer for Daena's chat pipeline.

Detects the emotional state of incoming messages so Daena can match
tone and register instead of replying in a flat, robotic voice. This
was explicitly requested by the founder -- the earlier implementation
was lost in a refactor; this is the canonical restoration point.

**Why it matters:**
- Marketing / Sales / Social outreach are gated by tonal match. A
  prospect who wrote "we're drowning in ransomware alerts" needs an
  empathetic, calm reply, not a cheerful product pitch.
- Even internal Daena chat benefits: a frustrated founder typing
  "this is still broken" deserves a different response cadence than
  the same words said casually.

**Design constraints:**
- Must be fast (<200ms on local models) so it doesn't bloat the hot path.
- Must be optional -- a config flag disables the pass entirely and
  the system falls back to purely soul-driven tone.
- Output is structured (EmotionalSignal) so the system prompt overlay
  can adapt deterministically.

**Output model (no free-form hallucination):**
- valence:       -1.0 (highly negative) to +1.0 (highly positive)
- energy:         0.0 (calm/low-energy) to 1.0 (urgent/high-energy)
- primary_emotion: one of a closed enum (frustrated, curious, etc.)
- formality:      0.0 (casual) to 1.0 (formal / professional)
- urgency:        0.0 (relaxed) to 1.0 (time-pressured)
- confidence:     0.0-1.0 how certain the classifier is
- cues:           list of short phrases from the message that drove the read

The heuristic classifier runs first (zero-cost, always available).
When confidence < threshold, an LLM pass refines the read. That keeps
most turns at near-zero cost while handling nuance when it matters.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class PrimaryEmotion(str, Enum):
    """Closed set -- the LLM cannot return anything else."""

    NEUTRAL = "neutral"
    CURIOUS = "curious"
    ENTHUSIASTIC = "enthusiastic"
    GRATEFUL = "grateful"
    FRUSTRATED = "frustrated"
    ANXIOUS = "anxious"
    ANGRY = "angry"
    DISAPPOINTED = "disappointed"
    CONFUSED = "confused"
    URGENT = "urgent"
    REFLECTIVE = "reflective"
    PLAYFUL = "playful"


@dataclass
class EmotionalSignal:
    """Structured read of the user's emotional state on one turn."""

    valence: float = 0.0          # -1.0 .. 1.0
    energy: float = 0.5           # 0.0 .. 1.0
    primary_emotion: PrimaryEmotion = PrimaryEmotion.NEUTRAL
    formality: float = 0.5        # 0.0 .. 1.0
    urgency: float = 0.3          # 0.0 .. 1.0
    confidence: float = 0.0       # 0.0 .. 1.0 -- how sure we are
    cues: list[str] = field(default_factory=list)
    source: str = "heuristic"     # "heuristic" | "llm" | "disabled"

    def to_dict(self) -> dict[str, Any]:
        return {
            "valence": round(self.valence, 2),
            "energy": round(self.energy, 2),
            "primary_emotion": self.primary_emotion.value,
            "formality": round(self.formality, 2),
            "urgency": round(self.urgency, 2),
            "confidence": round(self.confidence, 2),
            "cues": self.cues[:6],
            "source": self.source,
        }


# ── Heuristic lexicon ──────────────────────────────────────────────
# Hand-tuned keyword lists. Not "real" sentiment analysis -- just fast
# triage so the hot path avoids LLM latency when the signal is obvious.

_NEGATIVE_CUES = {
    "angry": {"furious", "pissed", "fed up", "outraged", "unacceptable"},
    "frustrated": {"stuck", "not working", "broken", "still", "again", "keeps failing", "annoying"},
    "anxious": {"worried", "nervous", "scared", "concerned", "stressed", "what if"},
    "disappointed": {"let down", "thought you", "expected", "promised", "should have"},
    "confused": {"confused", "don't understand", "unclear", "what does", "i'm lost"},
}

_POSITIVE_CUES = {
    "enthusiastic": {"love it", "amazing", "excellent", "perfect", "awesome", "wonderful"},
    "grateful": {"thanks", "thank you", "appreciate", "grateful", "really helpful"},
    "playful": {"lol", "haha", "😂", "🤣", "funny", "lmao"},
    "curious": {"how does", "why does", "wonder", "curious", "interesting"},
    "reflective": {"thinking about", "wonder if", "what if we", "long-term"},
}

_URGENCY_CUES = {
    "asap", "urgent", "right now", "immediately", "today", "blocker",
    "emergency", "production down", "customer waiting", "before the meeting",
    "by end of day", "eod", "in the next",
}

_FORMALITY_HIGH = {
    "please", "would you", "could you", "kindly", "would appreciate", "sincerely",
    "best regards", "respectfully", "per our discussion",
}

_FORMALITY_LOW = {
    "yo", "hey", "sup", "gonna", "wanna", "kinda", "lol", "wtf", "bruh", "dude",
}


def _scan(text: str, vocab: dict[str, set[str]]) -> tuple[str | None, list[str]]:
    """Return (matched_bucket, matched_cue_list) for the first bucket with a hit."""
    lower = text.lower()
    for bucket, cues in vocab.items():
        hits = [c for c in cues if c in lower]
        if hits:
            return bucket, hits
    return None, []


def _heuristic_read(text: str) -> EmotionalSignal:
    """Fast lexicon scan. Always returns; confidence is the quality signal."""
    sig = EmotionalSignal(source="heuristic")
    cues: list[str] = []

    # Negative vs positive bucket
    neg_bucket, neg_cues = _scan(text, _NEGATIVE_CUES)
    pos_bucket, pos_cues = _scan(text, _POSITIVE_CUES)

    if neg_bucket and not pos_bucket:
        sig.primary_emotion = PrimaryEmotion(neg_bucket)
        sig.valence = -0.6
        sig.confidence = 0.55
        cues.extend(neg_cues)
    elif pos_bucket and not neg_bucket:
        sig.primary_emotion = PrimaryEmotion(pos_bucket)
        sig.valence = 0.6
        sig.confidence = 0.55
        cues.extend(pos_cues)
    elif neg_bucket and pos_bucket:
        # Mixed signal -- give it to the LLM pass
        sig.primary_emotion = PrimaryEmotion.NEUTRAL
        sig.confidence = 0.25
        cues.extend(neg_cues + pos_cues)
    else:
        sig.confidence = 0.40

    # Urgency
    lower = text.lower()
    urgency_hits = [c for c in _URGENCY_CUES if c in lower]
    if urgency_hits:
        sig.urgency = 0.85
        sig.energy = max(sig.energy, 0.8)
        cues.extend(urgency_hits)
        if sig.primary_emotion == PrimaryEmotion.NEUTRAL:
            sig.primary_emotion = PrimaryEmotion.URGENT

    # Formality
    if any(p in lower for p in _FORMALITY_HIGH):
        sig.formality = 0.8
    elif any(p in lower for p in _FORMALITY_LOW):
        sig.formality = 0.2

    # Punctuation-based energy hint
    excls = text.count("!")
    if excls >= 3:
        sig.energy = max(sig.energy, 0.8)
        sig.confidence = max(sig.confidence, 0.55)
    if re.search(r"[A-Z]{4,}", text):  # ALL CAPS word
        sig.energy = max(sig.energy, 0.85)
        sig.confidence = max(sig.confidence, 0.55)

    # Longer reflective messages bias toward lower energy + higher formality
    if len(text) > 400 and excls == 0:
        sig.energy = min(sig.energy, 0.4)
        sig.formality = max(sig.formality, 0.55)
        if sig.primary_emotion == PrimaryEmotion.NEUTRAL:
            sig.primary_emotion = PrimaryEmotion.REFLECTIVE

    sig.cues = cues[:6]
    return sig


# ── LLM refinement pass ────────────────────────────────────────────


_LLM_PROMPT = """\
You classify the emotional tone of a short user message so an AI
assistant can match the user's register in its reply.

MESSAGE:
<<<
{message}
>>>

Reply with ONLY a JSON object, no prose:
{{
  "valence": -1.0 to 1.0 (negative to positive),
  "energy": 0.0 to 1.0 (calm to intense),
  "primary_emotion": one of {allowed},
  "formality": 0.0 to 1.0 (casual to formal),
  "urgency": 0.0 to 1.0 (relaxed to time-pressured),
  "confidence": 0.0 to 1.0 (your certainty),
  "cues": ["up to 4 short phrases from the message that drove your read"]
}}

Rules:
- If the message is short and neutral, confidence should be around 0.4-0.6.
- Do not invent cues. Only quote phrases that actually appear.
- primary_emotion MUST be one of the allowed values. No others.
"""


async def _llm_refine(message: str, timeout_s: float = 3.0) -> EmotionalSignal | None:
    """Optional LLM pass when heuristic confidence is low."""
    settings = get_settings()
    allowed = [e.value for e in PrimaryEmotion]
    prompt = _LLM_PROMPT.format(message=message[:2000], allowed=allowed)
    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            # Match skill_refinery pattern: POST to Ollama chat if available,
            # otherwise fall through. This avoids introducing a new provider
            # path that could drift; tonal analysis is cheap text in / text out.
            resp = await client.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": settings.ollama_default_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "stream": False,
                    "options": {"temperature": 0.15, "num_predict": 256},
                },
            )
            resp.raise_for_status()
            raw = resp.json().get("message", {}).get("content", "").strip()
    except Exception as exc:
        logger.debug("emotional.llm_refine_failed", error=str(exc))
        return None

    # Strip markdown fences and parse
    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw = "\n".join(lines)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            data = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None

    try:
        emo = str(data.get("primary_emotion", "neutral")).lower()
        primary = PrimaryEmotion(emo) if emo in {e.value for e in PrimaryEmotion} else PrimaryEmotion.NEUTRAL
    except ValueError:
        primary = PrimaryEmotion.NEUTRAL

    return EmotionalSignal(
        valence=_clip(data.get("valence", 0.0), -1.0, 1.0),
        energy=_clip(data.get("energy", 0.5), 0.0, 1.0),
        primary_emotion=primary,
        formality=_clip(data.get("formality", 0.5), 0.0, 1.0),
        urgency=_clip(data.get("urgency", 0.3), 0.0, 1.0),
        confidence=_clip(data.get("confidence", 0.6), 0.0, 1.0),
        cues=[str(c)[:80] for c in (data.get("cues") or [])][:6],
        source="llm",
    )


def _clip(v: Any, lo: float, hi: float) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        f = (lo + hi) / 2
    return max(lo, min(hi, f))


# ── Public API ──────────────────────────────────────────────────────


async def analyze_message(
    message: str,
    *,
    history: list[dict[str, str]] | None = None,
    llm_threshold: float = 0.5,
    enable_llm: bool | None = None,
    llm_timeout_s: float = 3.0,
) -> EmotionalSignal:
    """Classify the emotional state of a user message.

    Args:
        message: The raw user text to analyze.
        history: Optional last-few-turns context. Not used in the
            heuristic pass; reserved for a future richer analyzer.
        llm_threshold: If the heuristic's confidence is below this,
            spend a cheap LLM call to refine the read.
        enable_llm: Force-enable or force-disable the LLM pass. None
            (default) respects the settings flag ``EMOTIONAL_AWARENESS_LLM``.
        llm_timeout_s: Hard cap on the LLM refinement call.

    Returns:
        An EmotionalSignal. Always returns -- never raises.
    """
    if not message or not message.strip():
        return EmotionalSignal(source="disabled", confidence=0.0)

    signal = _heuristic_read(message)

    # Heuristic was confident enough, or LLM is disabled: ship it.
    settings = get_settings()
    llm_allowed = getattr(settings, "emotional_awareness_llm", True) if enable_llm is None else enable_llm

    if signal.confidence >= llm_threshold or not llm_allowed:
        logger.debug(
            "emotional.heuristic_final",
            emotion=signal.primary_emotion.value,
            confidence=signal.confidence,
        )
        return signal

    # Try LLM refinement; fall back to heuristic result on any failure.
    try:
        refined = await asyncio.wait_for(_llm_refine(message), timeout=llm_timeout_s + 0.5)
    except TimeoutError:
        logger.debug("emotional.llm_timeout")
        return signal
    except Exception as exc:
        logger.debug("emotional.llm_error", error=str(exc))
        return signal

    if refined is None:
        return signal
    return refined


def build_tone_overlay(signal: EmotionalSignal) -> str:
    """Produce the system-prompt overlay Daena injects to adapt her tone.

    The overlay is intentionally short -- LLM attention budget is
    precious and the soul already carries the baseline personality.
    This just nudges register for the current turn.

    Keep the output self-contained so it can be appended to any prompt
    (core soul, department overlay, orchestrator system prompt).
    """
    emo = signal.primary_emotion
    # Map emotion -> short guidance line. Pragmatic, not poetic --
    # guidance that would read as acceptable "if a human coworker did this."
    guidance = {
        PrimaryEmotion.FRUSTRATED: (
            "User is frustrated. Acknowledge the friction in one short sentence before "
            "solving. No cheery language. Be direct and specific about the fix."
        ),
        PrimaryEmotion.ANGRY: (
            "User is angry. Do not be defensive. Name the problem they raised in your "
            "first sentence, then propose the most concrete fix you can deliver right now."
        ),
        PrimaryEmotion.ANXIOUS: (
            "User is anxious. Steady, confident tone. Break the answer into small ordered "
            "steps so they have footing. Avoid hedging language."
        ),
        PrimaryEmotion.DISAPPOINTED: (
            "User expected more. Acknowledge the gap between expectation and reality, "
            "then raise the bar. Do not over-apologize."
        ),
        PrimaryEmotion.CONFUSED: (
            "User is confused. Slow down. One idea per sentence. Define any jargon "
            "the moment you use it."
        ),
        PrimaryEmotion.URGENT: (
            "User is time-pressured. Lead with the action or answer. Details second. "
            "Under 80 words unless they ask for more."
        ),
        PrimaryEmotion.ENTHUSIASTIC: (
            "User is enthusiastic. Match the energy but stay grounded -- do not inflate. "
            "Channel momentum into a concrete next step."
        ),
        PrimaryEmotion.GRATEFUL: (
            "User is grateful. One warm beat of acknowledgement, then move on. "
            "Do not milk it."
        ),
        PrimaryEmotion.CURIOUS: (
            "User is curious. Reward the curiosity with a crisp answer and one deeper "
            "pointer they can chase."
        ),
        PrimaryEmotion.PLAYFUL: (
            "User is playful. Match the casual register. Short replies are welcome. "
            "Do not force humor if you do not have it."
        ),
        PrimaryEmotion.REFLECTIVE: (
            "User is reflective. Meet the depth. Answer in structured paragraphs, "
            "not bullets. Name trade-offs explicitly."
        ),
        PrimaryEmotion.NEUTRAL: (
            "User's tone is neutral. Default Daena voice applies -- direct, specific, warm."
        ),
    }.get(emo, "")

    formality_line = ""
    if signal.formality >= 0.7:
        formality_line = "Register: formal. Full sentences, no slang, no emoji."
    elif signal.formality <= 0.3:
        formality_line = "Register: casual. Contractions are fine. Light informality is welcome."

    urgency_line = ""
    if signal.urgency >= 0.7:
        urgency_line = "Time pressure detected: lead with the answer, push context to a P.S. line."

    lines = ["## EMOTIONAL AWARENESS (this turn only)"]
    lines.append(
        f"Detected: {emo.value} (valence {signal.valence:+.1f}, energy {signal.energy:.1f}, "
        f"formality {signal.formality:.1f}, urgency {signal.urgency:.1f}, "
        f"confidence {signal.confidence:.2f})."
    )
    if guidance:
        lines.append(guidance)
    if formality_line:
        lines.append(formality_line)
    if urgency_line:
        lines.append(urgency_line)
    lines.append(
        "Do NOT mention the emotional analysis to the user. Just adapt your tone."
    )
    return "\n".join(lines)
