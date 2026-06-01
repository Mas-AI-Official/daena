"""Tests for the goal-derived plan-review gate (council DECISION-002).

A goal-derived autopilot run must PAUSE for founder plan-review before any
step executes or budget is spent. Approving the synthetic PLAN_REVIEW_GATE
begins execution; rejecting it stops the run with zero execution. Runs WITHOUT
require_initial_approval keep the prior (empty-plan / orchestrator) behavior.
"""

from __future__ import annotations

import asyncio

import pytest

from app.services.autopilot.continuation import AutopilotController, PLAN_REVIEW_GATE
from app.services.autopilot.criticality_classifier import CriticalityLevel
from app.services.swarm.planner import SubTask


class _Receipt:
    estimated_cost_usd = 0.0
    runtime_id = "test"
    status = "complete"
    duration_ms = 1


class _FakeExecutor:
    """Records executed step ids; never spends real budget."""

    def __init__(self) -> None:
        self.executed: list[str] = []

    async def execute_single(self, step, context):  # noqa: ANN001
        self.executed.append(step.id)
        return _Receipt()


class _AutoClassifier:
    """Always AUTO_PROCEED so the test isolates the plan-review gate (no per-step pause)."""

    def classify(self, task_type, context):  # noqa: ANN001
        return CriticalityLevel.AUTO_PROCEED


async def _wait_until(predicate, timeout: float = 3.0) -> bool:
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return True
        await asyncio.sleep(0.02)
    return False


@pytest.mark.asyncio
async def test_goal_plan_pauses_for_review_before_execution():
    executor = _FakeExecutor()
    controller = AutopilotController(executor, _AutoClassifier())
    plan = [
        SubTask(id="s1", description="Research market", task_type="web_research"),
        SubTask(id="s2", description="Draft summary", task_type="generate_draft"),
    ]
    state = await controller.start("sess-1", plan, {"require_initial_approval": True})

    # Pauses at the plan-review gate BEFORE any execution.
    assert await _wait_until(
        lambda: state.paused_step == PLAN_REVIEW_GATE and state._approval_event is not None
    )
    assert state.awaiting_plan_approval is True
    assert executor.executed == []  # nothing ran, no budget spent
    # Real plan preview is exposed for founder review (not opaque ids).
    assert [p["description"] for p in state.plan] == ["Research market", "Draft summary"]

    # Approving the review gate begins execution.
    assert await controller.approve_step("sess-1", PLAN_REVIEW_GATE)
    assert await _wait_until(lambda: executor.executed == ["s1", "s2"])
    assert state.awaiting_plan_approval is False


@pytest.mark.asyncio
async def test_goal_plan_reject_blocks_all_execution():
    executor = _FakeExecutor()
    controller = AutopilotController(executor, _AutoClassifier())
    plan = [SubTask(id="s1", description="x", task_type="web_research")]
    state = await controller.start("sess-2", plan, {"require_initial_approval": True})

    assert await _wait_until(
        lambda: state.paused_step == PLAN_REVIEW_GATE and state._approval_event is not None
    )
    # Rejecting the plan stops the run with zero execution.
    assert await controller.reject_step("sess-2", PLAN_REVIEW_GATE)
    assert await _wait_until(lambda: state.enabled is False)
    assert executor.executed == []


@pytest.mark.asyncio
async def test_no_goal_keeps_empty_plan_behavior():
    executor = _FakeExecutor()
    controller = AutopilotController(executor, _AutoClassifier())
    # No require_initial_approval, empty plan -> no review gate, completes at once.
    state = await controller.start("sess-3", [], {})
    assert await _wait_until(lambda: state.enabled is False)
    assert state.paused_step is None
    assert state.awaiting_plan_approval is False
    assert executor.executed == []
