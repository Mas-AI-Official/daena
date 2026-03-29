"""Tests for SwarmPlanner and SwarmExecutor (Sprint 2, Phase 2).

Covers task decomposition, routing, parallel execution with
dependencies, fallback logic, governance rejection, and cost tracking.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.runtimes.base_adapter import (
    BaseRuntimeAdapter,
    ExecutionReceipt,
    RuntimeCapability,
    RuntimeStatus,
)
from app.services.runtimes.cost_estimator import CostEstimator
from app.services.runtimes.registry import RuntimeRegistry
from app.services.swarm.executor import SwarmExecutor
from app.services.swarm.planner import SubTask, SwarmPlanner

# ── Helpers ──


class MockAdapter(BaseRuntimeAdapter):
    """Mock runtime adapter for testing."""

    def __init__(
        self,
        runtime_id: str = "mock",
        display_name: str = "Mock",
        installed: bool = True,
        health: RuntimeStatus = RuntimeStatus.ONLINE,
        capabilities: RuntimeCapability | None = None,
        output: str = "mock output",
    ):
        super().__init__(runtime_id, display_name)
        self._installed = installed
        self._health = health
        self._capabilities = capabilities or RuntimeCapability(
            complex_reasoning=8.0,
            code_generation=9.0,
            simple_chat=7.0,
            cost_per_1k_tokens=0.01,
        )
        self._output = output

    async def check_installed(self) -> bool:
        return self._installed

    async def check_health(self) -> RuntimeStatus:
        return self._health

    async def get_capabilities(self) -> RuntimeCapability:
        return self._capabilities

    async def execute(self, task, context):
        yield self._output

    async def cancel(self, session_id: str) -> bool:
        return True

    def get_auth_requirements(self) -> dict:
        return {"type": "none"}


def _make_registry(*adapters: BaseRuntimeAdapter) -> RuntimeRegistry:
    """Create a registry with adapters, pre-populated health/install caches."""
    registry = RuntimeRegistry()
    for a in adapters:
        registry.register(a)
        registry._installed_cache[a.runtime_id] = True
        registry._health_cache[a.runtime_id] = RuntimeStatus.ONLINE
    return registry


# ── SubTask tests ──


class TestSubTask:
    def test_to_dict_serialization(self):
        st = SubTask(
            id="st-1",
            description="Test task",
            task_type="code_generation",
            assigned_runtime="claude_code",
            estimated_tokens=1000,
            estimated_cost_usd=0.015,
        )
        d = st.to_dict()
        assert d["id"] == "st-1"
        assert d["task_type"] == "code_generation"
        assert d["estimated_cost_usd"] == 0.015
        assert d["receipt"] is None

    def test_to_dict_with_receipt(self):
        receipt = ExecutionReceipt(
            runtime_id="claude_code",
            task_description="test",
            assigned_reason="best",
            capability_score=9.5,
            start_time="2026-01-01T00:00:00",
            end_time="2026-01-01T00:00:01",
            duration_ms=1000,
            token_count=500,
            estimated_cost_usd=0.01,
            status="success",
            output_summary="done",
            governance_tier="auto",
        )
        st = SubTask(receipt=receipt)
        d = st.to_dict()
        assert d["receipt"] is not None
        assert d["receipt"]["status"] == "success"

    def test_default_status_is_pending(self):
        st = SubTask()
        assert st.status == "pending"

    def test_depends_on_default_empty(self):
        st = SubTask()
        assert st.depends_on == []


# ── SwarmPlanner tests ──


class TestSwarmPlanner:
    @pytest.fixture
    def registry(self):
        return _make_registry(
            MockAdapter("claude_code", "Claude Code"),
            MockAdapter("ollama", "Ollama", capabilities=RuntimeCapability(
                simple_chat=7.0, code_generation=6.5, cost_per_1k_tokens=0.0,
            )),
        )

    @pytest.fixture
    def planner(self, registry):
        return SwarmPlanner(registry, CostEstimator())

    def test_fallback_single_task(self, planner):
        result = planner._fallback_single_task("Build a REST API")
        assert len(result) == 1
        assert result[0]["task_type"] == "complex_reasoning"

    def test_parse_decomposition_valid_json(self, planner):
        raw = (
            '[{"description": "step1", "task_type": "code_generation",'
            ' "depends_on": [], "estimated_tokens": 1000}]'
        )
        result = planner._parse_decomposition(raw)
        assert len(result) == 1
        assert result[0]["task_type"] == "code_generation"

    def test_parse_decomposition_with_code_fences(self, planner):
        raw = (
            '```json\n[{"description": "step1",'
            ' "task_type": "simple_chat", "depends_on": []}]\n```'
        )
        result = planner._parse_decomposition(raw)
        assert len(result) == 1

    def test_parse_decomposition_invalid_returns_empty(self, planner):
        result = planner._parse_decomposition("not json at all")
        assert result == []

    def test_parse_decomposition_nested_subtasks_key(self, planner):
        raw = '{"subtasks": [{"description": "a", "task_type": "search"}]}'
        result = planner._parse_decomposition(raw)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_decompose_and_route_fallback(self, planner):
        """When LLM is unavailable, falls back to single subtask."""
        with patch.object(planner, '_decompose_with_llm', side_effect=Exception("no LLM")):
            subtasks = await planner.decompose_and_route("Build an API")
        assert len(subtasks) == 1
        assert subtasks[0].task_type == "complex_reasoning"
        assert subtasks[0].assigned_runtime in ("claude_code", "ollama")

    @pytest.mark.asyncio
    async def test_decompose_and_route_multi_step(self, planner):
        """Decomposition with multiple steps routes each independently."""
        mock_result = [
            {
                "description": "Research", "task_type": "web_research",
                "depends_on": [], "estimated_tokens": 500,
            },
            {
                "description": "Code it", "task_type": "code_generation",
                "depends_on": [0], "estimated_tokens": 2000,
            },
        ]
        with patch.object(planner, '_decompose_with_llm', return_value=mock_result):
            subtasks = await planner.decompose_and_route("Research and build")
        assert len(subtasks) == 2
        # Second depends on first
        assert subtasks[1].depends_on == [subtasks[0].id]
        # Each has a cost estimate
        assert all(st.estimated_cost_usd >= 0 for st in subtasks)

    @pytest.mark.asyncio
    async def test_decompose_assigns_fallback_runtime(self, planner):
        """Each subtask gets a fallback runtime different from primary."""
        mock_result = [
            {
                "description": "Test", "task_type": "code_generation",
                "depends_on": [], "estimated_tokens": 1000,
            },
        ]
        with patch.object(planner, '_decompose_with_llm', return_value=mock_result):
            subtasks = await planner.decompose_and_route("Test task")
        st = subtasks[0]
        # Fallback should be different from primary (or None if only 1 runtime)
        if st.fallback_runtime is not None:
            assert st.fallback_runtime != st.assigned_runtime


# ── SwarmExecutor tests ──


class TestSwarmExecutor:
    @pytest.fixture
    def registry(self):
        return _make_registry(
            MockAdapter("claude_code", "Claude Code", output="success output"),
            MockAdapter("ollama", "Ollama", output="fallback output"),
        )

    @pytest.fixture
    def executor(self, registry):
        return SwarmExecutor(registry, CostEstimator())

    @pytest.mark.asyncio
    async def test_execute_single_success(self, executor):
        st = SubTask(
            description="Test task",
            task_type="code_generation",
            assigned_runtime="claude_code",
        )
        receipt = await executor.execute_single(st)
        assert receipt.status == "success"
        assert receipt.runtime_id == "claude_code"

    @pytest.mark.asyncio
    async def test_execute_plan_no_deps(self, executor):
        """Subtasks without dependencies execute in parallel."""
        subtasks = [
            SubTask(id="a", description="Task A", assigned_runtime="claude_code"),
            SubTask(id="b", description="Task B", assigned_runtime="claude_code"),
        ]
        receipts = await executor.execute_plan(subtasks)
        assert len(receipts) == 2
        assert all(r.status == "success" for r in receipts)

    @pytest.mark.asyncio
    async def test_execute_plan_with_deps(self, executor):
        """Subtask B depends on A. B only runs after A completes."""
        subtasks = [
            SubTask(id="a", description="Task A", assigned_runtime="claude_code"),
            SubTask(id="b", description="Task B", assigned_runtime="claude_code", depends_on=["a"]),
        ]
        receipts = await executor.execute_plan(subtasks)
        assert len(receipts) == 2
        # Both should succeed
        assert all(r.status == "success" for r in receipts)

    @pytest.mark.asyncio
    async def test_execute_plan_dependency_failure_cascades(self, executor):
        """If A fails, B (which depends on A) also fails."""
        # Use a broken adapter for the primary
        broken = MockAdapter("broken", "Broken")
        broken._health = RuntimeStatus.ERROR
        executor._registry.register(broken)
        executor._registry._installed_cache["broken"] = True
        executor._registry._health_cache["broken"] = RuntimeStatus.ERROR

        subtasks = [
            SubTask(
                id="a", description="Task A", assigned_runtime="broken",
                fallback_runtime=None,
            ),
            SubTask(
                id="b", description="Task B", assigned_runtime="claude_code",
                depends_on=["a"],
            ),
        ]
        receipts = await executor.execute_plan(subtasks)
        # A should fail (runtime offline)
        a_receipt = next(r for r in receipts if "A" in r.task_description)
        assert a_receipt.status == "error"
        # B should also fail due to dependency
        b_receipt = next(r for r in receipts if "B" in r.task_description)
        assert b_receipt.status == "failed"

    @pytest.mark.asyncio
    async def test_execute_plan_fallback_on_failure(self, executor):
        """When primary runtime fails, executor tries fallback."""
        # Make a registry where primary is offline, fallback is online
        broken = MockAdapter("broken", "Broken")
        broken._health = RuntimeStatus.ERROR
        executor._registry.register(broken)
        executor._registry._installed_cache["broken"] = True
        executor._registry._health_cache["broken"] = RuntimeStatus.ERROR

        subtasks = [
            SubTask(
                id="a", description="Task A",
                assigned_runtime="broken",
                fallback_runtime="claude_code",
            ),
        ]
        receipts = await executor.execute_plan(subtasks)
        assert len(receipts) == 1
        assert receipts[0].status == "success"
        assert receipts[0].runtime_id == "claude_code"

    @pytest.mark.asyncio
    async def test_execute_plan_cancellation(self, executor):
        """Cancel signal stops processing new subtasks."""
        subtasks = [
            SubTask(id="a", description="A", assigned_runtime="claude_code"),
            SubTask(id="b", description="B", assigned_runtime="claude_code"),
            SubTask(id="c", description="C", assigned_runtime="claude_code"),
        ]
        # Cancel immediately
        executor.cancel()
        receipts = await executor.execute_plan(subtasks)
        # Should have 0 receipts since cancelled before starting
        assert len(receipts) == 0

    @pytest.mark.asyncio
    async def test_execute_plan_governance_rejection(self, executor):
        """When governance rejects a subtask, it gets status='rejected'."""
        mock_gov = MagicMock()
        mock_gov.evaluate = AsyncMock(return_value={"allowed": False, "message": "Blocked"})
        executor._governance = mock_gov

        subtasks = [
            SubTask(id="a", description="Dangerous task", assigned_runtime="claude_code"),
        ]
        receipts = await executor.execute_plan(subtasks, {"governance_slider": "STRICT"})
        assert len(receipts) == 1
        assert receipts[0].status == "rejected"

    @pytest.mark.asyncio
    async def test_execute_plan_runtime_not_registered(self, executor):
        """Subtask with non-existent runtime gets error receipt."""
        subtasks = [
            SubTask(id="a", description="Task", assigned_runtime="nonexistent"),
        ]
        receipts = await executor.execute_plan(subtasks)
        assert len(receipts) == 1
        assert receipts[0].status == "error"
        assert "not registered" in receipts[0].error_detail

    @pytest.mark.asyncio
    async def test_execute_single_builds_receipt(self, executor):
        """execute_single returns a properly structured receipt."""
        st = SubTask(
            description="Quick task",
            task_type="simple_chat",
            assigned_runtime="claude_code",
            estimated_tokens=500,
        )
        receipt = await executor.execute_single(st)
        assert receipt.runtime_id == "claude_code"
        assert receipt.duration_ms >= 0
        assert receipt.status == "success"
        assert receipt.governance_tier == "auto"
