"""Integration tests for Tool Lifecycle Manager -- full pipeline flows.

Tests the complete TLM flow: registry -> session manager -> activation proxy
-> usage tracker -> NBMF bridge, simulating multi-turn conversations with
natural tool churn, governance blocks, predictive activation, and cost savings.
"""

from __future__ import annotations

import pytest
from typing import Any

from app.services.tool_lifecycle.tool_registry import (
    GovernanceRules,
    ToolDefinition,
    ToolRegistry,
)
from app.services.tool_lifecycle.session_manager import SessionManager, ToolStatus
from app.services.tool_lifecycle.activation_proxy import (
    ActivationProxy,
    ToolCall,
)
from app.services.tool_lifecycle.usage_tracker import UsageTracker
from app.services.tool_lifecycle.nbmf_bridge import NBMFBridge


# ── Helpers ───────────────────────────────────────────────────

def _tool(
    tid: str,
    category: str = "general",
    departments: list[str] | None = None,
    requires_approval: bool = False,
    tokens: int = 200,
) -> ToolDefinition:
    return ToolDefinition(
        id=tid,
        name=tid.replace("_", " ").title(),
        category=category,
        light_description=f"A {tid} tool",
        full_schema={"type": "function", "name": tid, "params": {}},
        governance_rules=GovernanceRules(
            allowed_departments=departments or [],
            requires_approval=requires_approval,
        ),
        estimated_schema_tokens=tokens,
    )


async def _mock_executor(tool_id: str, params: dict[str, Any]) -> dict[str, Any]:
    """Simple mock executor that returns success."""
    return {"status": "completed", "tool": tool_id, "output": f"Result from {tool_id}"}


async def _flaky_executor(tool_id: str, params: dict[str, Any]) -> dict[str, Any]:
    """Executor that fails for terminal commands with 'rm' in them."""
    if tool_id == "terminal" and "rm" in str(params.get("command", "")):
        raise PermissionError("Blocked: destructive command")
    return {"status": "completed", "tool": tool_id}


CONV = "conv-integration-001"
DEPT = "engineering"


@pytest.fixture
def full_system():
    """Complete TLM system with 10 tools registered."""
    registry = ToolRegistry()
    registry.register_tool(_tool("google_drive", "storage", tokens=200))
    registry.register_tool(_tool("terminal", "code", departments=["engineering", "security"], tokens=150))
    registry.register_tool(_tool("web_search", "search", tokens=250))
    registry.register_tool(_tool("slack", "comms", tokens=100))
    registry.register_tool(_tool("canva", "design", departments=["marketing", "product"], tokens=300))
    registry.register_tool(_tool("github", "code", departments=["engineering"], tokens=350))
    registry.register_tool(_tool("jira", "project", tokens=180))
    registry.register_tool(_tool("calendar", "productivity", tokens=120))
    registry.register_tool(_tool("email", "comms", tokens=160))
    registry.register_tool(_tool("spreadsheet", "finance", departments=["finance", "operations"], tokens=220))

    sm = SessionManager(
        idle_turns_before_cooldown=2,
        idle_turns_before_deactivate=4,
        max_active_tools=5,
    )
    proxy = ActivationProxy(registry, sm)
    tracker = UsageTracker()
    bridge = NBMFBridge()

    return {
        "registry": registry,
        "sm": sm,
        "proxy": proxy,
        "tracker": tracker,
        "bridge": bridge,
    }


# ── Full Pipeline Flow ────────────────────────────────────────

class TestFullPipelineFlow:
    @pytest.mark.asyncio
    async def test_message_to_execute_to_deactivate(self, full_system):
        """Complete flow: tool call -> activate -> execute -> track -> deactivate."""
        proxy = full_system["proxy"]
        sm = full_system["sm"]
        tracker = full_system["tracker"]

        # Turn 1: User asks to search files
        result = await proxy.intercept_and_execute(
            tool_calls=[ToolCall("google_drive", {"query": "budget Q4"})],
            conversation_id=CONV,
            department=DEPT,
            executor=_mock_executor,
        )

        # Verify activation
        assert "google_drive" in result.activated
        assert result.executed[0].success
        assert sm.is_tool_active("google_drive", CONV)

        # Track it
        tracker.record_activation(CONV, "google_drive", "agent-1", DEPT)
        tracker.record_call(CONV, "google_drive")
        tracker.record_turn_snapshot(CONV, 1)

        # Turn 2-5: No tool calls (idle)
        for _ in range(4):
            sm.tick_turn(CONV)

        # google_drive should be deactivated after 4 idle turns
        assert not sm.is_tool_active("google_drive", CONV)

    @pytest.mark.asyncio
    async def test_mid_conversation_tool_shift(self, full_system):
        """Research -> design -> code: tools shift as conversation evolves."""
        proxy = full_system["proxy"]

        # Phase 1: Research (turn 1)
        r1 = await proxy.intercept_and_execute(
            tool_calls=[
                ToolCall("web_search", {"query": "competitor analysis"}),
                ToolCall("google_drive", {"query": "market data"}),
            ],
            conversation_id=CONV,
            department=DEPT,
            executor=_mock_executor,
        )
        assert len(r1.activated) == 2

        # Phase 2: Code (turn 2) - search still active, add terminal + github
        r2 = await proxy.intercept_and_execute(
            tool_calls=[
                ToolCall("terminal", {"command": "git status"}),
                ToolCall("github", {"action": "create_pr"}),
            ],
            conversation_id=CONV,
            department=DEPT,
            executor=_mock_executor,
        )
        assert "terminal" in r2.activated
        assert "github" in r2.activated

        # Phase 3: Communication (turn 3) - notify team
        r3 = await proxy.intercept_and_execute(
            tool_calls=[ToolCall("slack", {"message": "PR ready for review"})],
            conversation_id=CONV,
            department=DEPT,
            executor=_mock_executor,
        )
        assert "slack" in r3.activated

        # At this point: 5 tools active (drive, search, terminal, github, slack)
        # That's the max. web_search and google_drive are idle.

    @pytest.mark.asyncio
    async def test_governance_blocks_mid_conversation(self, full_system):
        """Engineering agent tries to use marketing-only tool mid-conversation."""
        proxy = full_system["proxy"]

        # Allowed tools
        r1 = await proxy.intercept_and_execute(
            tool_calls=[ToolCall("terminal", {})],
            conversation_id=CONV,
            department=DEPT,
            executor=_mock_executor,
        )
        assert r1.executed[0].success

        # Blocked: canva is marketing/product only
        r2 = await proxy.intercept_and_execute(
            tool_calls=[
                ToolCall("terminal", {"command": "build"}),
                ToolCall("canva", {"design": "logo"}),  # blocked!
            ],
            conversation_id=CONV,
            department=DEPT,
            executor=_mock_executor,
        )
        assert len(r2.executed) == 1  # only terminal
        assert len(r2.blocked) == 1
        assert r2.blocked[0].tool_id == "canva"


class TestNBMFPreWarming:
    @pytest.mark.asyncio
    async def test_nbmf_learns_and_predicts_after_sessions(self, full_system):
        """After 3 similar sessions, NBMF should predict tools."""
        bridge = full_system["bridge"]

        # Session 1
        bridge.learn_from_session(
            "s1", "agent-eng", "engineering",
            tool_sequence=["terminal", "github", "slack"],
            tool_call_counts={"terminal": 5, "github": 3, "slack": 1},
        )

        # Session 2
        bridge.learn_from_session(
            "s2", "agent-eng", "engineering",
            tool_sequence=["terminal", "github", "web_search"],
            tool_call_counts={"terminal": 4, "github": 2, "web_search": 3},
        )

        # Session 3
        bridge.learn_from_session(
            "s3", "agent-eng", "engineering",
            tool_sequence=["terminal", "github"],
            tool_call_counts={"terminal": 6, "github": 4},
        )

        # Predict for new session: agent always starts with terminal
        predictions = bridge.predict_next_tools(
            "new-conv", "agent-eng", "engineering",
            current_tools=[],
        )
        predicted_ids = [p.tool_id for p in predictions]
        # terminal (15 calls) and github (9 calls) should be top predictions
        assert "terminal" in predicted_ids
        assert "github" in predicted_ids

    @pytest.mark.asyncio
    async def test_prewarm_suggestions_match_history(self, full_system):
        bridge = full_system["bridge"]
        bridge.learn_from_session(
            "s1", "agent-fin", "finance",
            tool_sequence=["spreadsheet", "email"],
            tool_call_counts={"spreadsheet": 10, "email": 2},
        )
        suggestions = bridge.get_prewarm_suggestions("agent-fin")
        assert suggestions[0] == "spreadsheet"  # highest call count


class TestCostReport:
    @pytest.mark.asyncio
    async def test_cost_report_shows_real_savings(self, full_system):
        """Cost report should show tokens saved vs baseline (all tools loaded)."""
        proxy = full_system["proxy"]
        registry = full_system["registry"]
        tracker = full_system["tracker"]

        # 3-turn conversation using only 2 tools
        for _ in range(3):
            result = await proxy.intercept_and_execute(
                tool_calls=[ToolCall("terminal", {})],
                conversation_id=CONV,
                department=DEPT,
                executor=_mock_executor,
            )
            tracker.record_activation(CONV, "terminal", "agent-1", DEPT)
            tracker.record_call(CONV, "terminal", tokens_saved=result.cost_savings.tokens_not_loaded)
            tracker.record_turn_snapshot(CONV, 1)

        report = tracker.get_session_report(CONV)
        assert report.total_calls == 3
        assert report.total_tokens_saved > 0

        # Baseline: all 10 tools * 3 turns
        total_tokens = registry.get_total_schema_tokens()
        baseline = tracker.calculate_baseline_cost(total_tokens, 3)
        assert report.total_tokens_saved < baseline  # savings < total baseline


class TestTenTurnConversation:
    @pytest.mark.asyncio
    async def test_10_turn_natural_tool_churn(self, full_system):
        """Simulate a realistic 10-turn conversation with tool churn."""
        proxy = full_system["proxy"]
        sm = full_system["sm"]
        tracker = full_system["tracker"]

        # Turn 1: Research phase
        await proxy.intercept_and_execute(
            tool_calls=[
                ToolCall("web_search", {"query": "react performance"}),
                ToolCall("google_drive", {"query": "project specs"}),
            ],
            conversation_id=CONV, department=DEPT, executor=_mock_executor,
        )
        tracker.record_activation(CONV, "web_search", "a1", DEPT)
        tracker.record_activation(CONV, "google_drive", "a1", DEPT)
        tracker.record_call(CONV, "web_search")
        tracker.record_call(CONV, "google_drive")
        tracker.record_turn_snapshot(CONV, 2)

        # Turn 2: Still researching
        await proxy.intercept_and_execute(
            tool_calls=[ToolCall("web_search", {"query": "react hooks best practices"})],
            conversation_id=CONV, department=DEPT, executor=_mock_executor,
        )
        tracker.record_call(CONV, "web_search")
        tracker.record_turn_snapshot(CONV, 2)

        # Turn 3: Transition to coding
        await proxy.intercept_and_execute(
            tool_calls=[
                ToolCall("terminal", {"command": "npm init"}),
                ToolCall("github", {"action": "clone"}),
            ],
            conversation_id=CONV, department=DEPT, executor=_mock_executor,
        )
        tracker.record_activation(CONV, "terminal", "a1", DEPT)
        tracker.record_activation(CONV, "github", "a1", DEPT)
        tracker.record_call(CONV, "terminal")
        tracker.record_call(CONV, "github")
        tracker.record_turn_snapshot(CONV, 4)

        # Turn 4-6: Pure coding (search/drive go idle)
        for _ in range(3):
            await proxy.intercept_and_execute(
                tool_calls=[ToolCall("terminal", {"command": "npm test"})],
                conversation_id=CONV, department=DEPT, executor=_mock_executor,
            )
            tracker.record_call(CONV, "terminal")
            active = sm.get_active_tools(CONV)
            tracker.record_turn_snapshot(CONV, len(active))

        # Turn 7: Communication (search/drive should be cooling or deactivated by now)
        await proxy.intercept_and_execute(
            tool_calls=[ToolCall("slack", {"message": "code review needed"})],
            conversation_id=CONV, department=DEPT, executor=_mock_executor,
        )
        tracker.record_activation(CONV, "slack", "a1", DEPT)
        tracker.record_call(CONV, "slack")
        active = sm.get_active_tools(CONV)
        tracker.record_turn_snapshot(CONV, len(active))

        # Turn 8-10: Wrap up
        for _ in range(3):
            await proxy.intercept_and_execute(
                tool_calls=[ToolCall("terminal", {"command": "git push"})],
                conversation_id=CONV, department=DEPT, executor=_mock_executor,
            )
            tracker.record_call(CONV, "terminal")
            active = sm.get_active_tools(CONV)
            tracker.record_turn_snapshot(CONV, len(active))

        # Final report
        report = tracker.get_session_report(CONV)
        assert report.total_tools_used >= 4  # at least drive, search, terminal, github, slack
        assert report.total_calls >= 10
        assert report.avg_tools_active_per_turn > 0
        assert report.avg_tools_active_per_turn < 5  # not all tools active every turn


class TestAutoActivateUnknownTool:
    @pytest.mark.asyncio
    async def test_agent_requests_unknown_tool_errors(self, full_system):
        """Agent requests a tool that doesn't exist -> error, not crash."""
        proxy = full_system["proxy"]
        result = await proxy.intercept_and_execute(
            tool_calls=[ToolCall("photoshop", {"action": "edit"})],
            conversation_id=CONV,
            department=DEPT,
            executor=_mock_executor,
        )
        assert len(result.errors) == 1
        assert "not registered" in result.errors[0]

    @pytest.mark.asyncio
    async def test_agent_requests_tool_it_doesnt_have_auto_activates(self, full_system):
        """Registered but not-yet-active tool auto-activates on demand."""
        proxy = full_system["proxy"]
        sm = full_system["sm"]

        assert not sm.is_tool_active("jira", CONV)
        result = await proxy.intercept_and_execute(
            tool_calls=[ToolCall("jira", {"action": "create_ticket"})],
            conversation_id=CONV,
            department=DEPT,
            executor=_mock_executor,
        )
        assert "jira" in result.activated
        assert result.executed[0].success
        assert sm.is_tool_active("jira", CONV)


class TestMaxActiveEviction:
    @pytest.mark.asyncio
    async def test_eviction_during_complex_workflow(self, full_system):
        """When max tools reached, oldest idle gets evicted."""
        proxy = full_system["proxy"]
        sm = full_system["sm"]

        # Activate 5 tools (the max)
        tools = ["terminal", "github", "web_search", "google_drive", "slack"]
        await proxy.intercept_and_execute(
            tool_calls=[ToolCall(t, {}) for t in tools],
            conversation_id=CONV,
            department=DEPT,
            executor=_mock_executor,
        )
        assert len(sm.get_active_tools(CONV)) <= 5

        # Use only terminal and github for the next turn
        sm.record_use("terminal", CONV)
        sm.record_use("github", CONV)

        # Now request a 6th tool -> should evict one of the idle ones
        result = await proxy.intercept_and_execute(
            tool_calls=[ToolCall("jira", {})],
            conversation_id=CONV,
            department=DEPT,
            executor=_mock_executor,
        )
        assert "jira" in result.activated
        active = sm.get_active_tools(CONV)
        assert len(active) <= 5


class TestExecutionWithGovernanceAndErrors:
    @pytest.mark.asyncio
    async def test_flaky_executor_partial_success(self, full_system):
        """Some tool calls succeed, some fail due to execution errors."""
        proxy = full_system["proxy"]

        result = await proxy.intercept_and_execute(
            tool_calls=[
                ToolCall("terminal", {"command": "git status"}),  # succeeds
                ToolCall("terminal", {"command": "rm -rf /"}),     # fails (flaky executor)
            ],
            conversation_id=CONV,
            department=DEPT,
            executor=_flaky_executor,
        )
        assert len(result.executed) == 2
        assert result.executed[0].success
        assert not result.executed[1].success
        assert "destructive command" in result.executed[1].error


class TestEndToEndWithNBMF:
    @pytest.mark.asyncio
    async def test_full_session_with_learning(self, full_system):
        """Complete session: execute tools -> generate report -> learn -> predict."""
        proxy = full_system["proxy"]
        tracker = full_system["tracker"]
        bridge = full_system["bridge"]

        # Execute some tools
        await proxy.intercept_and_execute(
            tool_calls=[
                ToolCall("terminal", {}),
                ToolCall("github", {}),
            ],
            conversation_id=CONV,
            department=DEPT,
            executor=_mock_executor,
        )
        tracker.record_activation(CONV, "terminal", "agent-1", DEPT)
        tracker.record_activation(CONV, "github", "agent-1", DEPT)
        tracker.record_call(CONV, "terminal")
        tracker.record_call(CONV, "github")
        tracker.record_turn_snapshot(CONV, 2)

        # Generate report
        report = tracker.get_session_report(CONV)
        assert report.total_calls == 2

        # Learn from session
        bridge.learn_from_session(
            CONV, "agent-1", DEPT,
            tool_sequence=["terminal", "github"],
            tool_call_counts={"terminal": 1, "github": 1},
        )

        # Run a second session with same pattern
        bridge.learn_from_session(
            "conv-2", "agent-1", DEPT,
            tool_sequence=["terminal", "github", "slack"],
            tool_call_counts={"terminal": 3, "github": 2, "slack": 1},
        )

        # Predict for new session
        predictions = bridge.predict_next_tools(
            "conv-3", "agent-1", DEPT,
            current_tools=[],
        )
        predicted_ids = [p.tool_id for p in predictions]
        assert "terminal" in predicted_ids  # most used
