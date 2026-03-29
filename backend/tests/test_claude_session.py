"""Tests for persistent Claude Code session manager."""

from __future__ import annotations

from datetime import datetime

import pytest

from app.services.runtimes.adapters.claude_session import (
    ClaudeSession,
    ClaudeSessionManager,
    ClaudeSessionResult,
)


class TestClaudeSessionResult:
    def test_basic_result(self):
        r = ClaudeSessionResult(
            result_text="Hello",
            session_id="abc-123",
            cost_usd=0.05,
            duration_ms=1000,
        )
        assert r.result_text == "Hello"
        assert r.session_id == "abc-123"
        assert not r.is_error

    def test_error_result(self):
        r = ClaudeSessionResult(
            result_text="[Error]",
            session_id="",
            is_error=True,
        )
        assert r.is_error


class TestClaudeSession:
    def test_create_session(self):
        s = ClaudeSession(daena_session_id="test-1")
        assert s.daena_session_id == "test-1"
        assert s.cli_session_id is None
        assert s.command_count == 0
        assert s.is_alive is True

    def test_parse_output_valid(self):
        s = ClaudeSession(daena_session_id="test")
        stdout = '{"type":"result","result":"Hello","session_id":"abc","total_cost_usd":0.01,"duration_ms":500,"is_error":false,"num_turns":1}'
        result = s._parse_output(stdout)
        assert result.result_text == "Hello"
        assert result.session_id == "abc"
        assert result.cost_usd == 0.01
        assert result.duration_ms == 500

    def test_parse_output_multiline(self):
        s = ClaudeSession(daena_session_id="test")
        stdout = '{"type":"system","subtype":"init"}\n{"type":"result","result":"OK","session_id":"xyz","total_cost_usd":0.02,"duration_ms":200,"is_error":false}'
        result = s._parse_output(stdout)
        assert result.result_text == "OK"
        assert result.session_id == "xyz"

    def test_parse_output_empty(self):
        s = ClaudeSession(daena_session_id="test")
        result = s._parse_output("")
        assert result.is_error

    def test_parse_output_no_result_type(self):
        s = ClaudeSession(daena_session_id="test")
        result = s._parse_output('not json at all')
        assert result.is_error

    def test_get_status(self):
        s = ClaudeSession(daena_session_id="test-1", cli_session_id="cli-abc")
        s.command_count = 3
        s.total_cost_usd = 0.15
        status = s.get_status()
        assert status["daena_session_id"] == "test-1"
        assert status["cli_session_id"] == "cli-abc"
        assert status["command_count"] == 3
        assert status["total_cost_usd"] == 0.15


class TestClaudeSessionManager:
    def test_create_manager(self):
        mgr = ClaudeSessionManager()
        assert mgr.list_sessions() == []

    def test_get_or_create(self):
        mgr = ClaudeSessionManager()
        s1 = mgr.get_or_create("sess-1")
        assert s1.daena_session_id == "sess-1"
        # Same session returned
        s2 = mgr.get_or_create("sess-1")
        assert s1 is s2

    def test_get_nonexistent(self):
        mgr = ClaudeSessionManager()
        assert mgr.get("nope") is None

    def test_end_session(self):
        mgr = ClaudeSessionManager()
        mgr.get_or_create("sess-1")
        assert mgr.end_session("sess-1") is True
        assert mgr.get("sess-1") is None
        assert mgr.end_session("sess-1") is False  # Already gone

    def test_list_sessions(self):
        mgr = ClaudeSessionManager()
        mgr.get_or_create("sess-1")
        mgr.get_or_create("sess-2")
        sessions = mgr.list_sessions()
        assert len(sessions) == 2
        ids = {s["daena_session_id"] for s in sessions}
        assert ids == {"sess-1", "sess-2"}

    def test_cleanup_stale(self):
        mgr = ClaudeSessionManager()
        s = mgr.get_or_create("old")
        # Pretend it was created 25 hours ago
        from datetime import timedelta
        s.created_at = datetime.utcnow() - timedelta(hours=25)
        removed = mgr.cleanup_stale(max_age_hours=24)
        assert removed == 1
        assert mgr.get("old") is None

    def test_cleanup_keeps_fresh(self):
        mgr = ClaudeSessionManager()
        mgr.get_or_create("fresh")
        removed = mgr.cleanup_stale(max_age_hours=24)
        assert removed == 0
        assert mgr.get("fresh") is not None

    def test_error_recovery(self):
        mgr = ClaudeSessionManager()
        s = mgr.get_or_create("sess-1")
        s.is_alive = False
        s.history.append(ClaudeSessionResult(result_text="old", session_id="x"))
        # get_or_create returns same dead session
        s2 = mgr.get_or_create("sess-1")
        assert s2 is s  # Same object, still dead
        # But send() should recover automatically (would need live CLI to test fully)
