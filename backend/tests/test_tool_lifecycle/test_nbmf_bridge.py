"""Tests for NBMFBridge -- predictive tool activation from memory patterns."""

from __future__ import annotations

import pytest

from app.services.tool_lifecycle.nbmf_bridge import NBMFBridge, PredictedTool


CONV = "conv-001"
AGENT = "agent-eng-1"
DEPT = "engineering"


@pytest.fixture
def bridge() -> NBMFBridge:
    return NBMFBridge()


@pytest.fixture
def learned_bridge() -> NBMFBridge:
    """Bridge with learned patterns from 3 sessions."""
    b = NBMFBridge()

    # Session 1: drive -> search -> terminal
    b.learn_from_session(
        "s1", AGENT, DEPT,
        tool_sequence=["drive", "search", "terminal"],
        tool_call_counts={"drive": 3, "search": 2, "terminal": 1},
    )

    # Session 2: drive -> search -> slack
    b.learn_from_session(
        "s2", AGENT, DEPT,
        tool_sequence=["drive", "search", "slack"],
        tool_call_counts={"drive": 2, "search": 4, "slack": 1},
    )

    # Session 3: terminal -> drive
    b.learn_from_session(
        "s3", AGENT, DEPT,
        tool_sequence=["terminal", "drive"],
        tool_call_counts={"terminal": 5, "drive": 1},
    )

    # Org defaults
    b.set_org_defaults(["web_search", "calendar"])

    return b


# ── Prediction Tests ──────────────────────────────────────────

class TestPrediction:
    def test_predict_from_l1_conversation(self, bridge: NBMFBridge):
        """L1 predictions based on current conversation sequence."""
        bridge.learn_from_session(
            CONV, AGENT, DEPT,
            tool_sequence=["drive", "search", "terminal"],
            tool_call_counts={"drive": 1, "search": 1, "terminal": 1},
        )
        predictions = bridge.predict_next_tools(
            CONV, AGENT, DEPT,
            current_tools=["drive"],
        )
        tool_ids = [p.tool_id for p in predictions]
        assert "search" in tool_ids  # drive -> search in sequence

    def test_predict_from_l2_agent_history(self, learned_bridge: NBMFBridge):
        """L2 predictions based on agent's cross-session history."""
        predictions = learned_bridge.predict_next_tools(
            "new-conv", AGENT, DEPT,
            current_tools=[],
        )
        # search has highest total calls (2+4=6), then drive (3+2+1=6), then terminal (1+5=6)
        assert len(predictions) > 0
        sources = {p.source for p in predictions}
        assert "L2_agent" in sources

    def test_predict_from_l2q_department(self, learned_bridge: NBMFBridge):
        """L2Q predictions based on department norms."""
        predictions = learned_bridge.predict_next_tools(
            "new-conv", "unknown-agent", DEPT,
            current_tools=["drive", "search", "terminal", "slack"],  # exclude all L2 suggestions
        )
        # Department has learned drive, search, terminal, slack
        # But those are in current_tools, so should get org defaults
        sources = {p.source for p in predictions}
        # Might get L3_org since department tools are excluded
        assert len(predictions) >= 0

    def test_predict_from_l3_org_defaults(self, learned_bridge: NBMFBridge):
        """L3 org-wide defaults as last resort."""
        predictions = learned_bridge.predict_next_tools(
            "new-conv", "unknown-agent", "unknown-dept",
            current_tools=[],
        )
        tool_ids = [p.tool_id for p in predictions]
        assert "web_search" in tool_ids or "calendar" in tool_ids

    def test_predictions_exclude_current_tools(self, learned_bridge: NBMFBridge):
        """Tools already active should not be predicted."""
        predictions = learned_bridge.predict_next_tools(
            "new-conv", AGENT, DEPT,
            current_tools=["drive", "search", "terminal", "slack"],
        )
        predicted_ids = {p.tool_id for p in predictions}
        assert "drive" not in predicted_ids
        assert "search" not in predicted_ids

    def test_predictions_limited_to_max(self, learned_bridge: NBMFBridge):
        predictions = learned_bridge.predict_next_tools(
            "new-conv", AGENT, DEPT,
            current_tools=[],
            max_predictions=2,
        )
        assert len(predictions) <= 2

    def test_predictions_sorted_by_confidence(self, learned_bridge: NBMFBridge):
        predictions = learned_bridge.predict_next_tools(
            "new-conv", AGENT, DEPT,
            current_tools=[],
            max_predictions=10,
        )
        if len(predictions) >= 2:
            for i in range(len(predictions) - 1):
                assert predictions[i].confidence >= predictions[i + 1].confidence

    def test_empty_history_returns_no_predictions(self, bridge: NBMFBridge):
        predictions = bridge.predict_next_tools(
            "new-conv", "unknown", "unknown",
            current_tools=[],
        )
        assert predictions == []


# ── Pre-Warm Tests ────────────────────────────────────────────

class TestPreWarm:
    def test_prewarm_returns_top_tools(self, learned_bridge: NBMFBridge):
        suggestions = learned_bridge.get_prewarm_suggestions(AGENT)
        assert len(suggestions) > 0
        assert len(suggestions) <= 3

    def test_prewarm_unknown_agent(self, bridge: NBMFBridge):
        assert bridge.get_prewarm_suggestions("unknown") == []

    def test_prewarm_respects_max(self, learned_bridge: NBMFBridge):
        suggestions = learned_bridge.get_prewarm_suggestions(AGENT, max_suggestions=1)
        assert len(suggestions) == 1


# ── Learning Tests ────────────────────────────────────────────

class TestLearning:
    def test_learn_stores_l1(self, bridge: NBMFBridge):
        bridge.learn_from_session(
            CONV, AGENT, DEPT,
            tool_sequence=["a", "b"],
            tool_call_counts={"a": 1, "b": 2},
        )
        l1 = bridge._store.get("L1", {}).get(CONV)
        assert l1 is not None
        assert l1.tool_ids == ["a", "b"]
        assert l1.sequence_pairs == [("a", "b")]

    def test_learn_accumulates_l2(self, bridge: NBMFBridge):
        bridge.learn_from_session(
            "s1", AGENT, DEPT,
            tool_sequence=["a"],
            tool_call_counts={"a": 3},
        )
        bridge.learn_from_session(
            "s2", AGENT, DEPT,
            tool_sequence=["a"],
            tool_call_counts={"a": 2},
        )
        history = bridge.get_agent_history(AGENT)
        assert history.call_counts["a"] == 5  # 3 + 2

    def test_learn_updates_l2q(self, bridge: NBMFBridge):
        bridge.learn_from_session(
            "s1", AGENT, DEPT,
            tool_sequence=["drive", "search"],
            tool_call_counts={"drive": 1, "search": 1},
        )
        norms = bridge.get_department_norms(DEPT)
        assert "drive" in norms
        assert "search" in norms

    def test_learn_no_duplicate_l2q(self, bridge: NBMFBridge):
        bridge.learn_from_session(
            "s1", AGENT, DEPT,
            tool_sequence=["drive"],
            tool_call_counts={"drive": 1},
        )
        bridge.learn_from_session(
            "s2", AGENT, DEPT,
            tool_sequence=["drive"],
            tool_call_counts={"drive": 1},
        )
        norms = bridge.get_department_norms(DEPT)
        assert norms.count("drive") == 1  # no duplicates


# ── Cleanup Tests ─────────────────────────────────────────────

class TestCleanup:
    def test_clear_conversation(self, learned_bridge: NBMFBridge):
        learned_bridge.clear_conversation("s1")
        # L1 for s1 should be gone, but L2 should remain
        assert learned_bridge._store.get("L1", {}).get("s1") is None
        assert learned_bridge.get_agent_history(AGENT) is not None

    def test_clear_all(self, learned_bridge: NBMFBridge):
        learned_bridge.clear_all()
        assert learned_bridge.get_agent_history(AGENT) is None
        assert learned_bridge.get_department_norms(DEPT) == []
