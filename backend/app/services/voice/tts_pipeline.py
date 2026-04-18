"""TTS pipeline: unified text-to-speech with provider plugins.

Mirror of :mod:`app.services.voice.stt_pipeline`. Same provider-plugin
model so Daena can run browser-native (Phase 1), Piper local (Phase 2
default), and ElevenLabs Conversational (Phase 2 premium) behind the
same call surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Utterance:
    """Synthesized audio output."""

    audio: bytes
    format: str = "wav"
    duration_ms: int = 0
    provider: str = ""
    voice: str = ""
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TTSError:
    """Returned when a provider cannot synthesize."""

    provider: str
    reason: str


class TTSProvider:
    """Abstract provider interface."""

    name: str = "abstract"

    async def synthesize(
        self,
        text: str,
        *,
        voice: str = "default",
        rate: float = 1.0,
        language: str = "en",
    ) -> Utterance | TTSError:
        raise NotImplementedError


class BrowserBridgeProvider(TTSProvider):
    """Phase-1 pass-through.

    The browser's ``SpeechSynthesis`` API handles actual synthesis on
    the client. On the server side we return an empty audio payload
    plus metadata that the frontend uses to decide whether to speak.
    This mirrors how the browser STT provider works.
    """

    name = "browser"

    async def synthesize(
        self, text: str, *, voice: str = "default", rate: float = 1.0, language: str = "en",
    ) -> Utterance | TTSError:
        if not text.strip():
            return TTSError(provider=self.name, reason="Empty text")
        return Utterance(
            audio=b"",
            format="browser-directive",
            provider=self.name,
            voice=voice,
            text=text,
            metadata={"rate": rate, "language": language, "client_synthesis": True},
        )


class PiperProvider(TTSProvider):
    """Local Piper TTS. Lazy-imports the dep.

    Piper ships fast (sub-second) CPU-only synthesis with dozens of
    voices. Default voice ``en_US-amy-medium`` is a good neutral starter
    for outbound sales calls.
    """

    name = "piper"

    def __init__(self, voice_model: str = "en_US-amy-medium") -> None:
        self.voice_model = voice_model
        self._voice = None

    async def synthesize(
        self, text: str, *, voice: str = "default", rate: float = 1.0, language: str = "en",
    ) -> Utterance | TTSError:
        if not text.strip():
            return TTSError(provider=self.name, reason="Empty text")
        try:
            from piper.voice import PiperVoice  # type: ignore
        except ImportError:
            return TTSError(
                provider=self.name,
                reason=(
                    "piper-tts not installed. "
                    "Run: pip install piper-tts (requires the voice model file)."
                ),
            )

        if self._voice is None:
            try:
                self._voice = PiperVoice.load(self.voice_model)
            except Exception as exc:
                return TTSError(
                    provider=self.name,
                    reason=f"Could not load Piper voice model {self.voice_model!r}: {exc}",
                )

        try:
            import io
            import wave
            buf = io.BytesIO()
            with wave.open(buf, "wb") as wav:
                self._voice.synthesize(text, wav)
            data = buf.getvalue()
            return Utterance(
                audio=data,
                format="wav",
                provider=self.name,
                voice=self.voice_model,
                text=text,
            )
        except Exception as exc:
            return TTSError(provider=self.name, reason=str(exc))


# ── Pipeline orchestrator ────────────────────────────────────────


class TTSPipeline:
    """Dispatches to the selected provider with a single interface."""

    def __init__(self, default_provider: TTSProvider | None = None) -> None:
        self._providers: dict[str, TTSProvider] = {}
        self._default: TTSProvider = default_provider or BrowserBridgeProvider()
        self._providers[self._default.name] = self._default

    def register(self, provider: TTSProvider) -> None:
        self._providers[provider.name] = provider

    def available(self) -> list[str]:
        return sorted(self._providers)

    async def synthesize(
        self,
        text: str,
        *,
        provider: str | None = None,
        voice: str = "default",
        rate: float = 1.0,
        language: str = "en",
    ) -> Utterance | TTSError:
        p = self._providers.get(provider) if provider else self._default
        if p is None:
            return TTSError(
                provider=provider or "unknown",
                reason=f"Provider {provider!r} not registered. "
                       f"Registered: {self.available()}",
            )
        return await p.synthesize(text, voice=voice, rate=rate, language=language)
