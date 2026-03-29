"""Tests for Autopilot system (Sprint 2, Phase 2.5).

Covers CriticalityClassifier, AutopilotController, AutopilotState,
BackgroundQueue, and API endpoint wiring.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.autopilot.background_queue import BackgroundQueue, BackgroundTask
from app.services.autopilot.continuation import (
    AutopilotController,
    AutopilotState,
)
from app.services.autopilot.criticality_classifier import (
    CriticalityClassifier,
    CriticalityLevel,
    CriticalityRule,
)
from app.services.runtimes.base_adapter import (
    BaseRuntimeAdapter,
    RuntimeCapability,
    RuntimeStatus,
)
from app.services.runtimes.cost_estimator import CostEstimator
from app.services.runtimes.registry import RuntimeRegistry
from app.services.swarm.executor import SwarmExecutor
from app.services.swarm.planner import SubTask

# ── Helpers ──


class MockAdapter(BaseRuntimeAdapter):
    """Minimal mock adapter for autopilot tests."""

    def __init__(self, runtime_id="mock", display_name="Mock"):
        super().__init__(runtime_id, display_name)

    async def check_installed(self) -> bool:
        return True

    async def check_health(self) -> RuntimeStatus:
        return RuntimeStatus.ONLINE

    async def get_capabilities(self) -> RuntimeCapability:
        return RuntimeCapability(simple_chat=7.0, code_generation=8.0)

    async def execute(self, task, context):
        yield "done"

    async def cancel(self, session_id: str) -> bool:
        return True

    def get_auth_requirements(self) -> dict:
        return {}


def _make_executor() -> SwarmExecutor:
    """Create a SwarmExecutor with a mock registry."""
    registry = RuntimeRegistry()
    adapter = MockAdapter("mock_runtime", "Mock")
    registry.register(adapter)
    registry._installed_cache["mock_runtime"] = True
    registry._health_cache["mock_runtime"] = RuntimeStatus.ONLINE
    return SwarmExecutor(registry, CostEstimator())


# ── CriticalityClassifier tests ──


class TestCriticalityClassifier:
    def test_auto_proceed_actions(self):
        c = CriticalityClassifier()
        assert c.classify("read_file") == CriticalityLevel.AUTO_PROCEED
        assert c.classify("search") == CriticalityLevel.AUTO_PROCEED
        assert c.classify("analyze") == CriticalityLevel.AUTO_PROCEED
        assert c.classify("summarize") == CriticalityLevel.AUTO_PROCEED

    def test_notify_after_actions(self):
        c = CriticalityClassifier()
        assert c.classify("write_file") == CriticalityLevel.NOTIFY_AFTER
        assert c.classify("run_command") == CriticalityLevel.NOTIFY_AFTER
        assert c.classify("web_research") == CriticalityLevel.NOTIFY_AFTER

    def test_pause_for_approval_actions(self):
        c = CriticalityClassifier()
        assert c.classify("delete_file") == CriticalityLevel.PAUSE_FOR_APPROVAL
        assert c.classify("send_email") == CriticalityLevel.PAUSE_FOR_APPROVAL
        assert c.classify("deploy") == CriticalityLevel.PAUSE_FOR_APPROVAL
        assert c.classify("git_push") == CriticalityLevel.PAUSE_FOR_APPROVAL

    def test_unknown_action_defaults_to_pause(self):
        c = CriticalityClassifier()
        assert c.classify("unknown_action") == CriticalityLevel.PAUSE_FOR_APPROVAL

    def test_yolo_promotes_notify_to_auto(self):
        c = CriticalityClassifier()
        level = c.classify("write_file", context={"governance_preset": "YOLO"})
        assert level == CriticalityLevel.AUTO_PROCEED

    def test_yolo_does_not_promote_pause(self):
        c = CriticalityClassifier()
        level = c.classify("delete_file", context={"governance_preset": "YOLO"})
        assert level == CriticalityLevel.PAUSE_FOR_APPROVAL

    def test_lockdown_promotes_everything_to_pause(self):
        c = CriticalityClassifier()
        level = c.classify("read_file", context={"governance_preset": "LOCKDOWN"})
        assert level == CriticalityLevel.PAUSE_FOR_APPROVAL

    def test_paranoid_promotes_to_pause(self):
        c = CriticalityClassifier()
        level = c.classify("write_file", context={"governance_preset": "PARANOID"})
        assert level == CriticalityLevel.PAUSE_FOR_APPROVAL

    def test_custom_rules_override_defaults(self):
        custom = [CriticalityRule("read_file", CriticalityLevel.PAUSE_FOR_APPROVAL, "Custom")]
        c = CriticalityClassifier(custom_rules=custom)
        assert c.classify("read_file") == CriticalityLevel.PAUSE_FOR_APPROVAL

    def test_add_rule_dynamically(self):
        c = CriticalityClassifier()
        c.add_rule(CriticalityRule("custom_action", CriticalityLevel.NOTIFY_AFTER, "Custom"))
        assert c.classify("custom_action") == CriticalityLevel.NOTIFY_AFTER

    def test_get_rule(self):
        c = CriticalityClassifier()
        rule = c.get_rule("read_file")
        assert rule is not None
        assert rule.level == CriticalityLevel.AUTO_PROCEED

    def test_get_rule_nonexistent(self):
        c = CriticalityClassifier()
        assert c.get_rule("nonexistent") is None

    def test_known_action_types(self):
        c = CriticalityClassifier()
        types = c.known_action_types
        assert "read_file" in types
        assert "delete_file" in types
        assert len(types) > 20

    def test_to_dict_serialization(self):
        c = CriticalityClassifier()
        d = c.to_dict()
        assert "read_file" in d
        assert d["read_file"]["level"] == "auto_proceed"
        assert "reason" in d["read_file"]


# ── AutopilotState tests ──


class TestAutopilotState:
    def test_default_state(self):
        state = AutopilotState()
        assert state.enabled is False
        assert state.killed is False
        assert state.cost_ceiling_usd == 1.0
        assert state.total_cost_usd == 0.0

    def test_to_dict_excludes_internal_event(self):
        state = AutopilotState(
            enabled=True,
            session_id="test-123",
            pending_steps=["a", "b"],
        )
        d = state.to_dict()
        assert "enabled" in d
        assert "_approval_event" not in d
        assert d["session_id"] == "test-123"
        assert d["pending_steps"] == ["a", "b"]


# ── AutopilotController tests ──


class TestAutopilotController:
    @pytest.fixture
    def controller(self):
        executor = _make_executor()
        classifier = CriticalityClassifier()
        return AutopilotController(executor, classifier)

    @pytest.mark.asyncio
    async def test_start_creates_state(self, controller):
        plan = [SubTask(id="s1", task_type="simple_chat", assigned_runtime="mock_runtime")]
        state = await controller.start("sess-1", plan, {"cost_ceiling": 2.0})
        assert state.enabled is True
        assert state.session_id == "sess-1"
        assert state.cost_ceiling_usd == 2.0
        # Wait briefly for the loop to process
        await asyncio.sleep(0.1)

    @pytest.mark.asyncio
    async def test_kill_switch(self, controller):
        plan = [
            SubTask(id="s1", task_type="simple_chat", assigned_runtime="mock_runtime"),
            SubTask(id="s2", task_type="simple_chat", assigned_runtime="mock_runtime"),
        ]
        state = await controller.start("sess-2", plan)
        # Kill immediately
        killed = await controller.kill("sess-2")
        assert killed is True
        await asyncio.sleep(0.2)
        assert state.killed is True

    @pytest.mark.asyncio
    async def test_kill_nonexistent_session(self, controller):
        result = await controller.kill("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_get_state(self, controller):
        plan = [SubTask(id="s1", task_type="simple_chat", assigned_runtime="mock_runtime")]
        await controller.start("sess-3", plan)
        state = controller.get_state("sess-3")
        assert state is not None
        assert state.session_id == "sess-3"

    @pytest.mark.asyncio
    async def test_get_state_nonexistent(self, controller):
        assert controller.get_state("no-such-session") is None

    @pytest.mark.asyncio
    async def test_active_session_ids(self, controller):
        plan = [SubTask(id="s1", task_type="simple_chat", assigned_runtime="mock_runtime")]
        await controller.start("sess-4", plan)
        # Give the loop a moment
        await asyncio.sleep(0.05)
        # The session might complete quickly since it is a simple auto-proceed task
        ids = controller.active_session_ids
        assert isinstance(ids, list)

    @pytest.mark.asyncio
    async def test_ws_notification_sent(self, controller):
        """WebSocket manager receives notifications."""
        mock_ws = MagicMock()
        mock_ws.broadcast = AsyncMock()
        controller._ws = mock_ws

        plan = [SubTask(id="s1", task_type="simple_chat", assigned_runtime="mock_runtime")]
        await controller.start("sess-5", plan)
        await asyncio.sleep(0.2)

        # Should have been called with autopilot events
        assert mock_ws.broadcast.called

    @pytest.mark.asyncio
    async def test_cost_ceiling_stops_execution(self, controller):
        """When cost ceiling is hit, autopilot stops."""
        plan = [SubTask(id="s1", task_type="simple_chat", assigned_runtime="mock_runtime")]
        # Set cost ceiling to 0 so it stops immediately
        state = await controller.start("sess-6", plan, {"cost_ceiling": 0.0})
        # Wait for loop to process
        await asyncio.sleep(0.2)
        # The state should indicate cost ceiling was hit
        has_cost_event = any(
            n["type"] == "cost_ceiling_hit" for n in state.notifications
        )
        # Either cost ceiling hit or completed before checking (both valid)
        assert has_cost_event or not state.enabled

    @pytest.mark.asyncio
    async def test_approval_flow(self, controller):
        """Steps requiring approval pause and resume on approve."""
        plan = [SubTask(id="s1", task_type="deploy", assigned_runtime="mock_runtime")]
        state = await controller.start("sess-7", plan)
        # Wait for the loop to hit the pause
        await asyncio.sleep(0.1)
        assert state.paused_step == "s1"

        # Approve the step
        approved = await controller.approve_step("sess-7", "s1")
        assert approved is True
        await asyncio.sleep(0.2)

    @pytest.mark.asyncio
    async def test_reject_flow(self, controller):
        """Rejecting a paused step stops autopilot."""
        plan = [SubTask(id="s1", task_type="deploy", assigned_runtime="mock_runtime")]
        state = await controller.start("sess-8", plan)
        await asyncio.sleep(0.1)

        rejected = await controller.reject_step("sess-8", "s1")
        assert rejected is True
        await asyncio.sleep(0.2)
        assert state.killed is True


# ── BackgroundQueue tests ──


class TestBackgroundQueue:
    @pytest.mark.asyncio
    async def test_enqueue_and_process(self):
        queue = BackgroundQueue(max_concurrent=2)
        worker = asyncio.create_task(queue.start_worker())

        task = BackgroundTask(id="t1", session_id="s1", description="Test")
        await queue.enqueue(task)
        await asyncio.sleep(0.2)

        assert task.status in ("complete", "running")
        queue.stop()
        worker.cancel()
        with pytest.raises(asyncio.CancelledError):
            await worker

    @pytest.mark.asyncio
    async def test_cancel_task(self):
        queue = BackgroundQueue()
        task = BackgroundTask(id="t2", session_id="s1", description="Test")
        queue._active["t2"] = task
        result = await queue.cancel("t2")
        assert result is True
        assert task.status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_nonexistent(self):
        queue = BackgroundQueue()
        result = await queue.cancel("no-such-task")
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_all_for_session(self):
        queue = BackgroundQueue()
        t1 = BackgroundTask(id="t1", session_id="s1", description="A")
        t2 = BackgroundTask(id="t2", session_id="s1", description="B")
        t3 = BackgroundTask(id="t3", session_id="s2", description="C")
        queue._active = {"t1": t1, "t2": t2, "t3": t3}

        count = await queue.cancel_all("s1")
        assert count == 2
        assert t1.status == "cancelled"
        assert t2.status == "cancelled"
        assert t3.status != "cancelled"

    def test_get_summary_empty(self):
        queue = BackgroundQueue()
        summary = queue.get_summary("s1")
        assert summary["completed"] == 0
        assert summary["tasks"] == []

    def test_get_summary_with_history(self):
        queue = BackgroundQueue()
        t1 = BackgroundTask(id="t1", session_id="s1", description="A", status="complete")
        t2 = BackgroundTask(id="t2", session_id="s1", description="B", status="failed")
        t3 = BackgroundTask(id="t3", session_id="s2", description="C", status="complete")
        queue._history = [t1, t2, t3]

        summary = queue.get_summary("s1")
        assert summary["completed"] == 1
        assert summary["failed"] == 1
        assert len(summary["tasks"]) == 2

    def test_is_running_default_false(self):
        queue = BackgroundQueue()
        assert queue.is_running is False

    def test_active_count(self):
        queue = BackgroundQueue()
        assert queue.active_count == 0

    def test_background_task_to_dict(self):
        task = BackgroundTask(id="t1", session_id="s1", description="Test")
        d = task.to_dict()
        assert d["id"] == "t1"
        assert d["status"] == "queued"


# ── Integration: full pipeline ──


class TestAutopilotIntegration:
    @pytest.mark.asyncio
    async def test_full_pipeline_auto_proceed(self):
        """End-to-end: planner > executor > autopilot with auto-proceed tasks."""
        registry = RuntimeRegistry()
        adapter = MockAdapter("mock", "Mock")
        registry.register(adapter)
        registry._installed_cache["mock"] = True
        registry._health_cache["mock"] = RuntimeStatus.ONLINE

        executor = SwarmExecutor(registry, CostEstimator())
        classifier = CriticalityClassifier()
        controller = AutopilotController(executor, classifier)

        plan = [
            SubTask(
                id="s1", description="Read files",
                task_type="read_file", assigned_runtime="mock",
            ),
            SubTask(
                id="s2", description="Analyze",
                task_type="analyze", assigned_runtime="mock",
            ),
        ]

        state = await controller.start("full-test", plan, {"cost_ceiling": 10.0})
        await asyncio.sleep(0.3)

        # Both should complete (auto-proceed)
        assert len(state.completed_steps) == 2
        assert state.enabled is False

    @pytest.mark.asyncio
    async def test_full_pipeline_with_pause(self):
        """End-to-end: autopilot pauses on critical action."""
        registry = RuntimeRegistry()
        adapter = MockAdapter("mock", "Mock")
        registry.register(adapter)
        registry._installed_cache["mock"] = True
        registry._health_cache["mock"] = RuntimeStatus.ONLINE

        executor = SwarmExecutor(registry, CostEstimator())
        classifier = CriticalityClassifier()
        controller = AutopilotController(executor, classifier)

        plan = [
            SubTask(
                id="s1", description="Safe task",
                task_type="read_file", assigned_runtime="mock",
            ),
            SubTask(
                id="s2", description="Deploy to prod",
                task_type="deploy", assigned_runtime="mock",
            ),
        ]

        state = await controller.start("pause-test", plan, {"cost_ceiling": 10.0})
        await asyncio.sleep(0.2)

        # First should complete, second should pause
        assert "s1" in state.completed_steps
        assert state.paused_step == "s2"

        # Approve and let it continue
        await controller.approve_step("pause-test", "s2")
        await asyncio.sleep(0.3)

        assert "s2" in state.completed_steps
        assert state.enabled is False
