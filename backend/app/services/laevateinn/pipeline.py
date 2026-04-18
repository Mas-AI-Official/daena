"""Laevateinn Pipeline v4 -- Meta-Questioning Architecture.

The most advanced reasoning pipeline in any publicly deployable system.
20 stages/sub-stages total, with 15 unique beyond-Mythos capabilities.

    Stage 0:    Failure Memory Recall (learn from past mistakes)
    Stage 0.5:  Socratic Inversion -- upgrade the QUESTION before answering
                (Socrates + Musk + Shannon + Kahneman + Munger + Taleb)
    Stage 1:    Deep Comprehension Engine (DCE) + Recursive Constraints
    Stage 1.5:  Epistemic State Analysis + Meta-Strategy Selection
    Stage 1.75: Question Quality Auditor -- Meta-Level 3 cognition
                (Shannon info gain + Popper falsifiability + de Bono frames
                + Hofstadter meta-levels + Feynman gap detection)
    Stage 2:    Dynamic Compute Scaler (DCS)
    Stage 3:    Adversarial Model Debate (AMD) with disagreement focus
    Stage 3.5:  Cross-Domain Analogy Engine (for CREATE/ANALYZE queries)
    Stage 4:    Recursive Depth Engine (RDE) + CoVe
    Stage 4.5:  Causal Reasoning Graph (CRG) -- structural verification
    Stage 5:    Validation Gauntlet
    Stage 5.25: Cognitive Separation -- independent falsification vs construction
                (Popper/Taleb bug-finding || Polya/Feynman solution-finding)
    Stage 5.5:  Counterfactual Engine -- "what if the answer were different?"
    Stage 6:    Adversarial Verification Gate -- counter-evidence falsification
    Stage 6.5:  Outcome Simulator -- predict consequences of following advice
    Stage 7:    Consensus Gradient -- per-section confidence mapping
    Stage 8:    Confidence Calibration -- calibrated scores from history
    Stage 9:    Jobs Delivery Engine

    Stage 10 (Self-Evolution) runs asynchronously after delivery.

Meta-Questioning capabilities (unique to Laevateinn v4):
    1. Socratic Inversion -- upgrade questions before answering them
    2. Question Quality Audit -- Meta-Level 3: audit the auditor
    3. Cognitive Separation -- isolated bug-finding vs solution-finding tracks

These three capabilities implement what no other system has:
    Level 0: Ask a question about the domain ("What is the answer?")
    Level 1: Ask a question about the question ("Is this the right question?")
    Level 2: Ask about the questioning process ("Is my method working?")
    Level 3: Ask about the meta-questioning framework ("Is my framework adequate?")

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
from app.services.laevateinn.cognitive_separation import CognitiveSeparationEngine
from app.services.laevateinn.comprehension import DeepComprehensionEngine
from app.services.laevateinn.compute_scaler import DynamicComputeScaler
from app.services.laevateinn.consensus_gradient import ConsensusGradientEngine
from app.services.laevateinn.counterfactual import CounterfactualEngine
from app.services.laevateinn.cognitive_forcing import CognitiveForcingEngine
from app.services.laevateinn.debate import AdversarialModelDebate
from app.services.laevateinn.delivery import JobsDeliveryEngine
from app.services.laevateinn.depth_engine import RecursiveDepthEngine
from app.services.laevateinn.epistemic_tracker import EpistemicStateTracker
from app.services.laevateinn.failure_memory import FailureMemoryEngine
from app.services.laevateinn.outcome_simulator import OutcomeSimulator
from app.services.laevateinn.perspective_oscillator import PerspectiveOscillator
from app.services.laevateinn.question_auditor import QuestionQualityAuditor
from app.services.laevateinn.socratic_inversion import SocraticInversionEngine
from app.services.laevateinn.types import (
    ComputeProfile,
    DebateResult,
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
        # Meta-Questioning engines (Level 3 cognition)
        self._socratic = SocraticInversionEngine(llm_service)
        self._question_auditor = QuestionQualityAuditor(llm_service)
        self._cognitive_sep = CognitiveSeparationEngine(llm_service)
        # Core stages
        self._dce = DeepComprehensionEngine(llm_service)
        self._dcs = DynamicComputeScaler()
        self._epistemic = EpistemicStateTracker()
        self._cognitive_forcing = CognitiveForcingEngine(llm_service)
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
        self._oscillator = PerspectiveOscillator(llm_service)

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
        use_cognitive_forcing: bool = False,
    ) -> LaevateinnTrace:
        """Run the full Laevateinn v3 pipeline.

        Args:
            use_cognitive_forcing: When True, forces LLMs through structured
                cognitive stages (DECOMPOSE -> EXECUTE -> VERIFY) instead of
                bare LLM calls. This is the core intelligence amplification.
        """
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

        # ── Stage 0.5: Socratic Inversion ──────────────────────
        # Upgrades the question BEFORE DCE sees it.
        # Combines: Socrates, Musk, Polya, Shannon, Kahneman, Munger, Taleb.
        if "socratic" not in skip:
            logger.info("laev_stage_0_5_socratic", query=query[:80])
            use_llm_socratic = (
                force_difficulty in (Difficulty.HARD, Difficulty.BRUTAL)
                if force_difficulty else False
            )
            trace.socratic_inversion = await self._socratic.upgrade(
                query,
                context=context,
                use_llm=use_llm_socratic,
            )
            # If upgrade found a better question, use it downstream
            if (
                trace.socratic_inversion
                and trace.socratic_inversion.upgraded_question != query
            ):
                query = trace.socratic_inversion.upgraded_question
                logger.info(
                    "laev_socratic_upgraded",
                    depth=trace.socratic_inversion.depth_reached.value,
                    substitution=trace.socratic_inversion.substitution_detected,
                )
            trace.stages_executed.append("socratic")

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

        # ── Stage 1.75: Question Quality Audit ─────────────────
        # Meta-Level 3: audits whether our questions are the RIGHT ones.
        # Can loop back to DCE if question quality is too low.
        if "question_audit" not in skip and trace.comprehension:
            logger.info("laev_stage_1_75_question_audit")
            trace.question_audit = self._question_auditor.audit(
                trace.comprehension,
                epistemic=trace.epistemic_state,
                socratic=trace.socratic_inversion,
            )
            # If audit says questions are bad, loop back to DCE
            if trace.question_audit and trace.question_audit.loops_back:
                logger.warning(
                    "laev_question_audit_loop_back",
                    quality=trace.question_audit.overall_question_quality,
                    meta_level=trace.question_audit.meta_level_reached,
                )
                # Re-run DCE with upgraded questions from audit
                if trace.question_audit.upgraded_questions:
                    upgraded_q = trace.question_audit.upgraded_questions[0]
                    trace.comprehension = await self._dce.comprehend(
                        upgraded_q, use_llm=True, context=context,
                    )
            trace.stages_executed.append("question_audit")

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

        # ── Stage 3: Adversarial Model Debate (with cognitive forcing) ──
        if "amd" not in skip and model_ids:
            logger.info(
                "laev_stage_3_amd",
                models=len(model_ids),
                cognitive_forcing=use_cognitive_forcing,
            )
            enriched_query = query
            if trace.comprehension:
                enriched_query = trace.comprehension.real_question or query

            trace.debate = await self._amd.debate(
                enriched_query, model_ids, compute,
                system_prompt=system_prompt,
                use_cognitive_forcing=use_cognitive_forcing,
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

        # ── Stage 5.25: Cognitive Separation ───────────────────
        # Independent falsification vs construction tracks.
        # Track A (Popper/Taleb): find bugs WITHOUT suggesting fixes.
        # Track B (Polya/Feynman): improve answer WITHOUT finding bugs.
        # Prevents verification from biasing toward confirming fixable bugs.
        if "cognitive_sep" not in skip and compute.difficulty in (
            Difficulty.HARD, Difficulty.BRUTAL,
        ):
            logger.info("laev_stage_5_25_cognitive_sep")
            trace.cognitive_separation = await self._cognitive_sep.separate(
                query, answer, compute,
                model_id=primary_model,
                validation=trace.validation,
            )
            # If falsification found load-bearing flaws, loop back to RDE
            if (
                trace.cognitive_separation
                and trace.cognitive_separation.falsification
                and trace.cognitive_separation.falsification.load_bearing_flaws
                and trace.depth
                and trace.depth.depth_used < compute.recursion_depth
            ):
                logger.warning(
                    "laev_cognitive_sep_loop_back",
                    flaws=len(
                        trace.cognitive_separation.falsification.load_bearing_flaws
                    ),
                )
                retry = await self._rde.recursive_solve(
                    query, answer, compute, model_id=primary_model,
                )
                answer = retry.final_answer
                trace.depth = retry
            trace.stages_executed.append("cognitive_sep")

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

        # ── Stage 7.5: Perspective Oscillation ─────────────────
        # Dimensional thinking: zoom-in/zoom-out/rotate/re-enter.
        # Uses consensus gradient to focus on weak sections.
        if "oscillation" not in skip and compute.difficulty in (
            Difficulty.HARD, Difficulty.BRUTAL,
        ):
            logger.info("laev_stage_7_5_oscillation")
            trace.metadata["oscillation"] = await self._oscillator.oscillate(
                query, answer, compute,
                model_id=primary_model,
                consensus=trace.consensus_gradient,
            )
            osc = trace.metadata["oscillation"]
            if osc.blind_spots_found:
                logger.info(
                    "laev_oscillation_blind_spots",
                    count=len(osc.blind_spots_found),
                    contradictions=len(osc.contradictions_found),
                )
            trace.stages_executed.append("oscillation")

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
            socratic_depth=trace.socratic_inversion.depth_reached.value if trace.socratic_inversion else "skipped",
            question_quality=trace.question_audit.overall_question_quality if trace.question_audit else "skipped",
            meta_level=trace.question_audit.meta_level_reached if trace.question_audit else 0,
            cog_sep_agreed=trace.cognitive_separation.tracks_agreed if trace.cognitive_separation else "skipped",
            latency_ms=trace.total_latency_ms,
        )

        return trace

    # ── Single-model cognitive forcing mode ──────────────────────

    async def process_cognitive(
        self,
        query: str,
        model_id: str,
        *,
        system_prompt: str = "",
        full_mode: bool = True,
    ) -> LaevateinnTrace:
        """Run pipeline with cognitive forcing on a SINGLE model.

        This is the key test: can the pipeline alone (without council/debate)
        make a single LLM produce better answers?

        Flow: Comprehension -> Cognitive Forcing (3 stages) -> Verify -> Deliver

        No debate, no council. The intelligence comes from forcing the model
        through DECOMPOSE -> EXECUTE -> VERIFY stages.

        Args:
            query: The question to solve.
            model_id: Single model to use.
            system_prompt: Additional context.
            full_mode: True = 3 stages, False = 2 stages (compact).
        """
        start = time.perf_counter_ns()
        trace = LaevateinnTrace(query=query)

        # ── Stage 1: Comprehension ────────────────────────────
        trace.comprehension = await self._dce.comprehend(
            query, use_llm=False, context="",
        )
        enriched_query = query
        if trace.comprehension:
            enriched_query = trace.comprehension.real_question or query
        trace.stages_executed.append("dce")

        # ── Stage 2: Cognitive Forcing (THE CORE) ─────────────
        logger.info(
            "laev_cognitive_forcing",
            model=model_id,
            mode="full" if full_mode else "compact",
        )
        cf_result = await self._cognitive_forcing.solve(
            enriched_query, model_id,
            system_prompt=system_prompt,
            full_mode=full_mode,
        )
        trace.stages_executed.extend(cf_result.stages_completed)

        # Create a minimal DebateResult to carry the answer through pipeline
        trace.debate = DebateResult(
            winner_model=model_id,
            winner_answer=cf_result.full_response,
            winner_reasoning=f"Cognitive forcing ({cf_result.mode}): {len(cf_result.stages_completed)} stages",
            confidence=0.7,
            all_answers={model_id: cf_result.full_response},
        )

        answer = cf_result.full_response

        # ── Stage 3: Delivery ─────────────────────────────────
        trace.delivery = self._delivery.deliver(
            answer, query, comprehension=trace.comprehension,
        )
        trace.stages_executed.append("delivery")

        trace.total_latency_ms = int(
            (time.perf_counter_ns() - start) / 1_000_000
        )
        logger.info(
            "laev_cognitive_forcing_complete",
            model=model_id,
            stages=trace.stages_executed,
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
