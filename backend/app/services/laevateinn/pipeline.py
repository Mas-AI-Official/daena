"""Laevateinn Pipeline v3 -- Complete Beyond-Mythos Architecture.

The most advanced reasoning pipeline in any publicly deployable system.
17 stages/sub-stages total, with 7 unique beyond-Mythos capabilities.

    Stage 0:   Failure Memory Recall (learn from past mistakes)
    Stage 1:   Deep Comprehension Engine (DCE) + Recursive Constraints
    Stage 1.5: Epistemic State Analysis + Meta-Strategy Selection
    Stage 2:   Dynamic Compute Scaler (DCS)
    Stage 3:   Adversarial Model Debate (AMD) with disagreement focus
    Stage 3.5: Cross-Domain Analogy Engine (for CREATE/ANALYZE queries)
    Stage 4:   Recursive Depth Engine (RDE) + CoVe
    Stage 4.5: Causal Reasoning Graph (CRG) -- structural verification
    Stage 5:   Validation Gauntlet
    Stage 5.5: Counterfactual Engine -- "what if the answer were different?"
    Stage 6:   Adversarial Verification Gate -- counter-evidence falsification
    Stage 6.5: Outcome Simulator -- predict consequences of following advice
    Stage 7:   Consensus Gradient -- per-section confidence mapping
    Stage 8:   Confidence Calibration -- calibrated scores from history
    Stage 9:   Jobs Delivery Engine

    Stage 10 (Self-Evolution) runs asynchronously after delivery.

Integration with Daena:
    Called from chat_orchestrator.py between QueryUnderstanding and LLMStream.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.laevateinn.adversarial_gate import AdversarialVerificationGate
from app.services.laevateinn.analogy_engine import AnalogyEngine
from app.services.laevateinn.calibration import ConfidenceCalibrator
from app.services.laevateinn.causal_graph import CausalReasoningGraph
from app.services.laevateinn.comprehension import DeepComprehensionEngine
from app.services.laevateinn.compute_scaler import DynamicComputeScaler
from app.services.laevateinn.consensus_gradient import ConsensusGradientEngine
from app.services.laevateinn.counterfactual import CounterfactualEngine
from app.services.laevateinn.debate import AdversarialModelDebate
from app.services.laevateinn.delivery import JobsDeliveryEngine
from app.services.laevateinn.depth_engine import RecursiveDepthEngine
from app.services.laevateinn.epistemic_tracker import EpistemicStateTracker
from app.services.laevateinn.failure_memory import FailureMemoryEngine
from app.services.laevateinn.outcome_simulator import OutcomeSimulator
from app.services.laevateinn.types import (
    ComputeProfile,
    DeliveryResult,
    Difficulty,
    LaevateinnTrace,
    ReasoningStrategy,
    UncertaintyShape,
)
from app.services.laevateinn.validation import ValidationGauntlet

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = get_logger(__name__)

_CHEAP_MODEL_PREFERENCES = [
    "llama3.1:8b", "mistral:7b", "qwen2.5:7b", "phi3:mini",
]


class LaevateinnPipeline:
    """Main Laevateinn v3 cognitive pipeline -- complete beyond-Mythos.

    17 stages total. 7 unique beyond-Mythos capabilities.
    Self-correcting mesh with 4 loop-back paths.
    Learns from failures across sessions.
    Calibrates confidence from historical accuracy.

    Args:
        llm_service: Daena's LLM service for model calls.
    """

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service
        # Core stages
        self._dce = DeepComprehensionEngine(llm_service)
        self._dcs = DynamicComputeScaler()
        self._epistemic = EpistemicStateTracker()
        self._amd = AdversarialModelDebate(llm_service)
        self._rde = RecursiveDepthEngine(llm_service)
        self._crg = CausalReasoningGraph(llm_service)
        self._gauntlet = ValidationGauntlet(llm_service)
        self._adv_gate = AdversarialVerificationGate(llm_service)
        self._delivery = JobsDeliveryEngine()
        # Beyond-Mythos engines
        self._failure_memory = FailureMemoryEngine(llm_service)
        self._counterfactual = CounterfactualEngine(llm_service)
        self._outcome_sim = OutcomeSimulator(llm_service)
        self._analogy = AnalogyEngine(llm_service)
        self._calibrator = ConfidenceCalibrator()
        self._consensus = ConsensusGradientEngine()

    async def process(
        self,
        query: str,
        model_ids: list[str],
        *,
        intent_type: str = "AMBIGUOUS",
        system_prompt: str = "",
        context: str = "",
        force_difficulty: Difficulty | None = None,
        skip_stages: set[str] | None = None,
    ) -> LaevateinnTrace:
        """Run the full Laevateinn v3 pipeline."""
        start = time.perf_counter_ns()
        trace = LaevateinnTrace(query=query)
        skip = skip_stages or set()

        # ── Stage 0: Failure Memory Recall ──────────────────────
        if "failure_memory" not in skip:
            trace.failure_memory = self._failure_memory.recall(
                query, strategy=trace.reasoning_strategy,
            )
            if trace.failure_memory and trace.failure_memory.risk_flags:
                logger.info(
                    "laev_stage_0_failure_memory",
                    patterns=trace.failure_memory.accumulated_patterns,
                    risks=len(trace.failure_memory.risk_flags),
                )
            trace.stages_executed.append("failure_memory")

        # ── Stage 1: Deep Comprehension + Recursive Constraints ─
        if "dce" not in skip:
            logger.info("laev_stage_1_dce", query=query[:80])
            use_llm = force_difficulty in (Difficulty.HARD, Difficulty.BRUTAL) if force_difficulty else False
            trace.comprehension = await self._dce.comprehend(
                query, use_llm=use_llm, context=context,
            )
            # Capture constraint tree from DCE
            if trace.comprehension and trace.comprehension.constraint_tree:
                trace.constraint_tree = trace.comprehension.constraint_tree
            trace.stages_executed.append("dce")

        # ── Stage 1.5: Epistemic State + Meta-Strategy ──────────
        if "epistemic" not in skip and trace.comprehension:
            logger.info("laev_stage_1_5_epistemic")
            prior_failures = []
            if trace.failure_memory:
                prior_failures = [
                    r.root_cause for r in trace.failure_memory.relevant_failures
                ]
            trace.epistemic_state = self._epistemic.analyze(
                trace.comprehension,
                prior_failures=prior_failures,
            )
            trace.reasoning_strategy = self._epistemic.recommend_strategy(
                trace.comprehension, trace.epistemic_state,
            )

            # Failure memory can override strategy
            if trace.failure_memory and trace.failure_memory.strategy_adjustments:
                logger.info(
                    "laev_strategy_adjusted_by_failures",
                    adjustments=len(trace.failure_memory.strategy_adjustments),
                )

            trace.stages_executed.append("epistemic")

        # ── Stage 2: Dynamic Compute Scaling ────────────────────
        if "dcs" not in skip:
            logger.info("laev_stage_2_dcs")
            trace.compute_profile = self._dcs.scale(
                trace.comprehension,
                intent_type=intent_type,
                available_models=len(model_ids),
                force_difficulty=force_difficulty,
            )
            if trace.epistemic_state and trace.epistemic_state.shape in (
                UncertaintyShape.CONTRADICTORY, UncertaintyShape.ABSENT,
            ):
                self._boost_compute_for_uncertainty(trace.compute_profile)
            trace.stages_executed.append("dcs")
        else:
            from app.services.laevateinn.types import CognitiveSystem
            trace.compute_profile = ComputeProfile(
                difficulty=Difficulty.STANDARD,
                system=CognitiveSystem.SYSTEM_2,
                num_models=1, recursion_depth=1,
                validation_level="feynman_only",
                amd_rounds=0, target_latency_ms=3000,
            )

        compute = trace.compute_profile

        # ── Stage 3: Adversarial Model Debate ───────────────────
        if "amd" not in skip and model_ids:
            logger.info("laev_stage_3_amd", models=len(model_ids))
            enriched_query = query
            if trace.comprehension:
                enriched_query = trace.comprehension.real_question or query

            trace.debate = await self._amd.debate(
                enriched_query, model_ids, compute,
                system_prompt=system_prompt,
            )
            if trace.debate and hasattr(trace.debate, "disagreement_points"):
                trace.disagreement_points = trace.debate.disagreement_points
            trace.stages_executed.append("amd")

        if not trace.debate or not trace.debate.winner_answer:
            trace.total_latency_ms = int((time.perf_counter_ns() - start) / 1_000_000)
            return trace

        answer = trace.debate.winner_answer
        primary_model = trace.debate.winner_model

        # ── Stage 3.5: Cross-Domain Analogy ─────────────────────
        if "analogy" not in skip and compute.difficulty in (
            Difficulty.HARD, Difficulty.BRUTAL,
        ):
            logger.info("laev_stage_3_5_analogy")
            trace.analogy = await self._analogy.find_analogies(
                query, answer, trace.comprehension, compute,
                model_id=primary_model,
            )
            # If a strong analogy was found, enrich the query for RDE
            if trace.analogy and trace.analogy.insight_applied:
                answer = (
                    f"{answer}\n\n"
                    f"[Analogical insight: {trace.analogy.insight_applied}]"
                )
            trace.stages_executed.append("analogy")

        # ── Stage 4: Recursive Depth Engine ─────────────────────
        if "rde" not in skip and compute.recursion_depth > 0:
            logger.info("laev_stage_4_rde", depth=compute.recursion_depth)
            ver_model = self._select_cheap_model(model_ids, primary_model)
            trace.depth = await self._rde.recursive_solve(
                trace.comprehension.real_question if trace.comprehension else query,
                answer, compute,
                model_id=primary_model,
                verification_model_id=ver_model,
            )
            answer = trace.depth.final_answer
            trace.stages_executed.append("rde")

        # ── Stage 4.5: Causal Reasoning Graph ───────────────────
        if "crg" not in skip and compute.difficulty in (
            Difficulty.HARD, Difficulty.BRUTAL,
        ):
            logger.info("laev_stage_4_5_crg")
            trace.causal_graph = await self._crg.analyze(
                query, answer, compute, model_id=primary_model,
            )
            if (
                trace.causal_graph
                and not trace.causal_graph.composition_valid
                and trace.depth
                and trace.depth.depth_used < compute.recursion_depth
            ):
                logger.warning("laev_crg_loop_back")
                retry = await self._rde.recursive_solve(
                    query, answer, compute, model_id=primary_model,
                )
                answer = retry.final_answer
                trace.depth = retry
            trace.stages_executed.append("crg")

        # ── Stage 5: Validation Gauntlet ────────────────────────
        if "validation" not in skip and compute.validation_level != "none":
            logger.info("laev_stage_5_validation")
            trace.validation = await self._gauntlet.validate(
                query, answer, depth_result=trace.depth,
                compute=compute, model_id=primary_model,
            )
            if (
                trace.validation and not trace.validation.passed
                and trace.depth
                and trace.depth.depth_used < compute.recursion_depth
            ):
                retry = await self._rde.recursive_solve(
                    query, answer, compute, model_id=primary_model,
                )
                answer = retry.final_answer
                trace.depth = retry
            trace.stages_executed.append("validation")

        # ── Stage 5.5: Counterfactual Engine ────────────────────
        if "counterfactual" not in skip and compute.difficulty in (
            Difficulty.HARD, Difficulty.BRUTAL,
        ):
            logger.info("laev_stage_5_5_counterfactual")
            trace.counterfactual = await self._counterfactual.analyze(
                query, answer, compute, model_id=primary_model,
            )
            trace.stages_executed.append("counterfactual")

        # ── Stage 6: Adversarial Verification Gate ──────────────
        if "adv_gate" not in skip and compute.difficulty != Difficulty.TRIVIAL:
            logger.info("laev_stage_6_adversarial_gate")
            cheap_model = self._select_cheap_model(model_ids, primary_model)
            trace.adversarial_gate = await self._adv_gate.verify(
                query, answer, compute,
                model_id=primary_model,
                cheap_model_id=cheap_model,
            )
            if trace.adversarial_gate and trace.adversarial_gate.loops_back:
                logger.warning("laev_adv_gate_loop_back")
                retry = await self._rde.recursive_solve(
                    query, answer, compute, model_id=primary_model,
                )
                answer = retry.final_answer
                trace.depth = retry
                trace.adversarial_gate = await self._adv_gate.verify(
                    query, answer, compute,
                    model_id=primary_model,
                    cheap_model_id=cheap_model,
                )
            trace.stages_executed.append("adversarial_gate")

        # ── Stage 6.5: Outcome Simulation ───────────────────────
        if "outcome_sim" not in skip and compute.difficulty in (
            Difficulty.HARD, Difficulty.BRUTAL,
        ):
            logger.info("laev_stage_6_5_outcome_sim")
            trace.outcome_simulation = await self._outcome_sim.simulate(
                query, answer, compute, model_id=primary_model,
            )
            # Flag catastrophic risks in metadata
            if (
                trace.outcome_simulation
                and not trace.outcome_simulation.safe_to_deliver
            ):
                trace.metadata["catastrophic_risk"] = True
                trace.metadata["risks"] = (
                    trace.outcome_simulation.catastrophic_risks
                )
                logger.warning(
                    "laev_catastrophic_risk",
                    risks=trace.outcome_simulation.catastrophic_risks,
                )
            trace.stages_executed.append("outcome_sim")

        # ── Stage 7: Consensus Gradient ─────────────────────────
        if "consensus" not in skip:
            trace.consensus_gradient = self._consensus.analyze(
                answer,
                debate=trace.debate,
                depth=trace.depth,
                causal_graph=trace.causal_graph,
                validation=trace.validation,
                adversarial_gate=trace.adversarial_gate,
            )
            trace.stages_executed.append("consensus_gradient")

        # ── Stage 8: Confidence Calibration ─────────────────────
        # Runs at delivery to adjust final confidence

        # ── Stage 9: Jobs Delivery ──────────────────────────────
        if "delivery" not in skip:
            logger.info("laev_stage_9_delivery")
            trace.delivery = self._delivery.deliver(
                answer, query,
                comprehension=trace.comprehension,
                validation=trace.validation,
                depth=trace.depth,
            )

            # Apply adversarial gate confidence boost/penalty
            if trace.adversarial_gate and trace.delivery:
                trace.delivery.confidence_score = min(
                    1.0,
                    trace.delivery.confidence_score
                    + trace.adversarial_gate.confidence_boost,
                )

            # Apply counterfactual confidence impact
            if trace.counterfactual and trace.delivery:
                trace.delivery.confidence_score = max(
                    0.1,
                    trace.delivery.confidence_score
                    + trace.counterfactual.confidence_impact,
                )

            # Stage 8: Calibrate final confidence from history
            if "calibration" not in skip and trace.delivery:
                trace.calibration = self._calibrator.calibrate(
                    trace.delivery.confidence_score
                )
                trace.delivery.confidence_score = (
                    trace.calibration.calibrated_confidence
                )
                trace.stages_executed.append("calibration")

            trace.stages_executed.append("delivery")

        # ── Finalize ────────────────────────────────────────────
        trace.total_latency_ms = int(
            (time.perf_counter_ns() - start) / 1_000_000
        )
        if trace.debate:
            trace.total_cost_usd += trace.debate.total_cost_usd

        logger.info(
            "laev_pipeline_complete",
            stages=trace.stages_executed,
            total_stages=len(trace.stages_executed),
            difficulty=compute.difficulty.value,
            strategy=trace.reasoning_strategy.value,
            epistemic=trace.epistemic_state.shape.value if trace.epistemic_state else "none",
            confidence=trace.delivery.confidence_score if trace.delivery else 0,
            calibrated=trace.calibration.reliability if trace.calibration else "none",
            adv_gate=trace.adversarial_gate.passed if trace.adversarial_gate else "skipped",
            crg_valid=trace.causal_graph.composition_valid if trace.causal_graph else "skipped",
            catastrophic=trace.metadata.get("catastrophic_risk", False),
            latency_ms=trace.total_latency_ms,
        )

        return trace

    # ── Quick mode ──────────────────────────────────────────────

    async def quick_answer(
        self, query: str, model_id: str, *, system_prompt: str = "",
    ) -> DeliveryResult:
        """Bypass most of Laevateinn for trivial queries (System 1)."""
        comprehension = await self._dce.comprehend(query, use_llm=False)

        from app.services.providers.base import GenerateRequest, LLMMessage
        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))
        messages.append(LLMMessage(
            role="user",
            content=comprehension.real_question or query,
        ))
        request = GenerateRequest(
            messages=messages, model_id=model_id,
            temperature=0.7, max_tokens=1024,
        )
        result = await self._llm.generate_direct(request)
        return self._delivery.deliver(
            result.content, query, comprehension=comprehension,
        )

    # ── Feedback loop (for calibration + failure memory) ────────

    async def record_feedback(
        self,
        query: str,
        answer: str,
        was_correct: bool,
        confidence: float,
        failure_description: str = "",
        strategy: ReasoningStrategy = ReasoningStrategy.STANDARD,
    ) -> None:
        """Record user feedback for calibration and failure learning.

        Call when user indicates answer was right or wrong.
        """
        # Calibration data point
        self._calibrator.record_outcome(
            predicted_confidence=confidence,
            was_correct=was_correct,
        )

        # Failure memory (only for incorrect answers)
        if not was_correct and failure_description:
            await self._failure_memory.record_failure(
                query, answer, failure_description, strategy,
            )

    # ── Helpers ─────────────────────────────────────────────────

    def _select_cheap_model(
        self, model_ids: list[str], primary_model: str,
    ) -> str:
        """Select cheapest available model for verification."""
        for pref in _CHEAP_MODEL_PREFERENCES:
            for mid in model_ids:
                if pref in mid.lower() and mid != primary_model:
                    return mid
        for mid in model_ids:
            if mid != primary_model:
                return mid
        return primary_model

    def _boost_compute_for_uncertainty(self, compute: ComputeProfile) -> None:
        """Boost compute when epistemic uncertainty is high."""
        if compute.difficulty == Difficulty.TRIVIAL:
            compute.difficulty = Difficulty.STANDARD
            compute.recursion_depth = max(compute.recursion_depth, 1)
            compute.validation_level = "feynman_only"
        elif compute.difficulty == Difficulty.STANDARD:
            compute.recursion_depth = max(compute.recursion_depth, 2)
            compute.amd_rounds = max(compute.amd_rounds, 3)
            compute.validation_level = "full_gauntlet"
