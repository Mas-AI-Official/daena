"""Tests for refinement service circuit breaker, emergency stop, and cost tracking.

Pure unit tests: no LLM calls, no database, no HTTP.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.services.skill_refinery.refinement_service import (
    _daily_cost,
    _emergency_stop,
    _parse_json,
    _track_cost,
    clear_emergency_stop,
    get_daily_cost,
    is_emergency_stopped,
    trigger_emergency_stop,
)

# ── Fixtures ──


@pytest.fixture(autouse=True)
def _reset_state():
    """Reset global state before each test."""
    _emergency_stop.clear()
    _daily_cost.clear()
    yield
    _emergency_stop.clear()
    _daily_cost.clear()


# ── Emergency stop tests ──


class TestEmergencyStop:
    """Emergency stop flag behavior."""

    def test_trigger_sets_flag(self) -> None:
        """trigger_emergency_stop sets the event flag."""
        assert not is_emergency_stopped()
        trigger_emergency_stop()
        assert is_emergency_stopped()

    def test_clear_resets_flag(self) -> None:
        """clear_emergency_stop clears the event flag."""
        trigger_emergency_stop()
        assert is_emergency_stopped()
        clear_emergency_stop()
        assert not is_emergency_stopped()

    def test_double_trigger_is_idempotent(self) -> None:
        """Calling trigger twice does not raise or change state."""
        trigger_emergency_stop()
        trigger_emergency_stop()
        assert is_emergency_stopped()

    def test_clear_without_trigger_is_safe(self) -> None:
        """Clearing when not set does not raise."""
        clear_emergency_stop()
        assert not is_emergency_stopped()


# ── Daily cost tracking tests ──


class TestDailyCostTracking:
    """In-memory daily token usage tracking."""

    def test_track_cost_increments(self) -> None:
        """_track_cost accumulates tokens for today."""
        _track_cost(100)
        _track_cost(200)
        today = date.today().isoformat()
        assert _daily_cost[today] == 300

    def test_track_cost_zero(self) -> None:
        """Tracking zero tokens is valid."""
        _track_cost(0)
        today = date.today().isoformat()
        assert _daily_cost[today] == 0

    def test_get_daily_cost_structure(self) -> None:
        """get_daily_cost returns expected keys and types."""
        result = get_daily_cost()
        assert "date" in result
        assert "tokens_used" in result
        assert "limit" in result
        assert "remaining" in result
        assert "paused" in result
        assert result["date"] == date.today().isoformat()
        assert isinstance(result["tokens_used"], (int, float))
        assert isinstance(result["limit"], int)
        assert isinstance(result["remaining"], (int, float))
        assert isinstance(result["paused"], bool)

    def test_get_daily_cost_empty(self) -> None:
        """get_daily_cost with no usage returns full budget."""
        result = get_daily_cost()
        assert result["tokens_used"] == 0
        assert result["remaining"] == 100_000
        assert result["paused"] is False

    def test_get_daily_cost_partial_usage(self) -> None:
        """get_daily_cost reflects partial usage correctly."""
        _track_cost(50_000)
        result = get_daily_cost()
        assert result["tokens_used"] == 50_000
        assert result["remaining"] == 50_000
        assert result["paused"] is False

    def test_get_daily_cost_at_limit(self) -> None:
        """get_daily_cost reports paused when limit is reached."""
        _track_cost(100_000)
        result = get_daily_cost()
        assert result["tokens_used"] == 100_000
        assert result["remaining"] == 0
        assert result["paused"] is True

    def test_get_daily_cost_over_limit(self) -> None:
        """get_daily_cost clamps remaining to zero when over limit."""
        _track_cost(150_000)
        result = get_daily_cost()
        assert result["tokens_used"] == 150_000
        assert result["remaining"] == 0
        assert result["paused"] is True


# ── JSON parsing tests ──


class TestParseJson:
    """_parse_json handles valid, invalid, and fenced JSON."""

    def test_valid_json(self) -> None:
        """Plain valid JSON parses correctly."""
        result = _parse_json('{"key": "value", "num": 42}')
        assert result == {"key": "value", "num": 42}

    def test_invalid_json_returns_empty(self) -> None:
        """Invalid JSON returns empty dict."""
        result = _parse_json("this is not json at all")
        assert result == {}

    def test_empty_string_returns_empty(self) -> None:
        """Empty string returns empty dict."""
        result = _parse_json("")
        assert result == {}

    def test_fenced_json(self) -> None:
        """JSON wrapped in markdown fences parses correctly."""
        fenced = '```json\n{"verdict": "APPROVE", "confidence": 0.85}\n```'
        result = _parse_json(fenced)
        assert result["verdict"] == "APPROVE"
        assert result["confidence"] == 0.85

    def test_fenced_json_no_lang_tag(self) -> None:
        """Fenced JSON without language tag also parses."""
        fenced = '```\n{"steps": ["a", "b"]}\n```'
        result = _parse_json(fenced)
        assert result["steps"] == ["a", "b"]

    def test_nested_json(self) -> None:
        """Nested JSON structures parse correctly."""
        nested = '{"outer": {"inner": [1, 2, 3]}, "flag": true}'
        result = _parse_json(nested)
        assert result["outer"]["inner"] == [1, 2, 3]
        assert result["flag"] is True

    def test_whitespace_padded_json(self) -> None:
        """JSON with leading/trailing whitespace parses."""
        padded = '  \n  {"key": "val"}  \n  '
        result = _parse_json(padded)
        assert result == {"key": "val"}
