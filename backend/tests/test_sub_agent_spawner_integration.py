"""Tests for SubAgentSpawner + SwarmPlanner integration.

Verifies:
1. SubAgentSpawner spawns and dissolves sub-agents correctly
2. KnowledgeBus enables cross-department awareness
3. SwarmPlanner attaches spawn plans to bulk_operations subtasks
4. execute_bulk_subtask bridges planner -> spawner correctly
5. Capacity limits are respected
6. Failed sub-agents don't crash the system
"""

from __future__ import annotations

import asyncio

import pytest

from app.services.sub_agent_spawner import (
    DEFAULT_CONCURRENCY,
    MAX_PER_TASK,
    KnowledgeBus,
    SpawnPlan,
    SpawnResult,
    SubAgent,
    SubAgentSpawner,
    SubAgentStatus,
)


# ── KnowledgeBus tests ──────────────────────────────────────


class TestKnowledgeBus:
    """Tests for cross-department knowledge sharing."""

    def setup_method(self) -> None:
        self.bus = KnowledgeBus()

    def test_publish_and_query(self) -> None:
        self.bus.publish("Engineering", "build_status", "v3.7 deployed")
        results = self.bus.query("Marketing", source_department="Engineering")
        assert len(results) == 1
        assert results[0]["content"] == "v3.7 deployed"
        assert results[0]["department"] == "Engineering"

    def test_cross_department_visibility(self) -> None:
        self.bus.publish("Engineering", "release", "New API endpoint live")
        self.bus.publish("Sales", "deal", "Enterprise client signed")
        self.bus.publish("Finance", "cost", "Monthly burn: $12k")

        # Marketing should see Engineering and Sales, not itself
        results = self.bus.query("Marketing")
        depts = {r["department"] for r in results}
        assert "Engineering" in depts
        assert "Sales" in depts
        assert "Finance" in depts
        assert "Marketing" not in depts

    def test_query_by_type(self) -> None:
        self.bus.publish("Engineering", "build", "v3.7")
        self.bus.publish("Engineering", "incident", "Redis down")

        results = self.bus.query(
            "Operations",
            source_department="Engineering",
            knowledge_type="incident",
        )
        assert len(results) == 1
        assert results[0]["type"] == "incident"

    def test_query_limit(self) -> None:
        for i in range(20):
            self.bus.publish("Engineering", "log", f"Entry {i}")

        results = self.bus.query("Operations", limit=5)
        assert len(results) == 5

    def test_clear_wipes_all(self) -> None:
        self.bus.publish("Engineering", "test", "data")
        self.bus.clear()
        assert self.bus.get_company_state() == {}

    def test_company_state_summary(self) -> None:
        self.bus.publish("Engineering", "a", "x")
        self.bus.publish("Engineering", "b", "y")
        self.bus.publish("Sales", "c", "z")

        state = self.bus.get_company_state()
        assert state == {"Engineering": 2, "Sales": 1}


# ── SubAgent lifecycle tests ─────────────────────────────────


class TestSubAgent:
    """Tests for sub-agent creation and dissolution."""

    def test_sub_agent_defaults(self) -> None:
        sa = SubAgent()
        assert sa.status == SubAgentStatus.SPAWNING
        assert len(sa.id) == 12
        assert sa.tokens_used == 0
        assert sa.cost_usd == 0.0

    def test_dissolve_returns_report(self) -> None:
        sa = SubAgent(
            parent_department="Security Operations",
            parent_capability="SHIELD",
            task_slice="scan auth.py",
        )
        sa.status = SubAgentStatus.COMPLETE
        sa.result = "2 vulnerabilities found"
        sa.tokens_used = 500

        report = sa.dissolve()
        assert report["status"] == "DISSOLVED"
        assert report["parent"] == "Security Operations.SHIELD"
        assert report["tokens_used"] == 500
        assert report["duration_ms"] >= 0


# ── SubAgentSpawner tests ────────────────────────────────────


class TestSubAgentSpawner:
    """Tests for spawning and managing sub-agents."""

    def setup_method(self) -> None:
        self.bus = KnowledgeBus()
        self.spawner = SubAgentSpawner(self.bus, max_concurrency=10)

    def test_plan_spawn_basic(self) -> None:
        items = [f"file_{i}.py" for i in range(10)]
        plan = self.spawner.plan_spawn(
            task="Scan files",
            department="Security Operations",
            capability="SHIELD",
            items=items,
        )
        assert plan.total_slices == 10
        assert plan.concurrency == 10
        assert plan.estimated_tokens == 10_000  # 1000 per item
        assert len(plan.slices) == 10

    def test_plan_spawn_caps_at_max(self) -> None:
        items = [f"file_{i}.py" for i in range(1000)]
        plan = self.spawner.plan_spawn(
            task="Scan many files",
            department="Engineering",
            capability="MIND",
            items=items,
        )
        assert plan.total_slices == MAX_PER_TASK  # 500
        assert len(plan.slices) == MAX_PER_TASK

    @pytest.mark.asyncio
    async def test_spawn_and_execute_success(self) -> None:
        items = ["auth.py", "crypto.py", "network.py"]
        plan = self.spawner.plan_spawn(
            task="Scan",
            department="Security Operations",
            capability="SHIELD",
            items=items,
        )

        async def mock_executor(task_slice: str) -> str:
            return f"Scanned {task_slice}: no issues"

        result = await self.spawner.spawn_and_execute(plan, mock_executor)

        assert result.sub_agents_spawned == 3
        assert result.sub_agents_completed == 3
        assert result.sub_agents_failed == 0
        assert "auth.py" in result.merged_result
        assert result.total_duration_ms >= 0

    @pytest.mark.asyncio
    async def test_spawn_and_execute_with_failures(self) -> None:
        items = ["good.py", "bad.py", "good2.py"]
        plan = self.spawner.plan_spawn(
            task="Scan",
            department="Engineering",
            capability="MIND",
            items=items,
        )

        async def flaky_executor(task_slice: str) -> str:
            if "bad" in task_slice:
                raise ValueError("Parse error")
            return f"OK: {task_slice}"

        result = await self.spawner.spawn_and_execute(plan, flaky_executor)

        assert result.sub_agents_spawned == 3
        assert result.sub_agents_completed == 2
        assert result.sub_agents_failed == 1

    @pytest.mark.asyncio
    async def test_spawn_and_execute_timeout(self) -> None:
        items = ["slow.py"]
        plan = self.spawner.plan_spawn(
            task="Scan",
            department="Engineering",
            capability="MIND",
            items=items,
        )

        async def slow_executor(task_slice: str) -> str:
            await asyncio.sleep(10)
            return "done"

        result = await self.spawner.spawn_and_execute(
            plan, slow_executor, timeout=0.1,
        )

        assert result.sub_agents_failed == 1
        assert result.sub_agents_completed == 0

    @pytest.mark.asyncio
    async def test_knowledge_bus_updated_after_execution(self) -> None:
        items = ["file.py"]
        plan = self.spawner.plan_spawn(
            task="Scan",
            department="Security Operations",
            capability="SHIELD",
            items=items,
        )

        async def mock_executor(task_slice: str) -> str:
            return "clean"

        await self.spawner.spawn_and_execute(plan, mock_executor)

        # Knowledge bus should have the result published
        results = self.bus.query("Engineering", source_department="Security Operations")
        assert len(results) == 1
        assert "Completed 1/1" in results[0]["content"]

    def test_stats(self) -> None:
        stats = self.spawner.get_stats()
        assert stats["active_sub_agents"] == 0
        assert stats["total_spawned"] == 0
        assert stats["max_concurrency"] == 10

    @pytest.mark.asyncio
    async def test_all_sub_agents_dissolved_after_execution(self) -> None:
        items = ["a.py", "b.py"]
        plan = self.spawner.plan_spawn(
            task="Scan",
            department="Engineering",
            capability="MIND",
            items=items,
        )

        async def mock_executor(task_slice: str) -> str:
            return "ok"

        await self.spawner.spawn_and_execute(plan, mock_executor)

        # All sub-agents should be dissolved (removed from active)
        assert self.spawner.active_count == 0
        stats = self.spawner.get_stats()
        assert stats["total_spawned"] == 2
        assert stats["total_dissolved"] == 2


# ── SwarmPlanner + SubAgentSpawner integration ───────────────


class TestSwarmPlannerSpawnerIntegration:
    """Tests that SwarmPlanner correctly uses SubAgentSpawner."""

    def test_spawner_accessible_from_planner(self) -> None:
        """SwarmPlanner should expose its spawner."""
        from unittest.mock import AsyncMock, MagicMock

        from app.services.swarm.planner import SwarmPlanner

        mock_registry = MagicMock()
        mock_registry.select_runtime = AsyncMock(return_value="ollama")
        mock_registry.get_capabilities_summary = AsyncMock(return_value="{}")

        spawner = SubAgentSpawner()
        planner = SwarmPlanner(mock_registry, spawner=spawner)

        assert planner.spawner is spawner

    @pytest.mark.asyncio
    async def test_execute_bulk_subtask_bridges_correctly(self) -> None:
        """execute_bulk_subtask should use SubAgentSpawner under the hood."""
        from unittest.mock import AsyncMock, MagicMock

        from app.services.swarm.planner import SubTask, SwarmPlanner

        mock_registry = MagicMock()
        spawner = SubAgentSpawner()
        planner = SwarmPlanner(mock_registry, spawner=spawner)

        subtask = SubTask(
            description="Scan 3 files",
            task_type="bulk_operations",
        )
        items = ["a.py", "b.py", "c.py"]

        async def mock_fn(task_slice: str) -> str:
            return f"scanned {task_slice}"

        result = await planner.execute_bulk_subtask(
            subtask,
            executor_fn=mock_fn,
            items=items,
            department="Security Operations",
            capability="SHIELD",
        )

        assert result.sub_agents_spawned == 3
        assert result.sub_agents_completed == 3
        assert subtask.status == "complete"
        assert "scanned a.py" in subtask.result_data
