"""Tests for Voice Service (Sprint 5, Phase 7).

Covers VoiceSettings, VoiceUsageMetrics, and VoiceService
CRUD operations and usage tracking.
"""

from __future__ import annotations

from app.services.voice_service import VoiceService, VoiceSettings, VoiceUsageMetrics

# ── VoiceSettings tests ──


class TestVoiceSettings:
    def test_default_fields(self):
        s = VoiceSettings()
        assert s.stt_enabled is True
        assert s.tts_enabled is False
        assert s.tts_rate == 1.0
        assert s.tts_language == "en-US"
        assert s.continuous_listen is False
        assert s.stt_provider == "browser"
        assert s.tts_provider == "browser"

    def test_to_dict(self):
        s = VoiceSettings(user_id="u1", tts_enabled=True, tts_rate=1.5)
        d = s.to_dict()
        assert d["user_id"] == "u1"
        assert d["tts_enabled"] is True
        assert d["tts_rate"] == 1.5

    def test_custom_providers(self):
        s = VoiceSettings(stt_provider="whisper", tts_provider="elevenlabs")
        assert s.stt_provider == "whisper"
        assert s.tts_provider == "elevenlabs"


# ── VoiceUsageMetrics tests ──


class TestVoiceUsageMetrics:
    def test_default_fields(self):
        m = VoiceUsageMetrics()
        assert m.total_stt_sessions == 0
        assert m.total_tts_reads == 0
        assert m.total_stt_duration_ms == 0
        assert m.last_used == ""

    def test_to_dict(self):
        m = VoiceUsageMetrics(
            user_id="u1",
            total_stt_sessions=5,
            total_tts_reads=3,
        )
        d = m.to_dict()
        assert d["total_stt_sessions"] == 5
        assert d["total_tts_reads"] == 3


# ── VoiceService tests ──


class TestVoiceService:
    def test_get_settings_creates_defaults(self):
        service = VoiceService()
        settings = service.get_settings("user-1")
        assert settings.user_id == "user-1"
        assert settings.stt_enabled is True

    def test_get_settings_returns_same_instance(self):
        service = VoiceService()
        s1 = service.get_settings("user-1")
        s2 = service.get_settings("user-1")
        assert s1 is s2

    def test_update_settings(self):
        service = VoiceService()
        updated = service.update_settings(
            "user-1",
            tts_enabled=True,
            tts_rate=1.5,
            tts_voice="Microsoft David",
        )
        assert updated.tts_enabled is True
        assert updated.tts_rate == 1.5
        assert updated.tts_voice == "Microsoft David"

    def test_update_settings_preserves_user_id(self):
        """user_id is not changed via updates dict."""
        service = VoiceService()
        settings = service.get_settings("user-1")
        # Update other fields, verify user_id stays
        service.update_settings("user-1", tts_rate=2.0)
        assert settings.user_id == "user-1"

    def test_get_metrics_creates_defaults(self):
        service = VoiceService()
        metrics = service.get_metrics("user-1")
        assert metrics.user_id == "user-1"
        assert metrics.total_stt_sessions == 0

    def test_record_stt_session(self):
        service = VoiceService()
        metrics = service.record_stt_session("user-1", duration_ms=5000)
        assert metrics.total_stt_sessions == 1
        assert metrics.total_stt_duration_ms == 5000
        assert metrics.last_used != ""

    def test_record_multiple_stt_sessions(self):
        service = VoiceService()
        service.record_stt_session("user-1", duration_ms=3000)
        metrics = service.record_stt_session("user-1", duration_ms=2000)
        assert metrics.total_stt_sessions == 2
        assert metrics.total_stt_duration_ms == 5000

    def test_record_tts_read(self):
        service = VoiceService()
        metrics = service.record_tts_read("user-1")
        assert metrics.total_tts_reads == 1
        assert metrics.last_used != ""

    def test_record_multiple_tts_reads(self):
        service = VoiceService()
        service.record_tts_read("user-1")
        service.record_tts_read("user-1")
        metrics = service.record_tts_read("user-1")
        assert metrics.total_tts_reads == 3

    def test_separate_user_metrics(self):
        service = VoiceService()
        service.record_stt_session("user-1", duration_ms=1000)
        service.record_stt_session("user-2", duration_ms=2000)
        assert service.get_metrics("user-1").total_stt_sessions == 1
        assert service.get_metrics("user-2").total_stt_sessions == 1
