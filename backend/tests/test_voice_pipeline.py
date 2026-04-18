"""Phase I voice pipeline tests.

Pins the provider-plugin architecture and the governance gate logic
in :mod:`app.services.voice.conversation_session`. Uses the
``BrowserBridgeProvider`` stubs so the tests run without external
deps (faster-whisper, Piper).
"""

from __future__ import annotations

import pytest

from app.services.voice.conversation_session import (
    ConversationSession,
    TurnResult,
    VoiceRiskTier,
)
from app.services.voice.stt_pipeline import (
    BrowserBridgeProvider as STTBrowser,
    FasterWhisperProvider,
    STTError,
    STTPipeline,
    Transcript,
)
from app.services.voice.tts_pipeline import (
    BrowserBridgeProvider as TTSBrowser,
    PiperProvider,
    TTSError,
    TTSPipeline,
    Utterance,
)


# ── STT pipeline ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stt_browser_bridge_passes_through_text() -> None:
    stt = STTPipeline()
    result = await stt.transcribe("Hello Daena")
    assert isinstance(result, Transcript)
    assert result.text == "Hello Daena"
    assert result.provider == "browser"


@pytest.mark.asyncio
async def test_stt_browser_bridge_rejects_raw_bytes() -> None:
    stt = STTPipeline()
    result = await stt.transcribe(b"\x00\x01\x02")
    assert isinstance(result, STTError)
    assert "text" in result.reason.lower()


@pytest.mark.asyncio
async def test_stt_unknown_provider_returns_error() -> None:
    stt = STTPipeline()
    result = await stt.transcribe("hi", provider="not_registered")
    assert isinstance(result, STTError)


@pytest.mark.asyncio
async def test_stt_faster_whisper_graceful_when_dep_missing() -> None:
    """Lazy import must degrade to a structured error, not a crash."""
    stt = STTPipeline()
    stt.register(FasterWhisperProvider())
    result = await stt.transcribe(b"fake audio bytes", provider="faster_whisper")
    # Either real faster-whisper returned something or we got a
    # graceful ImportError reason. Both are acceptable.
    if isinstance(result, STTError):
        assert "faster-whisper" in result.reason.lower() or "install" in result.reason.lower()
    else:
        assert isinstance(result, Transcript)


# ── TTS pipeline ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tts_browser_bridge_returns_directive() -> None:
    tts = TTSPipeline()
    result = await tts.synthesize("Hi there")
    assert isinstance(result, Utterance)
    assert result.format == "browser-directive"
    assert result.metadata.get("client_synthesis") is True


@pytest.mark.asyncio
async def test_tts_piper_graceful_when_dep_missing() -> None:
    tts = TTSPipeline()
    tts.register(PiperProvider())
    result = await tts.synthesize("Hi", provider="piper")
    # Either real Piper returned audio or we got a graceful install message.
    if isinstance(result, TTSError):
        assert "piper" in result.reason.lower() or "install" in result.reason.lower()


@pytest.mark.asyncio
async def test_tts_rejects_empty_text() -> None:
    tts = TTSPipeline()
    result = await tts.synthesize("   ")
    assert isinstance(result, TTSError)


# ── ConversationSession ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_conversation_session_speaks_when_tier_low() -> None:
    """Low-tier replies get synthesized (or directed to the browser)."""
    stt = STTPipeline()
    tts = TTSPipeline()
    session = ConversationSession(
        stt=stt, tts=tts,
        chat_turn=lambda text: _fixed_reply("Got it. Let me know if you have more questions."),
    )
    result = await session.handle_turn("Hi there")
    assert isinstance(result, TurnResult)
    assert result.status == "spoken"
    assert result.tier in (VoiceRiskTier.NONE, VoiceRiskTier.LOW, VoiceRiskTier.MEDIUM)


@pytest.mark.asyncio
async def test_conversation_session_gates_high_tier_reply() -> None:
    """A reply containing pricing triggers the approval gate."""
    stt = STTPipeline()
    tts = TTSPipeline()
    session = ConversationSession(
        stt=stt, tts=tts,
        chat_turn=lambda text: _fixed_reply(
            "Our price starts at $50K per engagement. I can sign the contract today."
        ),
    )
    result = await session.handle_turn("What would this cost?")
    assert result.status == "awaiting_approval"
    assert result.tier in (VoiceRiskTier.HIGH, VoiceRiskTier.CRITICAL)
    assert result.approval_id and result.approval_id.startswith("voice-approval-")
    assert "$50K" in result.reply_text


@pytest.mark.asyncio
async def test_conversation_session_gates_critical_tier_reply() -> None:
    """Mention of credentials / PII export hits CRITICAL."""
    stt = STTPipeline()
    tts = TTSPipeline()
    session = ConversationSession(
        stt=stt, tts=tts,
        chat_turn=lambda text: _fixed_reply(
            "I can export your credentials dump for you right now."
        ),
    )
    result = await session.handle_turn("Can you send me the report?")
    assert result.status == "awaiting_approval"
    assert result.tier == VoiceRiskTier.CRITICAL


@pytest.mark.asyncio
async def test_conversation_session_logs_transcript() -> None:
    """transcript_log() must capture user + assistant turns."""
    stt = STTPipeline()
    tts = TTSPipeline()
    session = ConversationSession(
        stt=stt, tts=tts,
        chat_turn=lambda text: _fixed_reply("Nice to meet you."),
    )
    await session.handle_turn("Hello")
    log = session.transcript_log()
    assert log[0]["role"] == "user"
    assert log[0]["text"] == "Hello"
    assert log[1]["role"] == "assistant"
    assert log[1]["text"] == "Nice to meet you."


@pytest.mark.asyncio
async def test_conversation_session_handles_empty_stt_gracefully() -> None:
    stt = STTPipeline()
    tts = TTSPipeline()
    session = ConversationSession(
        stt=stt, tts=tts,
        chat_turn=lambda text: _fixed_reply("Should not run"),
    )
    result = await session.handle_turn("")  # empty string
    assert result.status == "error"


# ── Helpers ──────────────────────────────────────────────────────


async def _fixed_reply(text: str) -> str:
    return text
