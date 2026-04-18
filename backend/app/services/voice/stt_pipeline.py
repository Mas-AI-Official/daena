"""STT pipeline: unified speech-to-text with provider plugins.

Phase I of Roadmap V2.

Design
------
A single :class:`STTPipeline` dispatches to one of several
:class:`STTProvider` implementations. The provider is chosen per-call
(so one conversation can start on the browser and escalate to
FasterWhisper when the operator hands off to a mobile device without
Web Speech support).

The Phase-1 ``BrowserBridgeProvider`` is always available because it
is a pure pass-through: the browser already transcribed the audio via
Web Speech API, and the "audio" field carries the finalized text. That
keeps the pipeline symmetrical with the richer providers and lets
every caller talk to one class.

Heavier providers (``FasterWhisperProvider``, ``DeepgramProvider``)
lazy-import their dependencies inside the transcribe methods so the
module imports cleanly on machines that do not have the optional
packages installed. When called without the dep present, they return
a structured ``STTError`` instead of crashing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Transcript:
    """Finalized transcript result."""

    text: str
    language: str = "en"
    duration_ms: int = 0
    provider: str = ""
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class STTError:
    """Returned (not raised) when a provider cannot run.

    Using a value return instead of an exception means the pipeline
    caller can decide whether to fall back to a different provider
    without unwinding an entire conversation turn.
    """

    provider: str
    reason: str


class STTProvider:
    """Abstract provider interface."""

    name: str = "abstract"

    async def transcribe(
        self,
        audio: bytes | str,
        *,
        language: str = "en",
    ) -> Transcript | STTError:
        raise NotImplementedError


class BrowserBridgeProvider(STTProvider):
    """Phase-1 pass-through. The browser transcribed already.

    Accepts either bytes (ignored) or a str (already a transcript).
    This matches the existing :mod:`voice_service` flow where the
    frontend hands finalized text to the chat orchestrator.
    """

    name = "browser"

    async def transcribe(
        self, audio: bytes | str, *, language: str = "en",
    ) -> Transcript | STTError:
        if isinstance(audio, bytes):
            # Nothing to do with raw audio on the browser bridge; the
            # caller must send text.
            return STTError(
                provider=self.name,
                reason=(
                    "BrowserBridgeProvider expects finalized text, not "
                    "raw audio. Use FasterWhisperProvider for bytes input."
                ),
            )
        text = audio.strip()
        if not text:
            return STTError(provider=self.name, reason="Empty transcript")
        return Transcript(
            text=text,
            language=language,
            provider=self.name,
            metadata={"source": "web_speech_api"},
        )


class FasterWhisperProvider(STTProvider):
    """Local faster-whisper provider. Lazy-imports the dep.

    Default model ``base`` is a good latency/quality trade-off for the
    initial paid pilots. Upgrades to ``medium`` or ``large-v3`` are a
    constructor arg, not a code change.
    """

    name = "faster_whisper"

    def __init__(self, model_size: str = "base") -> None:
        self.model_size = model_size
        self._model = None  # lazy-loaded

    async def transcribe(
        self, audio: bytes | str, *, language: str = "en",
    ) -> Transcript | STTError:
        if isinstance(audio, str):
            return STTError(
                provider=self.name,
                reason="FasterWhisperProvider expects raw audio bytes, not text.",
            )
        # Lazy import so pytest collection works on machines without the
        # optional dep installed. Matches CLAUDE.md rule 9: real fallback,
        # not NotImplementedError.
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError:
            return STTError(
                provider=self.name,
                reason=(
                    "faster-whisper package not installed. "
                    "Run: pip install faster-whisper"
                ),
            )

        if self._model is None:
            self._model = WhisperModel(self.model_size, compute_type="int8")

        try:
            segments, info = self._model.transcribe(
                audio_input_for_whisper(audio),
                language=language,
            )
            text = " ".join(s.text.strip() for s in segments).strip()
            return Transcript(
                text=text,
                language=info.language if info else language,
                duration_ms=int((info.duration if info else 0) * 1000),
                provider=self.name,
                metadata={"model": self.model_size},
            )
        except Exception as exc:
            return STTError(provider=self.name, reason=str(exc))


def audio_input_for_whisper(audio: bytes):
    """Adapter so test doubles and the real model share a signature.

    Real model accepts a path, a numpy array, or a file-like object.
    Tests feed bytes; we wrap them in BytesIO so the local model can
    consume them without a round-trip to disk.
    """
    import io
    return io.BytesIO(audio)


# ── Pipeline orchestrator ────────────────────────────────────────


class STTPipeline:
    """Dispatches to the selected provider with a single interface."""

    def __init__(self, default_provider: STTProvider | None = None) -> None:
        self._providers: dict[str, STTProvider] = {}
        self._default: STTProvider = default_provider or BrowserBridgeProvider()
        self._providers[self._default.name] = self._default

    def register(self, provider: STTProvider) -> None:
        self._providers[provider.name] = provider

    def available(self) -> list[str]:
        return sorted(self._providers)

    async def transcribe(
        self,
        audio: bytes | str,
        *,
        provider: str | None = None,
        language: str = "en",
    ) -> Transcript | STTError:
        p = self._providers.get(provider) if provider else self._default
        if p is None:
            return STTError(
                provider=provider or "unknown",
                reason=f"Provider {provider!r} not registered. "
                       f"Registered: {self.available()}",
            )
        return await p.transcribe(audio, language=language)
