"""Tests for UsageTracker -- analytics, reporting, pattern detection."""

from __future__ import annotations

import pytest

from app.services.tool_lifecycle.usage_tracker import (
    SessionCostReport,
    ToolCooccurrence,
    UsageRecord,
    UsageTracker,
)


CONV = "conv-001"
AGENT = "agent-eng-1"
DEPT = "engineering"


@pytest.fixture
def tracker() -> UsageTracker:
    return UsageTracker()


@pytest.fixture
def active_tracker() -> UsageTracker:
    """Tracker with some activity already recorded."""
    t = UsageTracker()
    t.record_activation(CONV, "google_drive", AGENT, DEPT)
    t.record_activation(CONV, "terminal", AGENT, DEPT)
    t.record_call(CONV, "google_drive")
    t.record_call(CONV, "google_drive")
    t.record_call(CONV, "terminal")
    t.record_turn_snapshot(CONV, 2)
    return t


# ── Recording Tests ───────────────────────────────────────────

class TestRecording:
    def test_record_activation(self, tracker: UsageTracker):
        tracker.record_activation(CONV, "drive", AGENT, DEPT)
        stats = tracker.get_tool_stats(CONV, "drive")
        assert stats is not None
        assert stats.tool_id == "drive"
        assert stats.agent_id == AGENT
        assert stats.call_count == 0

    def test_record_deactivation(self, active_tracker: UsageTracker):
        active_tracker.record_deactivation(CONV, "google_drive")
        stats = active_tracker.get_tool_stats(CONV, "google_drive")
        assert stats.deactivated_at is not None

    def test_record_call_increments_count(self, active_tracker: UsageTracker):
        stats = active_tracker.get_tool_stats(CONV, "google_drive")
        assert stats.call_count == 2

    def test_record_call_with_tokens_saved(self, tracker: UsageTracker):
        tracker.record_activation(CONV, "drive", AGENT, DEPT)
        tracker.record_call(CONV, "drive", tokens_saved=150)
        tracker.record_call(CONV, "drive", tokens_saved=150)
        stats = tracker.get_tool_stats(CONV, "drive")
        assert stats.tokens_saved == 300

    def test_record_call_with_error(self, tracker: UsageTracker):
        tracker.record_activation(CONV, "drive", AGENT, DEPT)
        tracker.record_call(CONV, "drive", error=True)
        stats = tracker.get_tool_stats(CONV, "drive")
        assert stats.errors == 1
        assert stats.call_count == 1

    def test_record_call_nonexistent_conversation(self, tracker: UsageTracker):
        """No-op when conversation doesn't exist."""
        tracker.record_call("nonexistent", "drive")  # should not raise


# ── Reporting Tests ───────────────────────────────────────────

class TestReporting:
    def test_session_report_basic(self, active_tracker: UsageTracker):
        report = active_tracker.get_session_report(CONV)
        assert isinstance(report, SessionCostReport)
        assert report.conversation_id == CONV
        assert report.total_tools_used == 2
        assert report.total_calls == 3  # 2 drive + 1 terminal
        assert report.total_errors == 0

    def test_session_report_avg_active(self, active_tracker: UsageTracker):
        report = active_tracker.get_session_report(CONV)
        assert report.avg_tools_active_per_turn == 2.0

    def test_session_report_duration(self, active_tracker: UsageTracker):
        report = active_tracker.get_session_report(CONV)
        assert report.duration_seconds >= 0

    def test_session_report_empty_conversation(self, tracker: UsageTracker):
        report = tracker.get_session_report("nonexistent")
        assert report.total_tools_used == 0
        assert report.total_calls == 0

    def test_session_report_includes_records(self, active_tracker: UsageTracker):
        report = active_tracker.get_session_report(CONV)
        assert len(report.tools) == 2
        tool_ids = {r.tool_id for r in report.tools}
        assert tool_ids == {"google_drive", "terminal"}


# ── Pattern Detection Tests ───────────────────────────────────

class TestPatterns:
    def test_patterns_with_enough_history(self, tracker: UsageTracker):
        """Detect co-occurrence after multiple sessions."""
        # Session 1: drive + search
        tracker.record_activation("s1", "drive", AGENT, DEPT)
        tracker.record_activation("s1", "search", AGENT, DEPT)
        tracker.record_call("s1", "drive")
        tracker.record_call("s1", "search")
        tracker.learn_session_patterns("s1", AGENT)

        # Session 2: drive + search
        tracker.record_activation("s2", "drive", AGENT, DEPT)
        tracker.record_activation("s2", "search", AGENT, DEPT)
        tracker.record_call("s2", "drive")
        tracker.record_call("s2", "search")
        tracker.learn_session_patterns("s2", AGENT)

        # Session 3: drive + slack (different pair)
        tracker.record_activation("s3", "drive", AGENT, DEPT)
        tracker.record_activation("s3", "slack", AGENT, DEPT)
        tracker.record_call("s3", "drive")
        tracker.record_call("s3", "slack")
        tracker.learn_session_patterns("s3", AGENT)

        patterns = tracker.get_patterns(AGENT, min_co_occurrence=0.5)
        # drive + search: 2/3 = 0.667
        drive_search = [p for p in patterns if "drive" in (p.tool_a, p.tool_b) and "search" in (p.tool_a, p.tool_b)]
        assert len(drive_search) == 1
        assert drive_search[0].co_occurrence_rate >= 0.6

    def test_patterns_insufficient_history(self, tracker: UsageTracker):
        """Need at least 2 sessions for patterns."""
        tracker.record_activation("s1", "drive", AGENT, DEPT)
        tracker.record_call("s1", "drive")
        tracker.learn_session_patterns("s1", AGENT)
        assert tracker.get_patterns(AGENT) == []

    def test_patterns_sorted_by_rate(self, tracker: UsageTracker):
        """Patterns sorted highest co-occurrence first."""
        for i in range(5):
            sid = f"s{i}"
            tracker.record_activation(sid, "a", AGENT, DEPT)
            tracker.record_activation(sid, "b", AGENT, DEPT)
            tracker.record_call(sid, "a")
            tracker.record_call(sid, "b")
            if i < 3:
                tracker.record_activation(sid, "c", AGENT, DEPT)
                tracker.record_call(sid, "c")
            tracker.learn_session_patterns(sid, AGENT)

        patterns = tracker.get_patterns(AGENT, min_co_occurrence=0.5)
        # a+b: 5/5=1.0, a+c: 3/5=0.6, b+c: 3/5=0.6
        assert patterns[0].co_occurrence_rate >= patterns[-1].co_occurrence_rate

    def test_patterns_unknown_agent(self, tracker: UsageTracker):
        assert tracker.get_patterns("unknown-agent") == []


# ── Token Savings Tests ───────────────────────────────────────

class TestTokenSavings:
    def test_baseline_cost_calculation(self, tracker: UsageTracker):
        baseline = tracker.calculate_baseline_cost(
            total_registry_tokens=1000,
            turns=10,
        )
        assert baseline == 10000  # 1000 tokens * 10 turns

    def test_tlm_cost_less_than_baseline(self, active_tracker: UsageTracker):
        per_tool = {"google_drive": 200, "terminal": 150}
        tlm_cost = active_tracker.calculate_tlm_cost(CONV, per_tool)
        baseline = active_tracker.calculate_baseline_cost(1000, 1)
        # TLM cost should be less (only 2 tools loaded vs all)
        assert tlm_cost < baseline


# ── Cleanup Tests ─────────────────────────────────────────────

class TestCleanup:
    def test_clear_conversation(self, active_tracker: UsageTracker):
        active_tracker.clear_conversation(CONV)
        report = active_tracker.get_session_report(CONV)
        assert report.total_tools_used == 0

    def test_clear_all(self, active_tracker: UsageTracker):
        active_tracker.clear_all()
        assert active_tracker.get_session_report(CONV).total_tools_used == 0
