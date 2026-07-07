"""OODAEngine -- Daena's cognitive loop.

OODA-R: Observe -> Orient -> Decide -> Act -> Reflect

This is THE brain. Every task flows through this loop. It wraps the
existing ToolUseLoop with philosophical reasoning frameworks that make
Daena actually intelligent, not just a tool runner.

Key design:
    - OBSERVE: gather actual state (not assumed) -- Map != Territory
    - ORIENT: select reasoning frameworks via MetaReasoner -- Munger's Latticework
    - DECIDE: generate + score strategies -- Dalio's Believability, Pre-mortem
    - ACT: execute via ToolUseLoop with classification + loop detection
    - REFLECT: learn from outcome -- Reflexion, Anti-Fragility, 5 Whys on failure

On failure: doesn't retry the same approach. Runs 5 Whys to find root cause,
ConstraintAnalyzer to relax soft constraints, then tries a different strategy.
This is what Mythos does -- creative problem-solving, not brute force retries.

Integrates existing services (does NOT duplicate):
    - DeepThink -> used in Orient phase for extended reasoning
    - Council/Quintessence -> used in Decide phase for multi-model scoring
    - LearningService -> used in Reflect phase for pattern extraction
    - SelfAudit -> used in Reflect phase for self-evaluation
    - Memory (NBMF) -> used in Observe for context, Reflect for storage
    - SkillRefinery -> used when tools need to be created on the fly
    - Autopilot -> enables unstoppable AGI mode

BACKGROUND PATH ONLY when doing reflection/learning -- hot path is Act.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from app.core.logging import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class CognitivePhase(str, Enum):
    OBSERVE = "observe"
    ORIENT = "orient"
    DECIDE = "decide"
    ACT = "act"
    REFLECT = "reflect"


class StrategyStatus(str, Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABANDONED = "abandoned"  # switched to different strategy


@dataclass
class Observation:
    """What we ACTUALLY know (not assumed) about the current state."""
    task_description: str
    workspace_root: str | None = None
    file_states: dict[str, str] = field(default_factory=dict)
    system_state: dict[str, Any] = field(default_factory=dict)
    error_context: str | None = None
    prior_attempts: list[dict[str, Any]] = field(default_factory=list)
    memory_context: list[dict[str, Any]] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


@dataclass
class Strategy:
    """A candidate approach to solving the task."""
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    name: str = ""
    description: str = ""
    steps: list[str] = field(default_factory=list)
    frameworks_used: list[str] = field(default_factory=list)
    confidence: float = 0.5  # 0.0 to 1.0
    risk_level: str = "medium"  # low, medium, high
    reversible: bool = True
    pre_mortem_risks: list[str] = field(default_factory=list)
    status: StrategyStatus = StrategyStatus.PENDING


@dataclass
class CognitiveState:
    """The brain's working memory for a single task."""
    task_id: str = field(default_factory=lambda: str(uuid4())[:8])
    task: str = ""
    phase: CognitivePhase = CognitivePhase.OBSERVE
    cycle: int = 0
    max_cycles: int = 5

    # OBSERVE output
    observation: Observation | None = None

    # ORIENT output
    problem_type: str = "unknown"
    selected_frameworks: list[str] = field(default_factory=list)
    orientation_analysis: str = ""

    # DECIDE output
    strategies: list[Strategy] = field(default_factory=list)
    current_strategy: Strategy | None = None
    strategy_index: int = 0

    # ACT output
    action_results: list[dict[str, Any]] = field(default_factory=list)
    tool_calls_made: list[dict[str, Any]] = field(default_factory=list)

    # REFLECT output
    reflections: list[str] = field(default_factory=list)
    lessons_learned: list[str] = field(default_factory=list)
    failure_root_causes: list[str] = field(default_factory=list)

    # History across cycles
    attempted_strategies: list[Strategy] = field(default_factory=list)
    cycle_history: list[dict[str, Any]] = field(default_factory=list)

    @property
    def has_more_strategies(self) -> bool:
        return self.strategy_index < len(self.strategies) - 1

    @property
    def has_more_cycles(self) -> bool:
        return self.cycle < self.max_cycles


@dataclass
class CognitiveResult:
    """Final output of a cognitive run."""
    task_id: str
    success: bool
    output: str = ""
    strategies_tried: int = 0
    cycles_used: int = 0
    tool_calls: int = 0
    lessons_learned: list[str] = field(default_factory=list)
    frameworks_used: list[str] = field(default_factory=list)
    root_causes_found: list[str] = field(default_factory=list)
    execution_events: list[dict[str, Any]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# The Brain
# ---------------------------------------------------------------------------

class OODAEngine:
    """The main cognitive loop.

    Wraps ToolUseLoop with observe/orient/decide/act/reflect phases.
    Each phase uses existing Daena services -- no duplication.

    Usage::

        engine = OODAEngine(db, user_id, tenant_id)
        result = await engine.run(task, context)
    """

    def __init__(
        self,
        db: Any,
        user_id: UUID,
        tenant_id: UUID,
        *,
        agi_mode: bool = False,
        session_id: UUID | None = None,
        workspace_root: str | None = None,
    ) -> None:
        self.db = db
        self.user_id = user_id
        self.tenant_id = tenant_id
        self.agi_mode = agi_mode
        self.session_id = session_id
        self.workspace_root = workspace_root

        # Lazy imports to avoid circular deps -- wired at call time
        self._meta_reasoner = None
        self._five_whys = None
        self._constraint_analyzer = None
        self._pre_mortem = None
        self._learning_service = None
        self._pattern_memory = None

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        messages: list[Any] | None = None,
        system_prompt: str = "",
        model_id: str = "llama3.1:latest",
        provider: str = "ollama",
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute the full OODA-R loop for a task.

        Yields SSE events including tool calls, results, cognitive state
        updates, and the final response.
        """
        ctx = context or {}
        state = CognitiveState(task=task)

        while state.has_more_cycles:
            state.cycle += 1
            logger.info(
                "ooda.cycle_start",
                task_id=state.task_id,
                cycle=state.cycle,
                phase="observe",
            )

            # --- OBSERVE ---
            state.phase = CognitivePhase.OBSERVE
            yield {"type": "cognitive_phase", "phase": "observe", "cycle": state.cycle}
            state = await self._observe(state, ctx)

            # --- ORIENT ---
            state.phase = CognitivePhase.ORIENT
            yield {"type": "cognitive_phase", "phase": "orient", "cycle": state.cycle}
            state = await self._orient(state, ctx)

            # --- DECIDE ---
            state.phase = CognitivePhase.DECIDE
            yield {"type": "cognitive_phase", "phase": "decide", "cycle": state.cycle}
            state = await self._decide(state, ctx)

            if not state.current_strategy:
                # No strategy generated -- fall through to direct execution
                logger.warning("ooda.no_strategy", task_id=state.task_id)
                break

            # --- ACT ---
            state.phase = CognitivePhase.ACT
            yield {"type": "cognitive_phase", "phase": "act", "cycle": state.cycle}

            act_success = False
            final_output = ""
            async for event in self._act(state, messages, system_prompt, model_id, provider):
                yield event
                if event.get("type") == "tool_use_response":
                    final_output = event.get("content", "")
                    act_success = True
                elif event.get("type") == "tool_loop_complete":
                    # Loop finished -- check if we got a response
                    pass
                elif event.get("type") == "act_failed":
                    act_success = False
                    final_output = event.get("error", "")

            # --- REFLECT ---
            state.phase = CognitivePhase.REFLECT
            yield {"type": "cognitive_phase", "phase": "reflect", "cycle": state.cycle}
            state = await self._reflect(state, act_success, final_output, ctx)

            # Record cycle
            state.cycle_history.append({
                "cycle": state.cycle,
                "strategy": state.current_strategy.name if state.current_strategy else "none",
                "success": act_success,
                "frameworks": state.selected_frameworks,
            })

            if act_success:
                # Goal achieved
                yield {
                    "type": "cognitive_complete",
                    "success": True,
                    "cycles": state.cycle,
                    "strategies_tried": len(state.attempted_strategies),
                    "lessons": state.lessons_learned,
                }
                return

            # Failed -- try next strategy or re-orient
            if state.current_strategy:
                state.current_strategy.status = StrategyStatus.FAILED
                state.attempted_strategies.append(state.current_strategy)

            if state.has_more_strategies:
                # Try next pre-generated strategy
                state.strategy_index += 1
                state.current_strategy = state.strategies[state.strategy_index]
                state.current_strategy.status = StrategyStatus.EXECUTING
                logger.info(
                    "ooda.strategy_switch",
                    task_id=state.task_id,
                    new_strategy=state.current_strategy.name,
                    reason="previous_failed",
                )
                yield {
                    "type": "strategy_switch",
                    "from": state.attempted_strategies[-1].name,
                    "to": state.current_strategy.name,
                    "reason": "Previous approach failed. Trying alternative.",
                }
                # Skip back to ACT with new strategy (don't re-observe/orient)
                continue

            # No more strategies -- re-orient with failure context
            if state.has_more_cycles:
                yield {
                    "type": "cognitive_reorient",
                    "reason": "All strategies exhausted. Re-analyzing problem.",
                    "cycle": state.cycle,
                }
                # Reset for next cycle -- observe/orient will use failure data
                state.strategies = []
                state.strategy_index = 0
                state.current_strategy = None
                continue

        # Exhausted all cycles
        yield {
            "type": "cognitive_complete",
            "success": False,
            "cycles": state.cycle,
            "strategies_tried": len(state.attempted_strategies),
            "root_causes": state.failure_root_causes,
            "lessons": state.lessons_learned,
            "message": "Task requires human input or a fundamentally different approach.",
        }

    # ------------------------------------------------------------------
    # OBSERVE: What is ACTUALLY true? (Map != Territory)
    # ------------------------------------------------------------------

    async def _observe(self, state: CognitiveState, ctx: dict) -> CognitiveState:
        """Gather actual state. Never assume -- verify.

        Uses:
            - QueryUnderstanding (intent, complexity, risk)
            - NBMF Memory (prior context)
            - Actual file/system state checks
        """
        observation = Observation(
            task_description=state.task,
            workspace_root=self.workspace_root,
        )

        # Recall relevant memories
        try:
            from app.services.memory import MemoryService
            memory_svc = MemoryService(self.db, self.user_id, self.tenant_id)
            memories = await memory_svc.recall(state.task, limit=5)
            observation.memory_context = [
                {"tier": m.tier, "content": m.content[:500]}
                for m in memories
            ] if memories else []
        except Exception as exc:
            logger.debug("ooda.memory_recall_skipped", error=str(exc))

        # Include prior attempt context (for re-observe after failure)
        if state.attempted_strategies:
            observation.prior_attempts = [
                {
                    "strategy": s.name,
                    "status": s.status.value,
                    "frameworks": s.frameworks_used,
                }
                for s in state.attempted_strategies
            ]

        # ResourceFinder (Einstein): When Daena doesn't know something,
        # she searches for it -- memory, workspace, web -- then saves it.
        try:
            from app.services.cognition.resource_finder import ResourceFinder
            finder = ResourceFinder(self.db, self.user_id, self.tenant_id)
            knowledge = await finder.find(
                state.task,
                context=ctx,
                workspace_root=self.workspace_root,
            )
            if knowledge and knowledge.answer:
                observation.system_state["resource_knowledge"] = {
                    "answer": knowledge.answer[:500],
                    "source": knowledge.source,
                    "confidence": knowledge.confidence,
                }
                # Persist knowledge to NBMF so we never search for this again
                if knowledge.should_persist:
                    await finder.persist_knowledge(knowledge)
                logger.info(
                    "ooda.resource_found",
                    source=knowledge.source,
                    confidence=knowledge.confidence,
                )
        except Exception as exc:
            logger.debug("ooda.resource_finder_skipped", error=str(exc))

        state.observation = observation
        return state

    # ------------------------------------------------------------------
    # ORIENT: What does this mean? Which frameworks apply?
    # ------------------------------------------------------------------

    async def _orient(self, state: CognitiveState, ctx: dict) -> CognitiveState:
        """Classify the problem and select reasoning frameworks.

        Uses:
            - MetaReasoner (framework selection -- Munger's Latticework)
            - DeepThink (extended reasoning for complex problems)
            - Quintessence DCPs (expert lenses)
        """
        meta = self._get_meta_reasoner()

        # Classify problem type
        state.problem_type = await meta.classify_problem(
            state.task,
            prior_failures=[s.name for s in state.attempted_strategies],
            observation=state.observation,
        )

        # Select frameworks
        state.selected_frameworks = await meta.select_frameworks(
            state.problem_type,
            prior_failures=[s.name for s in state.attempted_strategies],
        )

        # WeaknessTracker (Ericsson): Check if this problem type is a known
        # weakness. If so, adjust strategy -- practice what we're bad at.
        weakness_note = ""
        try:
            from app.services.cognition.weakness_tracker import (
                build_weakness_note,
                get_weakness_tracker,
            )
            tracker = get_weakness_tracker(self.tenant_id)
            weakness_note = await build_weakness_note(tracker, state.problem_type)
        except Exception as exc:
            logger.debug("ooda.weakness_tracker_skipped", error=str(exc))

        # Build orientation analysis
        state.orientation_analysis = (
            f"Problem type: {state.problem_type}. "
            f"Frameworks: {', '.join(state.selected_frameworks)}. "
            f"Prior attempts: {len(state.attempted_strategies)}."
            f"{weakness_note}"
        )

        logger.info(
            "ooda.orient",
            task_id=state.task_id,
            problem_type=state.problem_type,
            frameworks=state.selected_frameworks,
        )

        return state

    # ------------------------------------------------------------------
    # DECIDE: What strategy to use? (Believability + Pre-mortem)
    # ------------------------------------------------------------------

    async def _decide(self, state: CognitiveState, ctx: dict) -> CognitiveState:
        """Generate and score strategies. Pick the best one.

        Uses:
            - First Principles (decompose to fundamentals)
            - Inversion (what would cause failure?)
            - Pre-mortem (imagine failure before executing)
            - Believability weighting (track record scoring)
            - Council/Quintessence (multi-model evaluation for high-risk)
        """
        # Generate candidate strategies via LLM
        strategies = await self._generate_strategies(state)

        if not strategies:
            # Fallback: create a simple direct-execution strategy
            strategies = [Strategy(
                name="direct_execution",
                description=f"Execute task directly: {state.task}",
                steps=["Execute the task as stated"],
                frameworks_used=["bias_for_action"],
                confidence=0.5,
                reversible=True,
            )]

        # Run pre-mortem on each strategy (imagine failure before it happens)
        if "pre_mortem" in state.selected_frameworks:
            pre_mortem = self._get_pre_mortem()
            for strategy in strategies:
                risks = await pre_mortem.analyze(strategy, state)
                strategy.pre_mortem_risks = risks

        # Score and rank
        strategies.sort(key=lambda s: s.confidence, reverse=True)

        state.strategies = strategies
        state.strategy_index = 0
        state.current_strategy = strategies[0]
        state.current_strategy.status = StrategyStatus.EXECUTING

        logger.info(
            "ooda.decide",
            task_id=state.task_id,
            strategy=state.current_strategy.name,
            confidence=state.current_strategy.confidence,
            alternatives=len(strategies) - 1,
        )

        return state

    # ------------------------------------------------------------------
    # ACT: Execute the strategy (ToolUseLoop)
    # ------------------------------------------------------------------

    async def _act(
        self,
        state: CognitiveState,
        messages: list[Any] | None,
        system_prompt: str,
        model_id: str,
        provider: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute the chosen strategy via ToolUseLoop.

        Uses:
            - ToolUseLoop (core execution)
            - ToolCallClassifier (gates each call)
            - LoopDetector (prevents spinning)
        """
        from app.services.tool_use_loop import ToolUseLoop

        # Inject strategy + cognitive context into system prompt
        strategy_context = ""
        if state.current_strategy and state.current_strategy.name != "direct_execution":
            strategy_context = (
                f"\n\n[COGNITIVE STRATEGY: {state.current_strategy.name}]\n"
                f"Description: {state.current_strategy.description}\n"
                f"Steps: {'; '.join(state.current_strategy.steps)}\n"
                f"Frameworks: {', '.join(state.current_strategy.frameworks_used)}\n"
            )
            if state.current_strategy.pre_mortem_risks:
                strategy_context += (
                    f"Risks to watch: {'; '.join(state.current_strategy.pre_mortem_risks)}\n"
                )

        # Inject the specific reasoning frameworks selected by MetaReasoner
        if state.selected_frameworks:
            from app.services.cognition.cognitive_reasoner import FRAMEWORK_PROMPTS
            strategy_context += "\n[ACTIVE REASONING LENSES]\n"
            for fw_name in state.selected_frameworks[:5]:
                if fw_name in FRAMEWORK_PROMPTS:
                    strategy_context += f"- {FRAMEWORK_PROMPTS[fw_name]}\n"
            strategy_context += "Apply these lenses to every decision in this task.\n"

        # Include orientation analysis if available
        if state.orientation_analysis:
            strategy_context += (
                f"\n[SITUATION ANALYSIS]\n{state.orientation_analysis[:500]}\n"
            )

        # Include failure context if we're retrying
        failure_context = ""
        if state.attempted_strategies:
            failure_context = "\n\n[PRIOR ATTEMPTS - DO NOT REPEAT THESE]\n"
            for s in state.attempted_strategies:
                failure_context += f"- {s.name}: FAILED\n"
            if state.failure_root_causes:
                failure_context += f"Root causes found: {'; '.join(state.failure_root_causes)}\n"
            failure_context += "Use a DIFFERENT approach.\n"

        enhanced_prompt = system_prompt + strategy_context + failure_context

        loop = ToolUseLoop(
            self.db,
            self.user_id,
            self.tenant_id,
            agi_mode=self.agi_mode,
            session_id=self.session_id,
        )

        msgs = messages or []
        try:
            async for event in loop.run(
                msgs,
                enhanced_prompt,
                model_id,
                provider,
            ):
                # Track tool calls for reflection
                if event.get("type") == "tool_call":
                    state.tool_calls_made.append(event)
                elif event.get("type") == "tool_result":
                    state.action_results.append(event)
                yield event
        except Exception as exc:
            logger.error("ooda.act_failed", error=str(exc), task_id=state.task_id)
            yield {"type": "act_failed", "error": str(exc)}

    # ------------------------------------------------------------------
    # REFLECT: Did it work? What did we learn? (Reflexion + Anti-Fragility)
    # ------------------------------------------------------------------

    async def _reflect(
        self,
        state: CognitiveState,
        success: bool,
        output: str,
        ctx: dict,
    ) -> CognitiveState:
        """Evaluate outcome and extract lessons.

        On success:
            - Extract pattern for future use (Compounding Knowledge -- Buffett)
            - Store in NBMF T1 (Working memory, 7 day)

        On failure:
            - Run 5 Whys to find root cause (Toyota)
            - Run ConstraintAnalyzer to find alternative paths (Mythos)
            - Update strategy scores (Dalio Believability)
            - Make the system STRONGER from this failure (Taleb Anti-Fragility)
        """
        if success:
            # Success reflection
            lesson = (
                f"Strategy '{state.current_strategy.name}' succeeded for "
                f"problem type '{state.problem_type}' using frameworks "
                f"{state.selected_frameworks}."
            )
            state.lessons_learned.append(lesson)
            state.reflections.append(f"CYCLE {state.cycle}: SUCCESS - {lesson}")

            # Store pattern via LearningService (existing service)
            try:
                from app.services.learning_service import ActionOutcome
                learning = await self._get_learning_service()
                await learning.track_outcome(ActionOutcome(
                    action_id=state.task_id,
                    session_id=str(self.session_id or "cognitive"),
                    agent="cognitive_engine",
                    operation=state.current_strategy.name if state.current_strategy else "unknown",
                    params={"problem_type": state.problem_type, "frameworks": state.selected_frameworks},
                    success=True,
                    output_preview=f"Strategy '{state.current_strategy.name}' succeeded",
                    duration_ms=0,
                ))
            except Exception as exc:
                logger.debug("ooda.learning_record_skipped", error=str(exc))

        else:
            # Failure reflection -- this is where the MAGIC happens
            reflection_parts = []

            # 1. Toyota 5 Whys -- drill to root cause
            if state.action_results:
                last_error = ""
                for r in reversed(state.action_results):
                    if not r.get("success", True):
                        last_error = str(r.get("result", {}).get("error", ""))
                        break
                if last_error:
                    five_whys = self._get_five_whys()
                    root_cause = await five_whys.analyze(
                        task=state.task,
                        error=last_error,
                        strategy=state.current_strategy.name if state.current_strategy else "",
                        context=state.observation,
                    )
                    state.failure_root_causes.append(root_cause)
                    reflection_parts.append(f"Root cause: {root_cause}")

            # 2. Constraint Probe (Mythos method) -- decompose the constraint,
            # find which channels are actually blocked vs assumed blocked
            try:
                from app.services.cognition.constraint_probe import ConstraintProbe
                probe = ConstraintProbe()
                probe_result = await probe.probe(
                    task=state.task,
                    constraint=state.current_strategy.name if state.current_strategy else "",
                    error=last_error if state.action_results else "",
                )
                if probe_result.open_channels:
                    open_names = [c.name for c in probe_result.open_channels[:3]]
                    reflection_parts.append(
                        f"Constraint probe found {len(probe_result.open_channels)} open channels: "
                        f"{', '.join(open_names)}"
                    )
                    if probe_result.recommended_path:
                        reflection_parts.append(
                            f"Recommended path: {probe_result.recommended_path.description}"
                        )
            except Exception as probe_exc:
                logger.debug("ooda.constraint_probe_skipped", error=str(probe_exc))

            # 3. Constraint relaxation -- what soft constraints can we drop?
            constraint_analyzer = self._get_constraint_analyzer()
            alternatives = await constraint_analyzer.find_alternatives(
                task=state.task,
                failed_approach=state.current_strategy.name if state.current_strategy else "",
                root_causes=state.failure_root_causes,
            )
            if alternatives:
                reflection_parts.append(
                    f"Alternative approaches found: {', '.join(alternatives)}"
                )

            lesson = (
                f"Strategy '{state.current_strategy.name if state.current_strategy else 'unknown'}' "
                f"FAILED for '{state.problem_type}'. "
                + " ".join(reflection_parts)
            )
            state.lessons_learned.append(lesson)
            state.reflections.append(f"CYCLE {state.cycle}: FAILURE - {lesson}")

            logger.info(
                "ooda.reflect_failure",
                task_id=state.task_id,
                root_causes=state.failure_root_causes,
                alternatives=alternatives,
            )

        # KnowledgeHunter: On failure, actively search for solutions
        # This is Einstein's razor: "I don't need to know everything,
        # I just need to know where to find it."
        if not success and state.failure_root_causes:
            try:
                from app.services.cognition.knowledge_hunter import KnowledgeHunter
                hunter = KnowledgeHunter(self.db, self.user_id, self.tenant_id)
                hunt_result = await hunter.hunt_for_failure(
                    task=state.task,
                    error=state.failure_root_causes[-1],
                    strategy_tried=state.current_strategy.name if state.current_strategy else "",
                    domain=state.problem_type,
                )
                if hunt_result.found:
                    state.lessons_learned.append(
                        f"Knowledge found online: {hunt_result.knowledge[:300]}"
                    )
                    reflection_parts.append(
                        f"Web research found solution (confidence {hunt_result.confidence:.0%}): "
                        f"{hunt_result.knowledge[:200]}"
                    )
                    logger.info(
                        "ooda.knowledge_hunt_success",
                        depth=hunt_result.search_depth,
                        sources=len(hunt_result.sources),
                        skill_saved=hunt_result.skill_extracted,
                    )
            except Exception as exc:
                logger.debug("ooda.knowledge_hunt_skipped", error=str(exc))

        # WeaknessTracker: Record this outcome for deliberate practice tracking
        try:
            from app.services.cognition.weakness_tracker import get_weakness_tracker
            tracker = get_weakness_tracker(self.tenant_id)
            await tracker.record(
                problem_type=state.problem_type,
                strategy=state.current_strategy.name if state.current_strategy else "",
                tools_used=[],
                success=success,
                error=state.failure_root_causes[-1] if state.failure_root_causes else "",
            )
        except Exception as exc:
            logger.debug("ooda.weakness_record_skipped", error=str(exc))

        # SelfUpgrader (Taleb Anti-Fragility): Check if this experience
        # reveals a new cognitive pattern worth adopting.
        # Only run periodically (every 5 cycles) to avoid overhead.
        if state.cycle >= 3 or (success and state.cycle > 1):
            try:
                from app.services.cognition.self_upgrader import SelfUpgrader
                upgrader = SelfUpgrader(self.db, self.user_id, self.tenant_id)
                history = [
                    {
                        "strategy": s.name,
                        "success": s.status == StrategyStatus.SUCCEEDED,
                        "frameworks": s.frameworks_used,
                        "problem_type": state.problem_type,
                    }
                    for s in state.attempted_strategies
                ]
                if state.current_strategy:
                    history.append({
                        "strategy": state.current_strategy.name,
                        "success": success,
                        "frameworks": state.current_strategy.frameworks_used,
                        "problem_type": state.problem_type,
                    })
                candidates = await upgrader.discover_from_history(history)
                if candidates:
                    for c in candidates:
                        state.lessons_learned.append(
                            f"New cognitive skill discovered: '{c.name}' -- {c.description}"
                        )
                    logger.info(
                        "ooda.self_upgrade_candidates",
                        count=len(candidates),
                        names=[c.name for c in candidates],
                    )
            except Exception as exc:
                logger.debug("ooda.self_upgrader_skipped", error=str(exc))

        # Durable experience sink: persist what this reflection learned so it
        # survives the request. LearningService above is in-memory only; this
        # row is what with_experience_history rehydrates from on later turns.
        await self._store_experience(state, success, output)

        return state

    async def _get_learning_service(self) -> Any:
        """LearningService rehydrated from this tenant's durable experience log.

        Falls back to a fresh in-memory instance if history cannot be loaded
        (Rule 17 -- reflection must never fail because history is unavailable).
        """
        from app.services.learning_service import LearningService
        try:
            return await LearningService.with_experience_history(self.db, self.tenant_id)
        except Exception as exc:
            logger.debug("ooda.learning_history_skipped", error=str(exc))
            return LearningService()

    async def _store_experience(
        self,
        state: CognitiveState,
        success: bool,
        action_taken: str,
    ) -> None:
        """Persist one reflect outcome to the durable experience_log table.

        Best-effort by design: a storage failure is logged and swallowed so it
        can never break the cognitive loop. Deliberately constructs nothing
        beyond the row itself (no MemoryService or other subsystems), so a
        disabled memory subsystem cannot make persisted experience vanish.
        Flush, not commit: the owning request/session decides the transaction.
        """
        try:
            from app.models.experience import ExperienceLog

            meta: dict[str, Any] = {
                "problem_type": state.problem_type,
                "frameworks": list(state.selected_frameworks or []),
                "cycle": state.cycle,
            }
            if state.failure_root_causes:
                meta["root_causes"] = list(state.failure_root_causes)[-3:]

            row = ExperienceLog(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                session_id=self.session_id,
                phase="reflect",
                situation=(state.task or "")[:500],
                decision=state.current_strategy.name if state.current_strategy else None,
                action_taken=(action_taken or "")[:1000],
                outcome="success" if success else "failure",
                reward=1.0 if success else 0.0,
                meta=meta,
            )
            self.db.add(row)
            await self.db.flush()
        except Exception as exc:
            logger.warning("ooda.experience_store_failed", error=str(exc))

    # ------------------------------------------------------------------
    # Strategy generation
    # ------------------------------------------------------------------

    async def _generate_strategies(self, state: CognitiveState) -> list[Strategy]:
        """Generate candidate strategies using selected frameworks.

        For simple tasks: 1 strategy (Bias for Action -- Bezos)
        For complex tasks: 3 strategies ranked by confidence
        """
        # Simple task heuristic: if no prior failures and low complexity
        if not state.attempted_strategies and state.problem_type in ("simple", "search", "lookup"):
            return [Strategy(
                name="direct_execution",
                description=f"Execute directly: {state.task}",
                steps=["Execute as stated"],
                frameworks_used=["bias_for_action"],
                confidence=0.7,
                reversible=True,
            )]

        strategies = []

        # Strategy 1: First Principles approach
        if "first_principles" in state.selected_frameworks:
            strategies.append(Strategy(
                name="first_principles",
                description="Decompose to fundamental truths, rebuild from atoms",
                steps=[
                    "List all assumptions about this task",
                    "Identify which assumptions are provably true vs assumed",
                    "Remove false assumptions",
                    "Build solution from remaining truths only",
                ],
                frameworks_used=["first_principles", "occams_razor"],
                confidence=0.7,
                reversible=True,
            ))

        # Strategy 2: Inversion approach
        if "inversion" in state.selected_frameworks:
            strategies.append(Strategy(
                name="inversion",
                description="Ask what would cause failure, then prevent those",
                steps=[
                    "List all ways this task could fail",
                    "For each failure mode: is it preventable?",
                    "Build solution that prevents all failure modes",
                    "Execute with safeguards",
                ],
                frameworks_used=["inversion", "pre_mortem"],
                confidence=0.65,
                reversible=True,
            ))

        # Strategy 3: Constraint relaxation (Mythos-style creative)
        if state.attempted_strategies:  # Only after failures
            strategies.append(Strategy(
                name="constraint_relaxation",
                description="Challenge assumed constraints, find creative path",
                steps=[
                    "List all constraints preventing success",
                    "Classify each as HARD (governance) vs SOFT (assumption)",
                    "Relax soft constraints",
                    "Find alternative path that only respects hard constraints",
                ],
                frameworks_used=["constraint_relaxation", "reality_distortion"],
                confidence=0.6,
                reversible=True,
            ))

        # If no frameworks matched, create a default
        if not strategies:
            strategies.append(Strategy(
                name="adaptive_execution",
                description="Execute with observation and adaptation",
                steps=["Observe state", "Execute step by step", "Adapt on failure"],
                frameworks_used=["ooda", "bias_for_action"],
                confidence=0.5,
                reversible=True,
            ))

        return strategies

    # ------------------------------------------------------------------
    # Lazy service access (avoids circular imports)
    # ------------------------------------------------------------------

    def _get_meta_reasoner(self):
        if not self._meta_reasoner:
            from app.services.cognition.meta_reasoner import MetaReasoner
            self._meta_reasoner = MetaReasoner()
        return self._meta_reasoner

    def _get_five_whys(self):
        if not self._five_whys:
            from app.services.cognition.five_whys import FiveWhys
            self._five_whys = FiveWhys()
        return self._five_whys

    def _get_constraint_analyzer(self):
        if not self._constraint_analyzer:
            from app.services.cognition.constraint_analyzer import ConstraintAnalyzer
            self._constraint_analyzer = ConstraintAnalyzer()
        return self._constraint_analyzer

    def _get_pre_mortem(self):
        if not self._pre_mortem:
            from app.services.cognition.pre_mortem import PreMortem
            self._pre_mortem = PreMortem()
        return self._pre_mortem
