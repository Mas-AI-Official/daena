"""Voice Service: thin backend layer for voice integration.

Browser-native Web Speech API handles STT and TTS directly.
This service manages voice settings, tracks voice usage metrics,
and provides the upgrade path to server-side Whisper/ElevenLabs.

Current architecture (Phase 1, zero cost):
  Frontend SpeechRecognition -> transcribed text -> normal chat message
  Frontend SpeechSynthesis <- response text <- normal chat response

Future upgrade path:
  Frontend audio stream -> WebSocket -> Whisper STT -> text
  Text -> ElevenLabs/XTTS -> audio stream -> WebSocket -> Frontend
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class VoiceSettings:
    """Per-user voice configuration.

    Attributes:
        user_id: Owner of these settings.
        stt_enabled: Speech-to-text active.
        tts_enabled: Text-to-speech auto-read active.
        tts_voice: Preferred TTS voice name.
        tts_rate: Speech rate multiplier (0.5 to 2.0).
        tts_language: Preferred language code.
        continuous_listen: Always-listen mode.
        stt_provider: 'browser' (Phase 1), 'whisper' (future).
        tts_provider: 'browser' (Phase 1), 'elevenlabs' (future).
    """

    user_id: str = ""
    stt_enabled: bool = True
    tts_enabled: bool = False
    tts_voice: str = ""
    tts_rate: float = 1.0
    tts_language: str = "en-US"
    continuous_listen: bool = False
    stt_provider: str = "browser"
    tts_provider: str = "browser"

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API responses."""
        return {
            "user_id": self.user_id,
            "stt_enabled": self.stt_enabled,
            "tts_enabled": self.tts_enabled,
            "tts_voice": self.tts_voice,
            "tts_rate": self.tts_rate,
            "tts_language": self.tts_language,
            "continuous_listen": self.continuous_listen,
            "stt_provider": self.stt_provider,
            "tts_provider": self.tts_provider,
        }


@dataclass
class VoiceUsageMetrics:
    """Track voice feature usage for analytics.

    Attributes:
        user_id: Owner.
        total_stt_sessions: Number of STT sessions started.
        total_tts_reads: Number of TTS responses played.
        total_stt_duration_ms: Approximate STT listening duration.
        last_used: Last time voice was used.
    """

    user_id: str = ""
    total_stt_sessions: int = 0
    total_tts_reads: int = 0
    total_stt_duration_ms: int = 0
    last_used: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API responses."""
        return {
            "user_id": self.user_id,
            "total_stt_sessions": self.total_stt_sessions,
            "total_tts_reads": self.total_tts_reads,
            "total_stt_duration_ms": self.total_stt_duration_ms,
            "last_used": self.last_used,
        }


class VoiceService:
    """In-memory voice settings and usage tracking.

    Phase 1: All STT/TTS is browser-native. This service only
    manages settings and tracks usage metrics.

    Usage::

        service = VoiceService()
        settings = service.get_settings("user-1")
        service.record_stt_session("user-1", duration_ms=5000)
    """

    def __init__(self) -> None:
        self._settings: dict[str, VoiceSettings] = {}
        self._metrics: dict[str, VoiceUsageMetrics] = {}

    def get_settings(self, user_id: str) -> VoiceSettings:
        """Get voice settings for a user (creates defaults if missing)."""
        if user_id not in self._settings:
            self._settings[user_id] = VoiceSettings(user_id=user_id)
        return self._settings[user_id]

    def update_settings(
        self,
        user_id: str,
        **updates: Any,
    ) -> VoiceSettings:
        """Update voice settings for a user.

        Args:
            user_id: User to update.
            **updates: Fields to update.

        Returns:
            Updated settings.
        """
        settings = self.get_settings(user_id)
        for key, value in updates.items():
            if hasattr(settings, key) and key != "user_id":
                setattr(settings, key, value)

        logger.info(
            "voice.settings_updated",
            user_id=user_id,
            fields=list(updates.keys()),
        )
        return settings

    def get_metrics(self, user_id: str) -> VoiceUsageMetrics:
        """Get voice usage metrics for a user."""
        if user_id not in self._metrics:
            self._metrics[user_id] = VoiceUsageMetrics(user_id=user_id)
        return self._metrics[user_id]

    def record_stt_session(
        self,
        user_id: str,
        duration_ms: int = 0,
    ) -> VoiceUsageMetrics:
        """Record a completed STT session.

        Args:
            user_id: User who used STT.
            duration_ms: Approximate listening duration.

        Returns:
            Updated metrics.
        """
        metrics = self.get_metrics(user_id)
        metrics.total_stt_sessions += 1
        metrics.total_stt_duration_ms += duration_ms
        metrics.last_used = datetime.now(UTC).isoformat()
        return metrics

    def record_tts_read(self, user_id: str) -> VoiceUsageMetrics:
        """Record a TTS response read.

        Args:
            user_id: User who used TTS.

        Returns:
            Updated metrics.
        """
        metrics = self.get_metrics(user_id)
        metrics.total_tts_reads += 1
        metrics.last_used = datetime.now(UTC).isoformat()
        return metrics
