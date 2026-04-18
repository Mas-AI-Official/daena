"""ConversationSession: stitches STT + LLM + TTS with governance hooks.

Phase I of Roadmap V2. The brain that turns a live voice channel into
a governed Daena conversation turn. Every utterance gets a risk tier;
tier 3+ utterances pause the session until a human approves, matching
the existing tool-dispatch approval flow.

Usage (simplified)
------------------

    session = ConversationSession(
        stt=stt_pipeline, tts=tts_pipeline,
        chat_turn=lambda text: run_orchestrator(text),
        governance_classifier=classify_voice_risk,
    )

    # Inbound: audio arrives from WebRTC
    result = await session.handle_turn(audio_in_bytes)
    if result.status == "awaiting_approval":
        # frontend shows Approve/Reject card keyed to result.approval_id
        ...
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable

from app.services.voice.stt_pipeline import STTError, STTPipeline, Transcript
from app.services.voice.tts_pipeline import TTSError, TTSPipeline, Utterance


class VoiceRiskTier(str, Enum):
    """Matches RiskTier used by the rest of Daena's governance."""

    NONE = "NONE"       # smalltalk
    LOW = "LOW"         # discovery
    MEDIUM = "MEDIUM"   # scheduling
    HIGH = "HIGH"       # pricing commitments
    CRITICAL = "CRITICAL"  # PII / data export / classified


_TIER_TO_GOV = {
    VoiceRiskTier.NONE: 0,
    VoiceRiskTier.LOW: 1,
    VoiceRiskTier.MEDIUM: 2,
    VoiceRiskTier.HIGH: 3,
    VoiceRiskTier.CRITICAL: 4,
}


@dataclass
class TurnResult:
    """Outcome of a single conversation turn."""

    status: str  # "spoken" | "awaiting_approval" | "blocked" | "error"
    transcript: str = ""
    reply_text: str = ""
    audio: bytes = b""
    audio_format: str = ""
    tier: VoiceRiskTier = VoiceRiskTier.NONE
    approval_id: str | None = None
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# Callbacks the session expects the caller to wire in.
ChatTurnFn = Callable[[str], Awaitable[str]]
TierClassifierFn = Callable[[str], Awaitable[VoiceRiskTier]]
ApprovalCreatorFn = Callable[[str, VoiceRiskTier], Awaitable[str]]  # returns approval_id


async def default_tier_classifier(text: str) -> VoiceRiskTier:
    """Minimal keyword-based tier classifier for Phase I.

    Good enough to prove the governance gate on a demo call; replace
    with a proper classifier once the voice corpus grows.
    """
    t = text.lower()
    if any(k in t for k in ("export", "download", "credentials", "password", "social security")):
        return VoiceRiskTier.CRITICAL
    if any(k in t for k in ("price", "cost", "contract", "sign", "commit")):
        return VoiceRiskTier.HIGH
    if any(k in t for k in ("schedule", "book", "calendar", "meeting", "follow up")):
        return VoiceRiskTier.MEDIUM
    if any(k in t for k in ("how", "what", "why", "tell me")):
        return VoiceRiskTier.LOW
    return VoiceRiskTier.NONE


async def default_approval_creator(text: str, tier: VoiceRiskTier) -> str:
    """Fallback approval creator for Phase I.

    Real path: calls ApprovalService.request_approval to land a row
    the Sidebar badge picks up. Phase I scaffold returns a stub id so
    unit tests can verify the gate logic without a DB.
    """
    import uuid
    return f"voice-approval-{uuid.uuid4().hex[:12]}"


class ConversationSession:
    """A single live voice conversation."""

    def __init__(
        self,
        *,
        stt: STTPipeline,
        tts: TTSPipeline,
        chat_turn: ChatTurnFn,
        governance_classifier: TierClassifierFn | None = None,
        approval_creator: ApprovalCreatorFn | None = None,
        tier_threshold_for_approval: VoiceRiskTier = VoiceRiskTier.HIGH,
        stt_provider: str | None = None,
        tts_provider: str | None = None,
    ) -> None:
        self._stt = stt
        self._tts = tts
        self._chat_turn = chat_turn
        self._classify = governance_classifier or default_tier_classifier
        self._create_approval = approval_creator or default_approval_creator
        self._stt_provider = stt_provider
        self._tts_provider = tts_provider
        self._threshold = tier_threshold_for_approval
        self._transcript_log: list[dict[str, Any]] = []

    async def handle_turn(
        self,
        audio_in: bytes | str,
        *,
        language: str = "en",
        voice: str = "default",
    ) -> TurnResult:
        """Process one inbound utterance end-to-end."""
        # Stage 1: STT
        stt_result = await self._stt.transcribe(
            audio_in, provider=self._stt_provider, language=language,
        )
        if isinstance(stt_result, STTError):
            return TurnResult(status="error", reason=f"STT: {stt_result.reason}")
        transcript: Transcript = stt_result
        if not transcript.text:
            return TurnResult(status="error", reason="Empty transcript")

        self._transcript_log.append({"role": "user", "text": transcript.text})

        # Stage 2: LLM turn (delegate to the existing chat pipeline so
        # every governance stage still applies to the reply body).
        try:
            reply_text = await self._chat_turn(transcript.text)
        except Exception as exc:
            return TurnResult(
                status="error",
                transcript=transcript.text,
                reason=f"Chat turn failed: {exc}",
            )
        if not reply_text.strip():
            return TurnResult(
                status="error",
                transcript=transcript.text,
                reason="Chat turn produced empty reply",
            )

        # Stage 3: Classify the REPLY (not the user utterance) since the
        # reply is what Daena is about to speak into the wild.
        tier = await self._classify(reply_text)

        # Stage 4: Governance gate.
        if _TIER_TO_GOV[tier] >= _TIER_TO_GOV[self._threshold]:
            approval_id = await self._create_approval(reply_text, tier)
            self._transcript_log.append(
                {"role": "assistant", "text": reply_text, "status": "awaiting_approval", "tier": tier.value}
            )
            return TurnResult(
                status="awaiting_approval",
                transcript=transcript.text,
                reply_text=reply_text,
                tier=tier,
                approval_id=approval_id,
                reason=f"Tier {tier.value} requires approval before speaking.",
            )

        # Stage 5: TTS
        tts_result = await self._tts.synthesize(
            reply_text, provider=self._tts_provider, voice=voice, language=language,
        )
        if isinstance(tts_result, TTSError):
            return TurnResult(
                status="error",
                transcript=transcript.text,
                reply_text=reply_text,
                reason=f"TTS: {tts_result.reason}",
            )
        utterance: Utterance = tts_result

        self._transcript_log.append(
            {"role": "assistant", "text": reply_text, "status": "spoken", "tier": tier.value}
        )

        return TurnResult(
            status="spoken",
            transcript=transcript.text,
            reply_text=reply_text,
            audio=utterance.audio,
            audio_format=utterance.format,
            tier=tier,
            metadata={"tts_provider": utterance.provider, "stt_provider": transcript.provider},
        )

    def transcript_log(self) -> list[dict[str, Any]]:
        """Full chronological log of the conversation so far.

        Callers persist this alongside the ChatSession for audit.
        """
        return list(self._transcript_log)
