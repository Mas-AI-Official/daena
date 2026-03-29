"""Tests for Orchestra Integration -- TLM wired into chat pipeline."""

from __future__ import annotations

import pytest

from app.services.tool_lifecycle.orchestra_integration import (
    finalize_session,
    get_tlm_bridge,
    get_tlm_proxy,
    get_tlm_registry,
    get_tlm_session_manager,
    get_tlm_tracker,
    get_tool_context_for_llm,
    initialize_tlm,
    record_tool_execution,
    reset_tlm,
    tick_conversation_turn,
)


CONV = "conv-orch-001"
AGENT = "agent-eng-1"
DEPT = "engineering"


@pytest.fixture(autouse=True)
def _clean_tlm():
    """Reset TLM state before each test."""
    reset_tlm()
    yield
    reset_tlm()


# ── Singleton Tests ───────────────────────────────────────────

class TestSingletons:
    def test_registry_is_singleton(self):
        r1 = get_tlm_registry()
        r2 = get_tlm_registry()
        assert r1 is r2

    def test_session_manager_is_singleton(self):
        s1 = get_tlm_session_manager()
        s2 = get_tlm_session_manager()
        assert s1 is s2

    def test_proxy_is_singleton(self):
        p1 = get_tlm_proxy()
        p2 = get_tlm_proxy()
        assert p1 is p2

    def test_tracker_is_singleton(self):
        t1 = get_tlm_tracker()
        t2 = get_tlm_tracker()
        assert t1 is t2

    def test_bridge_is_singleton(self):
        b1 = get_tlm_bridge()
        b2 = get_tlm_bridge()
        assert b1 is b2


# ── Initialization Tests ─────────────────────────────────────

class TestInitialization:
    def test_initialize_registers_builtin_tools(self):
        initialize_tlm()
        registry = get_tlm_registry()
        assert registry.count >= 10  # file(6) + terminal(1) + browser(3)

    def test_initialize_idempotent(self):
        initialize_tlm()
        count1 = get_tlm_registry().count
        initialize_tlm()
        count2 = get_tlm_registry().count
        assert count1 == count2

    def test_builtin_tools_have_correct_categories(self):
        initialize_tlm()
        registry = get_tlm_registry()
        file_tools = registry.get_tools_by_category("file")
        assert len(file_tools) >= 5
        terminal_tools = registry.get_tools_by_category("terminal")
        assert len(terminal_tools) >= 1
        browser_tools = registry.get_tools_by_category("browser")
        assert len(browser_tools) >= 3

    def test_delete_file_requires_approval(self):
        initialize_tlm()
        registry = get_tlm_registry()
        assert registry.requires_approval("file.delete_file")

    def test_read_file_does_not_require_approval(self):
        initialize_tlm()
        registry = get_tlm_registry()
        assert not registry.requires_approval("file.read_file")


# ── Pipeline Helper Tests ─────────────────────────────────────

class TestPipelineHelpers:
    def test_get_tool_context_for_llm(self):
        initialize_tlm()
        ctx = get_tool_context_for_llm(CONV)
        assert "catalog" in ctx
        assert "active_schemas" in ctx
        assert len(ctx["catalog"]) >= 10

    def test_record_tool_execution(self):
        initialize_tlm()
        record_tool_execution(CONV, "file.read_file", AGENT, DEPT)
        tracker = get_tlm_tracker()
        stats = tracker.get_tool_stats(CONV, "file.read_file")
        assert stats is not None
        assert stats.call_count == 1

    def test_record_tool_execution_with_error(self):
        initialize_tlm()
        record_tool_execution(CONV, "terminal.execute_command", AGENT, DEPT, success=False)
        tracker = get_tlm_tracker()
        stats = tracker.get_tool_stats(CONV, "terminal.execute_command")
        assert stats.errors == 1

    def test_tick_conversation_turn(self):
        initialize_tlm()
        sm = get_tlm_session_manager()
        sm.activate_tool("file.read_file", CONV)

        result = tick_conversation_turn(CONV)
        assert "active_count" in result
        assert "cooled" in result
        assert "deactivated" in result

    def test_tick_advances_idle_counter(self):
        initialize_tlm()
        sm = get_tlm_session_manager()
        sm.activate_tool("file.read_file", CONV)

        tick_conversation_turn(CONV)
        session = sm.get_tool_session("file.read_file", CONV)
        assert session.turns_since_last_use == 1


# ── Session Finalization Tests ────────────────────────────────

class TestSessionFinalization:
    def test_finalize_generates_report(self):
        initialize_tlm()
        record_tool_execution(CONV, "file.read_file", AGENT, DEPT)
        record_tool_execution(CONV, "terminal.execute_command", AGENT, DEPT)

        result = finalize_session(CONV, AGENT, DEPT)
        assert result["total_tools_used"] == 2
        assert result["total_calls"] == 2

    def test_finalize_learns_patterns(self):
        initialize_tlm()
        record_tool_execution(CONV, "file.read_file", AGENT, DEPT)
        record_tool_execution(CONV, "terminal.execute_command", AGENT, DEPT)

        finalize_session(CONV, AGENT, DEPT)

        bridge = get_tlm_bridge()
        history = bridge.get_agent_history(AGENT)
        assert history is not None
        assert "file.read_file" in history.tool_ids

    def test_finalize_cleans_up_session(self):
        initialize_tlm()
        sm = get_tlm_session_manager()
        sm.activate_tool("file.read_file", CONV)

        finalize_session(CONV, AGENT, DEPT)
        assert sm.get_active_tools(CONV) == []

    def test_finalize_empty_session(self):
        initialize_tlm()
        result = finalize_session(CONV, AGENT, DEPT)
        assert result["total_tools_used"] == 0
        assert result["total_calls"] == 0


# ── Reset Tests ───────────────────────────────────────────────

class TestReset:
    def test_reset_clears_all_state(self):
        initialize_tlm()
        record_tool_execution(CONV, "file.read_file", AGENT, DEPT)
        reset_tlm()

        # After reset, new instances should be fresh
        assert get_tlm_registry().count == 0
        tracker = get_tlm_tracker()
        assert tracker.get_session_report(CONV).total_tools_used == 0
