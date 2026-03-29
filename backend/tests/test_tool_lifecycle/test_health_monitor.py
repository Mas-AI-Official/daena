"""Tests for Health Monitor -- the difference between 'demo crashes' and 'demo recovers'.

Tests the fallback chain that makes Daena resilient:
- Provider goes down -> fall to next cheapest
- Tool goes down -> tell agent to adapt
- Every fallback is logged and visible to user
"""

from __future__ import annotations

import asyncio
import pytest

from app.services.tool_lifecycle.health_monitor import (
    FallbackEvent,
    HealthCheck,
    HealthMonitor,
    HealthState,
)


@pytest.fixture
def monitor() -> HealthMonitor:
    m = HealthMonitor()
    m.register_provider("ollama")
    m.register_provider("groq")
    m.register_provider("anthropic_haiku")
    m.register_provider("openai_gpt4o")
    return m


# ── Provider Health Tests ─────────────────────────────────────

class TestProviderHealth:
    def test_initial_state_unknown(self, monitor: HealthMonitor):
        health = monitor.get_provider_health("ollama")
        assert health.state == HealthState.UNKNOWN

    def test_set_provider_healthy(self, monitor: HealthMonitor):
        monitor.set_provider_health("ollama", HealthState.HEALTHY)
        health = monitor.get_provider_health("ollama")
        assert health.state == HealthState.HEALTHY

    def test_set_provider_unreachable(self, monitor: HealthMonitor):
        monitor.set_provider_health("ollama", HealthState.UNREACHABLE, error="Connection refused")
        health = monitor.get_provider_health("ollama")
        assert health.state == HealthState.UNREACHABLE
        assert "refused" in health.error

    def test_get_all_providers(self, monitor: HealthMonitor):
        all_health = monitor.get_all_provider_health()
        assert "ollama" in all_health
        assert "groq" in all_health

    @pytest.mark.asyncio
    async def test_check_with_function(self):
        monitor = HealthMonitor()

        async def healthy_check():
            return True

        monitor.register_provider("test_provider", check_fn=healthy_check)
        health = await monitor.check_provider("test_provider")
        assert health.state == HealthState.HEALTHY
        assert health.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_check_with_failing_function(self):
        monitor = HealthMonitor()

        async def failing_check():
            raise ConnectionError("Connection refused")

        monitor.register_provider("bad_provider", check_fn=failing_check)
        health = await monitor.check_provider("bad_provider")
        assert health.state == HealthState.UNREACHABLE
        assert "refused" in health.error


# ── Tool Health Tests ─────────────────────────────────────────

class TestToolHealth:
    def test_initial_tool_unknown(self, monitor: HealthMonitor):
        assert monitor.is_tool_healthy("jira")  # unknown = assume healthy

    def test_set_tool_healthy(self, monitor: HealthMonitor):
        monitor.set_tool_health("jira", HealthState.HEALTHY)
        assert monitor.is_tool_healthy("jira")

    def test_set_tool_unreachable(self, monitor: HealthMonitor):
        monitor.set_tool_health("jira", HealthState.UNREACHABLE, error="MCP server down")
        assert not monitor.is_tool_healthy("jira")
        health = monitor.get_tool_health("jira")
        assert health.state == HealthState.UNREACHABLE


# ── Fallback Chain Tests ──────────────────────────────────────

class TestFallbackChain:
    def test_fallback_after_ollama_failure(self, monitor: HealthMonitor):
        """Ollama down -> should suggest groq (next cheapest)."""
        fallback = monitor.get_best_fallback("ollama")
        assert fallback == "groq"

    def test_fallback_skips_unreachable(self, monitor: HealthMonitor):
        """If groq is also down, skip to next."""
        monitor.set_provider_health("groq", HealthState.UNREACHABLE)
        fallback = monitor.get_best_fallback("ollama")
        assert fallback == "gemini_flash"  # next in chain

    def test_fallback_with_exclusions(self, monitor: HealthMonitor):
        fallback = monitor.get_best_fallback("ollama", exclude=["groq", "gemini_flash"])
        assert fallback == "anthropic_haiku"

    def test_all_providers_down_returns_none(self, monitor: HealthMonitor):
        """When everything is down, return None (graceful give-up)."""
        for provider in monitor.get_fallback_chain():
            monitor.set_provider_health(provider, HealthState.UNREACHABLE)
        fallback = monitor.get_best_fallback("ollama")
        assert fallback is None

    def test_custom_fallback_chain(self, monitor: HealthMonitor):
        monitor.set_fallback_chain(["anthropic_sonnet", "openai_gpt4o"])
        fallback = monitor.get_best_fallback("ollama")
        assert fallback == "anthropic_sonnet"


# ── Fallback History Tests ────────────────────────────────────

class TestFallbackHistory:
    def test_record_fallback(self, monitor: HealthMonitor):
        monitor.record_fallback(FallbackEvent(
            original_target="ollama",
            fallback_target="groq",
            reason="Ollama not running",
            cost_impact="free -> $0.59/1M",
        ))
        history = monitor.get_fallback_history()
        assert len(history) == 1
        assert history[0].original_target == "ollama"

    def test_history_limit(self, monitor: HealthMonitor):
        for i in range(30):
            monitor.record_fallback(FallbackEvent(
                original_target=f"provider_{i}",
                fallback_target="backup",
                reason="test",
            ))
        history = monitor.get_fallback_history(limit=10)
        assert len(history) == 10

    def test_fallback_summary(self, monitor: HealthMonitor):
        monitor.record_fallback(FallbackEvent(
            original_target="ollama",
            fallback_target="groq",
            reason="offline",
        ))
        monitor.record_fallback(FallbackEvent(
            original_target="ollama",
            fallback_target="haiku",
            reason="still offline",
        ))
        summary = monitor.get_fallback_summary()
        assert summary["total_fallbacks"] == 2
        assert "ollama" in summary["providers_affected"]


# ── User-Facing Messages Tests ────────────────────────────────

class TestMessages:
    def test_fallback_message_readable(self):
        event = FallbackEvent(
            original_target="Ollama",
            fallback_target="Claude Haiku",
            reason="Ollama service not running",
            cost_impact="Free -> $0.25/1M tokens",
        )
        msg = HealthMonitor.format_fallback_message(event)
        assert "Ollama" in msg
        assert "Claude Haiku" in msg
        assert "$0.25" in msg

    def test_tool_unavailable_message(self):
        msg = HealthMonitor.format_tool_unavailable("jira", "MCP server timeout")
        assert "jira" in msg
        assert "unavailable" in msg
        assert "adapt" in msg


# ── Real Scenario: Demo Doesn't Crash ─────────────────────────

class TestDemoScenario:
    def test_ollama_offline_graceful_recovery(self, monitor: HealthMonitor):
        """THE demo scenario: Ollama not running, system recovers."""

        # Step 1: Router tries Ollama -> it's down
        monitor.set_provider_health("ollama", HealthState.UNREACHABLE,
                                     error="Connection refused on localhost:11434")

        # Step 2: Get fallback
        fallback = monitor.get_best_fallback("ollama")
        assert fallback is not None  # MUST NOT be None

        # Step 3: Record the fallback
        monitor.record_fallback(FallbackEvent(
            original_target="Ollama (llama3.1:8b)",
            fallback_target=f"{fallback}",
            reason="Ollama service not running on localhost:11434",
            cost_impact="Free -> cloud pricing",
        ))

        # Step 4: User sees explanation, not error
        history = monitor.get_fallback_history()
        assert len(history) == 1
        msg = HealthMonitor.format_fallback_message(history[0])
        assert "unavailable" in msg
        assert "Routed to" in msg

    def test_multiple_providers_cascade(self, monitor: HealthMonitor):
        """Ollama down, Groq down, lands on Haiku."""
        monitor.set_provider_health("ollama", HealthState.UNREACHABLE)
        monitor.set_provider_health("groq", HealthState.UNREACHABLE)
        monitor.set_provider_health("gemini_flash", HealthState.UNREACHABLE)

        fallback = monitor.get_best_fallback("ollama")
        assert fallback == "anthropic_haiku"

    def test_tool_down_agent_adapts(self, monitor: HealthMonitor):
        """Tool is down -> agent gets a clean error message, not stack trace."""
        monitor.set_tool_health("jira", HealthState.UNREACHABLE, error="MCP timeout")
        msg = HealthMonitor.format_tool_unavailable("jira", "MCP timeout")
        assert "stack trace" not in msg.lower()
        assert "adapt" in msg
