"""Unit tests for the Daena VP meta-agent.

Covers the three phases of the hybrid router:
* ``plan`` -- rule hit, rule miss with model fallback, total miss
* ``route`` -- stays put on IDLE, reroutes on OVERLOADED, falls back
  to original when no alternate is available
* ``resolve_conflict`` -- single-output passthrough, agreement-based
  pick, council escalation, forced fallback when council missing
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.daena_vp import (
    CANONICAL_DEPARTMENTS,
    DaenaVP,
    VPDecision,
    VPPlan,
    VPSubtask,
)


# ── plan() ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_plan_rule_match_marketing() -> None:
    """'Draft a Q2 marketing campaign' hits the Marketing rule first."""
    vp = DaenaVP()
    plan = await vp.plan("Draft a Q2 marketing campaign for product X")
    assert plan.routing_mode == "rule"
    assert plan.subtasks[0].department == "Marketing"
    assert "Marketing" in plan.involved_departments


@pytest.mark.asyncio
async def test_plan_multi_rule_hits_produce_multiple_subtasks() -> None:
    """A request that spans Marketing + Finance produces 2 subtasks."""
    vp = DaenaVP()
    plan = await vp.plan(
        "Launch the campaign within our $5k budget and track the expense",
    )
    depts = plan.involved_departments
    assert "Marketing" in depts
    assert "Finance" in depts


@pytest.mark.asyncio
async def test_plan_falls_back_to_engineering_when_nothing_matches() -> None:
    """Gibberish that matches no rules + no planner -> Engineering owns."""
    vp = DaenaVP()
    plan = await vp.plan("xyzzy plugh foobar")
    assert plan.routing_mode == "fallback"
    assert len(plan.subtasks) == 1
    assert plan.subtasks[0].department == "Engineering"


@pytest.mark.asyncio
async def test_plan_model_fallback_tags_subtasks_via_second_rule_pass() -> None:
    """When rule router misses at the top level but SwarmPlanner
    decomposes into subtasks that individually hit rules, tag them."""
    # Build a fake SwarmPlanner that returns two generic subtasks
    # whose descriptions trigger Marketing and Finance rules.
    fake_planner = MagicMock()
    fake_sub_a = MagicMock(description="refresh brand audience story", task_type="simple_chat", depends_on=[])
    fake_sub_b = MagicMock(description="reconcile quarterly expense forecast", task_type="complex_reasoning", depends_on=[])
    fake_planner.decompose_and_route = AsyncMock(return_value=[fake_sub_a, fake_sub_b])

    vp = DaenaVP(swarm_planner=fake_planner)
    plan = await vp.plan("handle the thing")

    assert plan.routing_mode == "model"
    depts = plan.involved_departments
    assert "Marketing" in depts
    assert "Finance" in depts


@pytest.mark.asyncio
async def test_plan_model_fallback_failure_degrades_gracefully() -> None:
    """If SwarmPlanner raises, VP returns the fallback subtask, not an error."""
    fake_planner = MagicMock()
    fake_planner.decompose_and_route = AsyncMock(side_effect=RuntimeError("boom"))

    vp = DaenaVP(swarm_planner=fake_planner)
    plan = await vp.plan("something nobody understands")

    assert plan.routing_mode == "fallback"
    assert plan.subtasks[0].department == "Engineering"


# ── route() ─────────────────────────────────────────────────────


def _snapshot(overrides: dict[str, str] | None = None) -> list[dict]:
    """Helper -- returns a full 10-dept snapshot with optional overrides."""
    overrides = overrides or {}
    return [
        {
            "department_name": name,
            "status": overrides.get(name, "IDLE"),
            "current_task_id": None,
            "current_task_summary": None,
            "queue_depth": 0,
            "last_activity_at": None,
        }
        for name in CANONICAL_DEPARTMENTS
    ]


@pytest.mark.asyncio
async def test_route_stays_when_dept_is_idle() -> None:
    """IDLE departments are NOT rerouted."""
    state = MagicMock()
    state.snapshot = AsyncMock(return_value=_snapshot())
    vp = DaenaVP(state_service=state)

    plan = VPPlan(
        user_request="campaign brief",
        subtasks=[VPSubtask(description="x", department="Marketing", reason="r")],
        routing_mode="rule",
    )
    routed = await vp.route(plan, tenant_id=uuid.uuid4())
    assert routed.subtasks[0].department == "Marketing"
    assert "rerouted" not in routed.subtasks[0].reason


@pytest.mark.asyncio
async def test_route_reroutes_when_dept_is_overloaded() -> None:
    """OVERLOADED primary -> swap to first available alternate."""
    state = MagicMock()
    state.snapshot = AsyncMock(return_value=_snapshot({"Marketing": "OVERLOADED"}))
    vp = DaenaVP(state_service=state)

    plan = VPPlan(
        user_request="campaign brief",
        subtasks=[VPSubtask(
            description="x",
            department="Marketing",
            reason="rule hit",
            metadata={"alternates": ["Product", "Sales"]},
        )],
        routing_mode="rule",
    )
    routed = await vp.route(plan, tenant_id=uuid.uuid4())
    assert routed.subtasks[0].department == "Product"
    assert "rerouted from Marketing" in routed.subtasks[0].reason


@pytest.mark.asyncio
async def test_route_leaves_subtask_when_no_alternate_is_available() -> None:
    """If primary and all alternates are OVERLOADED, leave the subtask
    on the original department. It will queue behind current work --
    that's correct behavior, not a bug."""
    state = MagicMock()
    state.snapshot = AsyncMock(return_value=_snapshot({
        "Marketing": "OVERLOADED",
        "Product": "OVERLOADED",
        "Sales": "OVERLOADED",
    }))
    vp = DaenaVP(state_service=state)

    plan = VPPlan(
        user_request="campaign brief",
        subtasks=[VPSubtask(
            description="x",
            department="Marketing",
            reason="rule hit",
            metadata={"alternates": ["Product", "Sales"]},
        )],
        routing_mode="rule",
    )
    routed = await vp.route(plan, tenant_id=uuid.uuid4())
    assert routed.subtasks[0].department == "Marketing"


@pytest.mark.asyncio
async def test_route_no_state_service_is_noop() -> None:
    """Without a state service (e.g. tests), route returns plan unchanged."""
    vp = DaenaVP()
    plan = VPPlan(
        user_request="x",
        subtasks=[VPSubtask(description="d", department="Engineering")],
        routing_mode="rule",
    )
    routed = await vp.route(plan, tenant_id=uuid.uuid4())
    assert routed is plan


# ── resolve_conflict() ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_resolve_single_output_passthrough() -> None:
    """One output = nothing to reconcile."""
    vp = DaenaVP()
    decision = await vp.resolve_conflict(
        [{"department": "Marketing", "content": "go for launch"}],
    )
    assert decision.method == "agreement"
    assert decision.verdict == "go for launch"


@pytest.mark.asyncio
async def test_resolve_empty_outputs_returns_forced_fallback() -> None:
    vp = DaenaVP()
    decision = await vp.resolve_conflict([])
    assert decision.method == "forced_fallback"
    assert decision.verdict == ""


@pytest.mark.asyncio
async def test_resolve_high_agreement_picks_longest() -> None:
    """When outputs largely agree, pick the most detailed one.
    Uses inputs with Jaccard >= 0.4 (empirical agreement threshold)."""
    vp = DaenaVP()
    decision = await vp.resolve_conflict([
        {"department": "Marketing", "content": "approve launch of Q2 campaign"},
        {"department": "Sales", "content": "approve launch of Q2 campaign with attribution tracking"},
    ])
    assert decision.method == "agreement"
    assert "attribution" in decision.verdict


@pytest.mark.asyncio
async def test_resolve_low_agreement_escalates_to_council() -> None:
    """Disagreement + council available -> synthesize via council."""
    fake_council = MagicMock()
    fake_llm = MagicMock()
    fake_council.synthesize = AsyncMock(return_value=MagicMock(
        synthesis="synthesized verdict",
        agreement_score=0.5,
    ))
    vp = DaenaVP(council_engine=fake_council, llm_service=fake_llm)

    decision = await vp.resolve_conflict(
        [
            {"department": "Marketing", "content": "ship now"},
            {"department": "Legal & Compliance", "content": "reject everything for regulatory reasons"},
        ],
        original_request="decide whether to ship",
    )
    assert decision.method == "council"
    assert decision.verdict == "synthesized verdict"
    assert "Marketing" in decision.participating_departments
    assert "Legal & Compliance" in decision.participating_departments


@pytest.mark.asyncio
async def test_resolve_low_agreement_no_council_forced_fallback() -> None:
    """Disagreement + no council available -> concat with dept headers
    so a human can pick. We should NOT silently lose an answer."""
    vp = DaenaVP()
    decision = await vp.resolve_conflict([
        {"department": "Marketing", "content": "ship now"},
        {"department": "Legal & Compliance", "content": "reject; regulatory risk"},
    ])
    assert decision.method == "forced_fallback"
    assert "Marketing" in decision.verdict
    assert "Legal & Compliance" in decision.verdict


@pytest.mark.asyncio
async def test_resolve_council_failure_degrades_to_fallback() -> None:
    """Council raises -> forced fallback, never lose the user's data."""
    fake_council = MagicMock()
    fake_llm = MagicMock()
    fake_council.synthesize = AsyncMock(side_effect=RuntimeError("council dead"))
    vp = DaenaVP(council_engine=fake_council, llm_service=fake_llm)

    decision = await vp.resolve_conflict([
        {"department": "A", "content": "one thing"},
        {"department": "B", "content": "contradictory opposite claim"},
    ])
    assert decision.method == "forced_fallback"


# ── Plan serialization ─────────────────────────────────────────


def test_plan_to_dict_shape() -> None:
    """to_dict is the shape the SSE stream + audit log depend on."""
    plan = VPPlan(
        user_request="x",
        subtasks=[VPSubtask(description="d", department="Finance", reason="r")],
        routing_mode="rule",
    )
    d = plan.to_dict()
    assert d["user_request"] == "x"
    assert d["routing_mode"] == "rule"
    assert d["involved_departments"] == ["Finance"]
    assert d["subtasks"][0]["department"] == "Finance"


def test_decision_to_dict_shape() -> None:
    decision = VPDecision(
        verdict="go",
        method="agreement",
        participating_departments=["Marketing"],
        agreement_score=1.0,
    )
    d = decision.to_dict()
    assert d["verdict"] == "go"
    assert d["participating_departments"] == ["Marketing"]
    assert d["agreement_score"] == 1.0
