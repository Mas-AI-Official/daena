"""Tests for OODA Engine: cycle flow, strategy switching, loop recovery.

Tests the brain loop without LLM calls -- mocks ToolUseLoop to test
cognitive flow logic: phase progression, strategy pivot on failure,
re-orientation after strategy exhaustion, and max-cycle guard.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from app.services.cognition.ooda_engine import (
    CognitivePhase,
    CognitiveResult,
    CognitiveState,
    OODAEngine,
    Observation,
    Strategy,
    StrategyStatus,
)


# ---- Helpers ----

FAKE_USER = UUID("00000000-0000-0000-0000-000000000001")
FAKE_TENANT = UUID("00000000-0000-0000-0000-000000000002")


def _make_engine(**kwargs) -> OODAEngine:
    """Create an OODAEngine with mocked DB."""
    db = MagicMock()
    return OODAEngine(db, FAKE_USER, FAKE_TENANT, **kwargs)


async def _collect_events(engine: OODAEngine, task: str, **kwargs) -> list[dict]:
    """Run engine and collect all yielded events."""
    events = []
    async for event in engine.run(task, **kwargs):
        events.append(event)
    return events


# ---- CognitiveState Tests ----


class TestCognitiveState:
    """Test CognitiveState data structure invariants."""

    def test_initial_state(self) -> None:
        state = CognitiveState(task="Do something")
        assert state.phase == CognitivePhase.OBSERVE
        assert state.cycle == 0
        assert state.max_cycles == 5
        assert state.current_strategy is None
        assert state.attempted_strategies == []

    def test_has_more_cycles(self) -> None:
        state = CognitiveState(task="x", max_cycles=3)
        state.cycle = 2
        assert state.has_more_cycles is True
        state.cycle = 3
        assert state.has_more_cycles is False

    def test_has_more_strategies(self) -> None:
        state = CognitiveState(task="x")
        state.strategies = [
            Strategy(name="a"),
            Strategy(name="b"),
            Strategy(name="c"),
        ]
        state.strategy_index = 0
        assert state.has_more_strategies is True
        state.strategy_index = 2
        assert state.has_more_strategies is False


# ---- Strategy Tests ----


class TestStrategy:
    def test_default_values(self) -> None:
        s = Strategy(name="test")
        assert s.status == StrategyStatus.PENDING
        assert s.confidence == 0.5
        assert s.reversible is True
        assert s.pre_mortem_risks == []

    def test_status_transitions(self) -> None:
        s = Strategy(name="test")
        s.status = StrategyStatus.EXECUTING
        assert s.status == StrategyStatus.EXECUTING
        s.status = StrategyStatus.FAILED
        assert s.status == StrategyStatus.FAILED


# ---- Observe Phase ----


class TestObservePhase:
    @pytest.mark.asyncio
    async def test_observe_creates_observation(self) -> None:
        engine = _make_engine()
        state = CognitiveState(task="Fix the auth bug")
        state = await engine._observe(state, {})

        assert state.observation is not None
        assert isinstance(state.observation, Observation)
        assert state.observation.task_description == "Fix the auth bug"

    @pytest.mark.asyncio
    async def test_observe_includes_prior_attempts(self) -> None:
        engine = _make_engine()
        state = CognitiveState(task="Fix bug")
        state.attempted_strategies = [
            Strategy(name="first_try", status=StrategyStatus.FAILED),
        ]
        state = await engine._observe(state, {})

        assert len(state.observation.prior_attempts) == 1
        assert state.observation.prior_attempts[0]["strategy"] == "first_try"
        assert state.observation.prior_attempts[0]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_observe_graceful_on_memory_failure(self) -> None:
        """Memory recall failure should not crash observe."""
        engine = _make_engine()
        state = CognitiveState(task="test")
        # Should not raise even if memory service is unavailable
        state = await engine._observe(state, {})
        assert state.observation is not None


# ---- Orient Phase ----


class TestOrientPhase:
    @pytest.mark.asyncio
    async def test_orient_classifies_problem(self) -> None:
        engine = _make_engine()
        state = CognitiveState(task="Fix the bug in auth middleware")
        state.observation = Observation(task_description=state.task)

        state = await engine._orient(state, {})

        assert state.problem_type in ("debugging", "creation", "deployment", "research", "optimization", "simple", "search", "lookup", "unknown")
        assert len(state.selected_frameworks) > 0
        assert "orient" not in state.orientation_analysis or state.orientation_analysis != ""

    @pytest.mark.asyncio
    async def test_orient_reclassifies_after_failures(self) -> None:
        """After failed strategies, orient should adjust classification."""
        engine = _make_engine()
        state = CognitiveState(task="Create config file")
        state.observation = Observation(task_description=state.task)
        state.attempted_strategies = [
            Strategy(name="first_principles", status=StrategyStatus.FAILED),
            Strategy(name="constraint_relaxation", status=StrategyStatus.FAILED),
        ]

        state = await engine._orient(state, {})
        # After 2+ failures, MetaReasoner reclassifies creation as debugging
        assert state.problem_type == "debugging"


# ---- Decide Phase ----


class TestDecidePhase:
    @pytest.mark.asyncio
    async def test_decide_generates_strategies(self) -> None:
        engine = _make_engine()
        state = CognitiveState(task="Create new API")
        state.observation = Observation(task_description=state.task)
        state.problem_type = "creation"
        state.selected_frameworks = ["first_principles", "inversion"]

        state = await engine._decide(state, {})

        assert len(state.strategies) >= 1
        assert state.current_strategy is not None
        assert state.current_strategy.status == StrategyStatus.EXECUTING

    @pytest.mark.asyncio
    async def test_decide_simple_task_single_strategy(self) -> None:
        """Simple tasks get one direct-execution strategy (Bezos: Bias for Action)."""
        engine = _make_engine()
        state = CognitiveState(task="Look up docs")
        state.problem_type = "simple"
        state.selected_frameworks = ["bias_for_action"]

        state = await engine._decide(state, {})

        assert state.current_strategy.name == "direct_execution"
        assert state.current_strategy.confidence == 0.7

    @pytest.mark.asyncio
    async def test_decide_after_failures_adds_constraint_relaxation(self) -> None:
        """After failed attempts, constraint_relaxation strategy is added."""
        engine = _make_engine()
        state = CognitiveState(task="complex task")
        state.problem_type = "debugging"
        state.selected_frameworks = ["five_whys", "first_principles", "inversion"]
        state.attempted_strategies = [
            Strategy(name="previous", status=StrategyStatus.FAILED),
        ]

        state = await engine._decide(state, {})

        strategy_names = [s.name for s in state.strategies]
        assert "constraint_relaxation" in strategy_names

    @pytest.mark.asyncio
    async def test_decide_strategies_sorted_by_confidence(self) -> None:
        engine = _make_engine()
        state = CognitiveState(task="complex task")
        state.problem_type = "creation"
        state.selected_frameworks = ["first_principles", "inversion"]

        state = await engine._decide(state, {})

        for i in range(len(state.strategies) - 1):
            assert state.strategies[i].confidence >= state.strategies[i + 1].confidence

    @pytest.mark.asyncio
    async def test_decide_with_pre_mortem(self) -> None:
        """When pre_mortem is in frameworks, strategies get risk analysis."""
        engine = _make_engine()
        state = CognitiveState(task="Deploy to production")
        state.observation = Observation(task_description=state.task)
        state.problem_type = "deployment"
        state.selected_frameworks = ["pre_mortem", "first_principles"]

        state = await engine._decide(state, {})

        # At least one strategy should have pre-mortem risks
        has_risks = any(s.pre_mortem_risks for s in state.strategies)
        assert has_risks


# ---- Reflect Phase ----


class TestReflectPhase:
    @pytest.mark.asyncio
    async def test_reflect_on_success_records_lesson(self) -> None:
        engine = _make_engine()
        state = CognitiveState(task="test task")
        state.current_strategy = Strategy(name="first_principles")
        state.problem_type = "creation"
        state.selected_frameworks = ["first_principles"]

        state = await engine._reflect(state, True, "output text", {})

        assert len(state.lessons_learned) == 1
        assert "succeeded" in state.lessons_learned[0]
        assert "first_principles" in state.lessons_learned[0]

    @pytest.mark.asyncio
    async def test_reflect_on_failure_runs_five_whys(self) -> None:
        engine = _make_engine()
        state = CognitiveState(task="write config")
        state.current_strategy = Strategy(name="direct_execution")
        state.problem_type = "creation"
        state.selected_frameworks = ["first_principles"]
        state.action_results = [
            {"success": False, "result": {"error": "Permission denied: /etc/config"}}
        ]

        state = await engine._reflect(state, False, "", {})

        assert len(state.failure_root_causes) > 0
        assert len(state.lessons_learned) > 0
        assert "FAILED" in state.reflections[0]

    @pytest.mark.asyncio
    async def test_reflect_failure_finds_alternatives(self) -> None:
        engine = _make_engine()
        state = CognitiveState(task="write config")
        state.current_strategy = Strategy(name="direct_execution")
        state.problem_type = "creation"
        state.action_results = []

        state = await engine._reflect(state, False, "", {})

        # Should still generate lesson even without error details
        assert len(state.lessons_learned) > 0


# ---- Full OODA Cycle (with mocked ToolUseLoop) ----


class TestOODACycle:
    """Test the full run() async generator with mocked execution."""

    @pytest.mark.asyncio
    async def test_success_on_first_cycle(self) -> None:
        """Happy path: task succeeds on first try."""
        engine = _make_engine()

        async def mock_act(state, messages, system_prompt, model_id, provider):
            yield {"type": "tool_use_response", "content": "Done!"}

        with patch.object(engine, "_act", side_effect=mock_act):
            events = await _collect_events(engine, "Simple task")

        phases = [e["phase"] for e in events if e.get("type") == "cognitive_phase"]
        assert phases == ["observe", "orient", "decide", "act", "reflect"]

        complete = [e for e in events if e.get("type") == "cognitive_complete"]
        assert len(complete) == 1
        assert complete[0]["success"] is True
        assert complete[0]["cycles"] == 1

    @pytest.mark.asyncio
    async def test_strategy_switch_on_failure(self) -> None:
        """When first strategy fails, engine switches to next without re-observing."""
        engine = _make_engine()
        call_count = 0

        async def mock_act(state, messages, system_prompt, model_id, provider):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                yield {"type": "act_failed", "error": "Strategy 1 failed"}
            else:
                yield {"type": "tool_use_response", "content": "Strategy 2 worked!"}

        # Force engine to generate 2 strategies
        async def mock_decide(state, ctx):
            state.strategies = [
                Strategy(name="strategy_a", confidence=0.8, status=StrategyStatus.EXECUTING),
                Strategy(name="strategy_b", confidence=0.6),
            ]
            state.strategy_index = 0
            state.current_strategy = state.strategies[0]
            return state

        with patch.object(engine, "_act", side_effect=mock_act), \
             patch.object(engine, "_decide", side_effect=mock_decide):
            events = await _collect_events(engine, "Complex task")

        # Should see strategy_switch event
        switches = [e for e in events if e.get("type") == "strategy_switch"]
        assert len(switches) == 1
        assert switches[0]["from"] == "strategy_a"
        assert switches[0]["to"] == "strategy_b"

        complete = [e for e in events if e.get("type") == "cognitive_complete"]
        assert complete[0]["success"] is True

    @pytest.mark.asyncio
    async def test_reorient_after_all_strategies_exhausted(self) -> None:
        """When all strategies fail, engine re-observes and re-orients."""
        engine = _make_engine()

        async def mock_act_fail(state, messages, system_prompt, model_id, provider):
            yield {"type": "act_failed", "error": "Failed again"}

        call_count = {"decide": 0}

        async def mock_decide(state, ctx):
            call_count["decide"] += 1
            # First cycle: 1 strategy. Second cycle: 1 strategy (after re-orient)
            state.strategies = [
                Strategy(name=f"attempt_{call_count['decide']}", confidence=0.5, status=StrategyStatus.EXECUTING),
            ]
            state.strategy_index = 0
            state.current_strategy = state.strategies[0]
            return state

        with patch.object(engine, "_act", side_effect=mock_act_fail), \
             patch.object(engine, "_decide", side_effect=mock_decide):
            events = await _collect_events(
                engine, "Impossible task",
                context={"max_cycles": 2},  # not used directly, but engine defaults to 5
            )

        # Should see cognitive_reorient event
        reorients = [e for e in events if e.get("type") == "cognitive_reorient"]
        assert len(reorients) >= 1

        complete = [e for e in events if e.get("type") == "cognitive_complete"]
        assert complete[0]["success"] is False

    @pytest.mark.asyncio
    async def test_max_cycles_guard(self) -> None:
        """Engine stops after max_cycles even if task isn't done."""
        engine = _make_engine()

        async def mock_act_fail(state, messages, system_prompt, model_id, provider):
            yield {"type": "act_failed", "error": "Always fails"}

        with patch.object(engine, "_act", side_effect=mock_act_fail):
            events = await _collect_events(engine, "Never-succeeding task")

        complete = [e for e in events if e.get("type") == "cognitive_complete"]
        assert len(complete) == 1
        assert complete[0]["success"] is False
        assert complete[0]["cycles"] <= 5  # default max_cycles

    @pytest.mark.asyncio
    async def test_phase_progression_always_ordered(self) -> None:
        """Phases always appear in OODA-R order within each cycle."""
        engine = _make_engine()

        async def mock_act_success(state, messages, system_prompt, model_id, provider):
            yield {"type": "tool_use_response", "content": "Done"}

        with patch.object(engine, "_act", side_effect=mock_act_success):
            events = await _collect_events(engine, "Test ordering")

        phases = [e["phase"] for e in events if e.get("type") == "cognitive_phase"]
        expected_order = ["observe", "orient", "decide", "act", "reflect"]
        assert phases == expected_order

    @pytest.mark.asyncio
    async def test_failure_context_accumulates(self) -> None:
        """Each failed cycle adds to attempted_strategies and root_causes."""
        engine = _make_engine()
        cycle_count = 0

        async def mock_act_fail_then_succeed(state, messages, system_prompt, model_id, provider):
            nonlocal cycle_count
            cycle_count += 1
            if cycle_count <= 2:
                yield {"type": "act_failed", "error": f"Error {cycle_count}"}
            else:
                yield {"type": "tool_use_response", "content": "Finally worked!"}

        with patch.object(engine, "_act", side_effect=mock_act_fail_then_succeed):
            events = await _collect_events(engine, "Eventually succeeds")

        complete = [e for e in events if e.get("type") == "cognitive_complete"]
        assert complete[0]["success"] is True
        assert complete[0]["strategies_tried"] >= 2

    @pytest.mark.asyncio
    async def test_no_strategy_falls_through(self) -> None:
        """If decide generates no strategy, engine exits gracefully."""
        engine = _make_engine()

        async def mock_decide_empty(state, ctx):
            state.strategies = []
            state.current_strategy = None
            return state

        with patch.object(engine, "_decide", side_effect=mock_decide_empty):
            events = await _collect_events(engine, "No strategy task")

        # Should still have observe, orient, decide phases
        phases = [e["phase"] for e in events if e.get("type") == "cognitive_phase"]
        assert "observe" in phases
        assert "orient" in phases
        assert "decide" in phases
        # No act phase since no strategy
        assert "act" not in phases


# ---- AGI Mode ----


class TestAGIMode:
    def test_agi_mode_flag_set(self) -> None:
        engine = _make_engine(agi_mode=True)
        assert engine.agi_mode is True

    def test_agi_mode_false_by_default(self) -> None:
        engine = _make_engine()
        assert engine.agi_mode is False


# ---- Integration: Strategy Generation ----


class TestStrategyGeneration:
    @pytest.mark.asyncio
    async def test_creation_problem_gets_first_principles(self) -> None:
        engine = _make_engine()
        state = CognitiveState(task="Build new feature")
        state.selected_frameworks = ["first_principles", "inversion"]

        strategies = await engine._generate_strategies(state)

        names = [s.name for s in strategies]
        assert "first_principles" in names

    @pytest.mark.asyncio
    async def test_simple_problem_gets_direct_execution(self) -> None:
        engine = _make_engine()
        state = CognitiveState(task="Look up docs")
        state.problem_type = "simple"
        state.selected_frameworks = ["bias_for_action"]

        strategies = await engine._generate_strategies(state)

        assert len(strategies) == 1
        assert strategies[0].name == "direct_execution"

    @pytest.mark.asyncio
    async def test_post_failure_adds_constraint_relaxation(self) -> None:
        engine = _make_engine()
        state = CognitiveState(task="Hard task")
        state.problem_type = "debugging"
        state.selected_frameworks = ["five_whys", "first_principles", "inversion"]
        state.attempted_strategies = [Strategy(name="prev", status=StrategyStatus.FAILED)]

        strategies = await engine._generate_strategies(state)

        names = [s.name for s in strategies]
        assert "constraint_relaxation" in names

    @pytest.mark.asyncio
    async def test_empty_frameworks_gets_adaptive(self) -> None:
        """No matching frameworks -> adaptive_execution fallback."""
        engine = _make_engine()
        state = CognitiveState(task="Unknown task")
        state.problem_type = "unknown"
        state.selected_frameworks = []

        strategies = await engine._generate_strategies(state)

        assert len(strategies) >= 1
        assert strategies[0].name == "adaptive_execution"
