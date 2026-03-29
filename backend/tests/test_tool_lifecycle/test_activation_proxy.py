"""Tests for ActivationProxy -- the core TLM interceptor."""

from __future__ import annotations

import pytest
from typing import Any

from app.services.tool_lifecycle.tool_registry import (
    GovernanceRules,
    ToolDefinition,
    ToolRegistry,
)
from app.services.tool_lifecycle.session_manager import SessionManager
from app.services.tool_lifecycle.activation_proxy import (
    ActivationProxy,
    BlockedCall,
    ProxyResult,
    ToolCall,
    ToolCallResult,
)


# ── Helpers ───────────────────────────────────────────────────

def _make_tool(
    tool_id: str,
    category: str = "general",
    departments: list[str] | None = None,
    requires_approval: bool = False,
    tokens: int = 200,
) -> ToolDefinition:
    return ToolDefinition(
        id=tool_id,
        name=tool_id.replace("_", " ").title(),
        category=category,
        light_description=f"A {tool_id} tool",
        full_schema={"type": "function", "name": tool_id},
        governance_rules=GovernanceRules(
            allowed_departments=departments or [],
            requires_approval=requires_approval,
        ),
        estimated_schema_tokens=tokens,
    )


async def _success_executor(tool_id: str, params: dict[str, Any]) -> dict[str, Any]:
    """Mock executor that always succeeds."""
    return {"status": "ok", "tool": tool_id, "params": params}


async def _failing_executor(tool_id: str, params: dict[str, Any]) -> dict[str, Any]:
    """Mock executor that always raises."""
    raise RuntimeError(f"Execution failed for {tool_id}")


async def _selective_executor(tool_id: str, params: dict[str, Any]) -> dict[str, Any]:
    """Mock executor that fails for specific tools."""
    if tool_id == "bad_tool":
        raise RuntimeError("bad_tool always fails")
    return {"status": "ok", "tool": tool_id}


CONV = "conv-001"
DEPT = "engineering"


@pytest.fixture
def registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register_tool(_make_tool("google_drive", "storage", tokens=200))
    reg.register_tool(_make_tool("terminal", "code", departments=["engineering", "security"], tokens=150))
    reg.register_tool(_make_tool("slack", "comms", tokens=100))
    reg.register_tool(_make_tool("canva", "design", departments=["marketing", "product"], tokens=300))
    reg.register_tool(_make_tool("web_search", "search", tokens=250))
    return reg


@pytest.fixture
def sm() -> SessionManager:
    return SessionManager(
        idle_turns_before_cooldown=2,
        idle_turns_before_deactivate=4,
        max_active_tools=8,
    )


@pytest.fixture
def proxy(registry: ToolRegistry, sm: SessionManager) -> ActivationProxy:
    return ActivationProxy(registry, sm)


# ── Pass-Through Tests ────────────────────────────────────────

class TestPassThrough:
    @pytest.mark.asyncio
    async def test_active_tool_passes_through(self, proxy: ActivationProxy, sm: SessionManager):
        """Tool that is already active passes through without re-activation."""
        sm.activate_tool("google_drive", CONV)
        result = await proxy.intercept_and_execute(
            tool_calls=[ToolCall("google_drive", {"query": "budget"})],
            conversation_id=CONV,
            department=DEPT,
            executor=_success_executor,
        )
        assert len(result.executed) == 1
        assert result.executed[0].success
        assert "google_drive" not in result.activated  # was already active

    @pytest.mark.asyncio
    async def test_execution_returns_result(self, proxy: ActivationProxy):
        result = await proxy.intercept_and_execute(
            tool_calls=[ToolCall("terminal", {"command": "ls"})],
            conversation_id=CONV,
            department=DEPT,
            executor=_success_executor,
        )
        assert result.executed[0].result == {
            "status": "ok",
            "tool": "terminal",
            "params": {"command": "ls"},
        }

    @pytest.mark.asyncio
    async def test_latency_tracked(self, proxy: ActivationProxy):
        result = await proxy.intercept_and_execute(
            tool_calls=[ToolCall("terminal", {})],
            conversation_id=CONV,
            department=DEPT,
            executor=_success_executor,
        )
        assert result.executed[0].latency_ms >= 0


# ── Auto-Activation Tests ────────────────────────────────────

class TestAutoActivation:
    @pytest.mark.asyncio
    async def test_inactive_tool_auto_activated(self, proxy: ActivationProxy, sm: SessionManager):
        """Registered but inactive tool is activated on first call."""
        assert not sm.is_tool_active("google_drive", CONV)
        result = await proxy.intercept_and_execute(
            tool_calls=[ToolCall("google_drive", {})],
            conversation_id=CONV,
            department=DEPT,
            executor=_success_executor,
        )
        assert "google_drive" in result.activated
        assert sm.is_tool_active("google_drive", CONV)

    @pytest.mark.asyncio
    async def test_multiple_tools_activated_in_one_turn(self, proxy: ActivationProxy):
        result = await proxy.intercept_and_execute(
            tool_calls=[
                ToolCall("google_drive", {}),
                ToolCall("slack", {}),
                ToolCall("web_search", {}),
            ],
            conversation_id=CONV,
            department=DEPT,
            executor=_success_executor,
        )
        assert set(result.activated) == {"google_drive", "slack", "web_search"}
        assert len(result.executed) == 3


# ── Unregistered Tool Tests ───────────────────────────────────

class TestUnregistered:
    @pytest.mark.asyncio
    async def test_unregistered_tool_errors(self, proxy: ActivationProxy):
        result = await proxy.intercept_and_execute(
            tool_calls=[ToolCall("nonexistent_tool", {})],
            conversation_id=CONV,
            department=DEPT,
            executor=_success_executor,
        )
        assert len(result.errors) == 1
        assert "not registered" in result.errors[0]
        assert len(result.executed) == 1
        assert not result.executed[0].success


# ── Governance Blocking Tests ─────────────────────────────────

class TestGovernanceBlocking:
    @pytest.mark.asyncio
    async def test_department_blocked(self, proxy: ActivationProxy):
        """Canva only allowed for marketing/product, not engineering."""
        result = await proxy.intercept_and_execute(
            tool_calls=[ToolCall("canva", {})],
            conversation_id=CONV,
            department="engineering",
            executor=_success_executor,
        )
        assert len(result.blocked) == 1
        assert result.blocked[0].tool_id == "canva"
        assert "not allowed" in result.blocked[0].reason

    @pytest.mark.asyncio
    async def test_allowed_department_passes(self, proxy: ActivationProxy):
        result = await proxy.intercept_and_execute(
            tool_calls=[ToolCall("canva", {})],
            conversation_id=CONV,
            department="marketing",
            executor=_success_executor,
        )
        assert len(result.blocked) == 0
        assert len(result.executed) == 1
        assert result.executed[0].success

    @pytest.mark.asyncio
    async def test_mixed_allowed_and_blocked(self, proxy: ActivationProxy):
        """One call allowed, one blocked in same turn."""
        result = await proxy.intercept_and_execute(
            tool_calls=[
                ToolCall("terminal", {}),  # allowed for engineering
                ToolCall("canva", {}),     # blocked for engineering
            ],
            conversation_id=CONV,
            department="engineering",
            executor=_success_executor,
        )
        assert len(result.executed) == 1
        assert result.executed[0].tool_id == "terminal"
        assert len(result.blocked) == 1
        assert result.blocked[0].tool_id == "canva"


# ── Execution Error Tests ─────────────────────────────────────

class TestExecutionErrors:
    @pytest.mark.asyncio
    async def test_executor_exception_captured(self, proxy: ActivationProxy):
        result = await proxy.intercept_and_execute(
            tool_calls=[ToolCall("terminal", {})],
            conversation_id=CONV,
            department=DEPT,
            executor=_failing_executor,
        )
        assert len(result.executed) == 1
        assert not result.executed[0].success
        assert "Execution failed" in result.executed[0].error

    @pytest.mark.asyncio
    async def test_partial_failures(self, proxy: ActivationProxy, registry: ToolRegistry):
        """Some tools succeed, some fail in same turn."""
        registry.register_or_update(_make_tool("bad_tool"))
        result = await proxy.intercept_and_execute(
            tool_calls=[
                ToolCall("terminal", {}),
                ToolCall("bad_tool", {}),
            ],
            conversation_id=CONV,
            department=DEPT,
            executor=_selective_executor,
        )
        assert len(result.executed) == 2
        assert result.executed[0].success  # terminal
        assert not result.executed[1].success  # bad_tool
        assert not result.all_succeeded


# ── Deactivation Tests ────────────────────────────────────────

class TestDeactivation:
    @pytest.mark.asyncio
    async def test_idle_tools_deactivated_after_tick(self, proxy: ActivationProxy, sm: SessionManager):
        """Tools not used for enough turns get deactivated."""
        # Activate drive
        sm.activate_tool("google_drive", CONV)
        # Tick enough turns without using it (threshold=4)
        for _ in range(4):
            sm.tick_turn(CONV)
        assert not sm.is_tool_active("google_drive", CONV)

    @pytest.mark.asyncio
    async def test_tick_turn_called_after_execute(self, proxy: ActivationProxy, sm: SessionManager):
        """Proxy calls tick_turn after execution, advancing idle counters."""
        sm.activate_tool("slack", CONV)  # pre-activate slack
        # Execute only terminal -- slack is idle
        await proxy.intercept_and_execute(
            tool_calls=[ToolCall("terminal", {})],
            conversation_id=CONV,
            department=DEPT,
            executor=_success_executor,
        )
        # Slack should have turns_since_last_use incremented
        slack_session = sm.get_tool_session("slack", CONV)
        assert slack_session.turns_since_last_use == 1


# ── Cost Savings Tests ────────────────────────────────────────

class TestCostSavings:
    @pytest.mark.asyncio
    async def test_cost_savings_calculated(self, proxy: ActivationProxy):
        """Inactive tool schemas should be counted as savings."""
        result = await proxy.intercept_and_execute(
            tool_calls=[ToolCall("terminal", {})],
            conversation_id=CONV,
            department=DEPT,
            executor=_success_executor,
        )
        # Only terminal (150 tokens) is active.
        # Remaining: drive(200) + slack(100) + canva(300) + web_search(250) = 850
        assert result.cost_savings.tokens_not_loaded > 0
        assert result.cost_savings.connections_avoided >= 1

    @pytest.mark.asyncio
    async def test_more_active_tools_less_savings(self, proxy: ActivationProxy):
        """Activating more tools should reduce token savings."""
        # 1 tool active
        r1 = await proxy.intercept_and_execute(
            tool_calls=[ToolCall("terminal", {})],
            conversation_id="conv-a",
            department=DEPT,
            executor=_success_executor,
        )
        # 3 tools active
        r3 = await proxy.intercept_and_execute(
            tool_calls=[
                ToolCall("terminal", {}),
                ToolCall("slack", {}),
                ToolCall("web_search", {}),
            ],
            conversation_id="conv-b",
            department=DEPT,
            executor=_success_executor,
        )
        assert r1.cost_savings.tokens_not_loaded > r3.cost_savings.tokens_not_loaded


# ── LLM Context Tests ────────────────────────────────────────

class TestLLMContext:
    @pytest.mark.asyncio
    async def test_context_has_catalog(self, proxy: ActivationProxy):
        ctx = proxy.get_context_for_llm(CONV)
        assert "catalog" in ctx
        assert len(ctx["catalog"]) == 5  # all registered tools

    @pytest.mark.asyncio
    async def test_context_active_schemas_only_for_active(self, proxy: ActivationProxy, sm: SessionManager):
        sm.activate_tool("terminal", CONV)
        ctx = proxy.get_context_for_llm(CONV)
        assert "terminal" in ctx["active_schemas"]
        assert "google_drive" not in ctx["active_schemas"]

    @pytest.mark.asyncio
    async def test_context_no_active_schemas_when_none_active(self, proxy: ActivationProxy):
        ctx = proxy.get_context_for_llm(CONV)
        assert ctx["active_schemas"] == {}
        assert ctx["active_tool_ids"] == []


# ── ProxyResult Tests ─────────────────────────────────────────

class TestProxyResult:
    @pytest.mark.asyncio
    async def test_all_succeeded_true(self, proxy: ActivationProxy):
        result = await proxy.intercept_and_execute(
            tool_calls=[ToolCall("terminal", {})],
            conversation_id=CONV,
            department=DEPT,
            executor=_success_executor,
        )
        assert result.all_succeeded

    @pytest.mark.asyncio
    async def test_all_succeeded_false_on_error(self, proxy: ActivationProxy):
        result = await proxy.intercept_and_execute(
            tool_calls=[ToolCall("terminal", {})],
            conversation_id=CONV,
            department=DEPT,
            executor=_failing_executor,
        )
        assert not result.all_succeeded

    @pytest.mark.asyncio
    async def test_empty_tool_calls(self, proxy: ActivationProxy):
        result = await proxy.intercept_and_execute(
            tool_calls=[],
            conversation_id=CONV,
            department=DEPT,
            executor=_success_executor,
        )
        assert result.executed == []
        assert result.activated == []
        assert result.all_succeeded
