"""Tests for SessionManager -- tool activation lifecycle per conversation."""

from __future__ import annotations

import threading
import pytest

from app.services.tool_lifecycle.session_manager import (
    DeactivationReport,
    SessionManager,
    ToolSession,
    ToolStatus,
)


@pytest.fixture
def sm() -> SessionManager:
    """Default session manager: cooldown=3, deactivate=5, max=8."""
    return SessionManager()


@pytest.fixture
def sm_tight() -> SessionManager:
    """Tight thresholds for testing: cooldown=1, deactivate=2, max=3."""
    return SessionManager(
        idle_turns_before_cooldown=1,
        idle_turns_before_deactivate=2,
        max_active_tools=3,
    )


CONV = "conv-001"


# ── Activation Tests ──────────────────────────────────────────

class TestActivation:
    def test_activate_new_tool(self, sm: SessionManager):
        session = sm.activate_tool("google_drive", CONV)
        assert isinstance(session, ToolSession)
        assert session.status == ToolStatus.ACTIVE
        assert session.tool_id == "google_drive"
        assert session.session_id == CONV

    def test_activate_returns_existing_if_active(self, sm: SessionManager):
        s1 = sm.activate_tool("drive", CONV)
        s2 = sm.activate_tool("drive", CONV)
        assert s1 is s2

    def test_activate_multiple_tools(self, sm: SessionManager):
        sm.activate_tool("drive", CONV)
        sm.activate_tool("slack", CONV)
        sm.activate_tool("terminal", CONV)
        active = sm.get_active_tools(CONV)
        assert len(active) == 3

    def test_activate_with_connection_handle(self, sm: SessionManager):
        handle = {"client": "mock_mcp_client"}
        session = sm.activate_tool("drive", CONV, connection_handle=handle)
        assert session.connection_handle is handle


# ── Deactivation Tests ────────────────────────────────────────

class TestDeactivation:
    def test_deactivate_active_tool(self, sm: SessionManager):
        sm.activate_tool("drive", CONV)
        result = sm.deactivate_tool("drive", CONV)
        assert result is True
        assert not sm.is_tool_active("drive", CONV)

    def test_deactivate_clears_handle(self, sm: SessionManager):
        sm.activate_tool("drive", CONV, connection_handle="conn")
        sm.deactivate_tool("drive", CONV)
        session = sm.get_tool_session("drive", CONV)
        assert session.connection_handle is None

    def test_deactivate_nonexistent_returns_false(self, sm: SessionManager):
        assert sm.deactivate_tool("nonexistent", CONV) is False

    def test_deactivate_already_deactivated(self, sm: SessionManager):
        sm.activate_tool("drive", CONV)
        sm.deactivate_tool("drive", CONV)
        assert sm.deactivate_tool("drive", CONV) is False

    def test_deactivate_no_conversation(self, sm: SessionManager):
        assert sm.deactivate_tool("drive", "nonexistent-conv") is False


# ── Reactivation Tests ────────────────────────────────────────

class TestReactivation:
    def test_reactivate_after_deactivation(self, sm: SessionManager):
        sm.activate_tool("drive", CONV)
        sm.deactivate_tool("drive", CONV)
        session = sm.activate_tool("drive", CONV)
        assert session.status == ToolStatus.ACTIVE
        assert session.turns_since_last_use == 0

    def test_reactivate_cooling_tool(self, sm_tight: SessionManager):
        sm_tight.activate_tool("drive", CONV)
        sm_tight.tick_turn(CONV)  # turns_since_last_use = 1 -> cooling
        session = sm_tight.get_tool_session("drive", CONV)
        assert session.status == ToolStatus.COOLING

        # Reactivate
        session = sm_tight.activate_tool("drive", CONV)
        assert session.status == ToolStatus.ACTIVE
        assert session.turns_since_last_use == 0


# ── Turn Counting Tests ───────────────────────────────────────

class TestTickTurn:
    def test_tick_increments_counters(self, sm: SessionManager):
        sm.activate_tool("drive", CONV)
        sm.tick_turn(CONV)
        session = sm.get_tool_session("drive", CONV)
        assert session.turns_since_last_use == 1

    def test_tick_multiple_turns(self, sm: SessionManager):
        sm.activate_tool("drive", CONV)
        for _ in range(3):
            sm.tick_turn(CONV)
        session = sm.get_tool_session("drive", CONV)
        assert session.turns_since_last_use == 3

    def test_tool_enters_cooling_after_threshold(self, sm_tight: SessionManager):
        sm_tight.activate_tool("drive", CONV)
        report = sm_tight.tick_turn(CONV)
        assert "drive" in report.cooled
        session = sm_tight.get_tool_session("drive", CONV)
        assert session.status == ToolStatus.COOLING

    def test_tool_deactivated_after_threshold(self, sm_tight: SessionManager):
        sm_tight.activate_tool("drive", CONV)
        sm_tight.tick_turn(CONV)  # turn 1: cooling
        report = sm_tight.tick_turn(CONV)  # turn 2: deactivated
        assert "drive" in report.deactivated
        assert not sm_tight.is_tool_active("drive", CONV)

    def test_tick_returns_report(self, sm: SessionManager):
        sm.activate_tool("drive", CONV)
        report = sm.tick_turn(CONV)
        assert isinstance(report, DeactivationReport)

    def test_tick_empty_conversation(self, sm: SessionManager):
        report = sm.tick_turn("nonexistent")
        assert report.cooled == []
        assert report.deactivated == []

    def test_record_use_resets_counter(self, sm: SessionManager):
        sm.activate_tool("drive", CONV)
        sm.tick_turn(CONV)
        sm.tick_turn(CONV)
        sm.record_use("drive", CONV)
        session = sm.get_tool_session("drive", CONV)
        assert session.turns_since_last_use == 0

    def test_record_use_increments_call_count(self, sm: SessionManager):
        sm.activate_tool("drive", CONV)
        sm.record_use("drive", CONV)
        sm.record_use("drive", CONV)
        session = sm.get_tool_session("drive", CONV)
        assert session.call_count == 2

    def test_record_use_reactivates_cooling_tool(self, sm_tight: SessionManager):
        sm_tight.activate_tool("drive", CONV)
        sm_tight.tick_turn(CONV)  # cooling
        sm_tight.record_use("drive", CONV)
        session = sm_tight.get_tool_session("drive", CONV)
        assert session.status == ToolStatus.ACTIVE

    def test_used_tool_not_deactivated(self, sm_tight: SessionManager):
        """Tool that is used every turn should never be deactivated."""
        sm_tight.activate_tool("drive", CONV)
        for _ in range(10):
            sm_tight.record_use("drive", CONV)
            report = sm_tight.tick_turn(CONV)
            assert "drive" not in report.deactivated
        assert sm_tight.is_tool_active("drive", CONV)


# ── Max Active Cap Tests ──────────────────────────────────────

class TestMaxActiveCap:
    def test_cap_enforced(self, sm_tight: SessionManager):
        """When at max (3), activating a 4th evicts the oldest idle."""
        sm_tight.activate_tool("a", CONV)
        sm_tight.activate_tool("b", CONV)
        sm_tight.activate_tool("c", CONV)
        # Use "c" so it's not the oldest idle
        sm_tight.record_use("c", CONV)
        sm_tight.tick_turn(CONV)

        # "a" and "b" now have turns_since_last_use=1, "c" has 1 (but was used)
        # Actually "c" was used then ticked, so all have 1
        # Let's use "b" and "c" to make "a" the idle one
        sm_tight.record_use("b", CONV)
        sm_tight.record_use("c", CONV)

        # Now activate a 4th -- should evict "a" (most idle)
        sm_tight.activate_tool("d", CONV)
        active = sm_tight.get_active_tools(CONV)
        active_ids = {s.tool_id for s in active}
        assert "d" in active_ids
        assert len(active) <= 3

    def test_eviction_prefers_cooling_tools(self, sm_tight: SessionManager):
        """Cooling tools should be evicted before active ones."""
        sm_tight.activate_tool("a", CONV)
        sm_tight.activate_tool("b", CONV)
        sm_tight.activate_tool("c", CONV)
        # Tick to put idle tools into cooling
        sm_tight.record_use("b", CONV)
        sm_tight.record_use("c", CONV)
        sm_tight.tick_turn(CONV)  # "a" -> cooling

        session_a = sm_tight.get_tool_session("a", CONV)
        assert session_a.status == ToolStatus.COOLING

        # Activate 4th: should evict "a" (cooling) not "b"/"c" (active but used)
        sm_tight.activate_tool("d", CONV)
        assert not sm_tight.is_tool_active("a", CONV)


# ── Conversation Isolation Tests ──────────────────────────────

class TestIsolation:
    def test_different_conversations_isolated(self, sm: SessionManager):
        sm.activate_tool("drive", "conv-1")
        sm.activate_tool("slack", "conv-2")
        assert sm.is_tool_active("drive", "conv-1")
        assert not sm.is_tool_active("drive", "conv-2")
        assert sm.is_tool_active("slack", "conv-2")
        assert not sm.is_tool_active("slack", "conv-1")

    def test_tick_turn_only_affects_own_conversation(self, sm_tight: SessionManager):
        sm_tight.activate_tool("drive", "conv-1")
        sm_tight.activate_tool("drive", "conv-2")
        sm_tight.tick_turn("conv-1")  # only conv-1 ticked
        s1 = sm_tight.get_tool_session("drive", "conv-1")
        s2 = sm_tight.get_tool_session("drive", "conv-2")
        assert s1.turns_since_last_use == 1
        assert s2.turns_since_last_use == 0

    def test_clear_conversation(self, sm: SessionManager):
        sm.activate_tool("drive", CONV)
        sm.clear_conversation(CONV)
        assert sm.get_active_tools(CONV) == []


# ── Query Tests ───────────────────────────────────────────────

class TestQuery:
    def test_get_active_tools_empty(self, sm: SessionManager):
        assert sm.get_active_tools(CONV) == []

    def test_is_tool_active_false_for_unknown(self, sm: SessionManager):
        assert sm.is_tool_active("drive", CONV) is False

    def test_get_active_cost(self, sm: SessionManager):
        sm.activate_tool("drive", CONV)
        sm.activate_tool("slack", CONV)
        sm.record_use("drive", CONV)
        cost = sm.get_active_cost(CONV)
        assert cost["active_count"] == 2
        assert cost["total_calls"] == 1

    def test_get_tool_session_none(self, sm: SessionManager):
        assert sm.get_tool_session("drive", CONV) is None


# ── Thread Safety Tests ───────────────────────────────────────

class TestThreadSafety:
    def test_concurrent_activation_same_conversation(self, sm: SessionManager):
        """Multiple threads activating different tools in same conversation."""
        errors: list[Exception] = []

        def activate_batch(prefix: str):
            try:
                for i in range(20):
                    sm.activate_tool(f"{prefix}_{i}", CONV)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=activate_batch, args=(f"batch_{b}",))
            for b in range(5)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors

    def test_concurrent_tick_turn(self, sm: SessionManager):
        """Tick turn from multiple threads on different conversations."""
        errors: list[Exception] = []

        for i in range(10):
            sm.activate_tool("drive", f"conv-{i}")

        def tick_batch(start: int):
            try:
                for i in range(start, start + 5):
                    for _ in range(10):
                        sm.tick_turn(f"conv-{i}")
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=tick_batch, args=(0,))
        t2 = threading.Thread(target=tick_batch, args=(5,))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not errors
