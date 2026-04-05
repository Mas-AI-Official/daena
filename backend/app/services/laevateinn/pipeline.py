"""Laevateinn Pipeline -- orchestrates all 7 stages into a single call.

This is the main entry point for the Laevateinn cognitive OS. It wires:
    Stage 1: Deep Comprehension Engine (DCE)
    Stage 2: Dynamic Compute Scaler (DCS)
    Stage 3: Adversarial Model Debate (AMD)
    Stage 4: Recursive Depth Engine (RDE) + CoVe
    Stage 5: Validation Gauntlet
    Stage 6: Jobs Delivery Engine

Stage 7 (Self-Evolution) runs asynchronously after delivery
and is not part of the synchronous pipeline.

Integration with Daena:
    The pipeline is called from chat_orchestrator.py between
    QueryUnderstanding (Stage 3) and LLMStream (Stage 9).
    It wraps the LLM call with Laevateinn intelligence layers.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.laevateinn.comprehension import DeepComprehensionEngine
from app.services.laevateinn.compute_scaler import DynamicComputeScaler
from app.services.laevateinn.debate import AdversarialModelDebate
from app.services.laevateinn.delivery import JobsDeliveryEngine
from app.services.laevateinn.depth_engine import RecursiveDepthEngine
from app.services.laevateinn.types import (
    LaevateinnTrace,
    ComputeProfile,
    DeliveryResult,
    Difficulty,
)
from app.services.laevateinn.validation import ValidationGauntlet

if TYPE_CHECKING:
    from app.services.llm_service import LLMService

logger = get_logger(__name__)


class LaevateinnPipeline:
    """Main Laevateinn v2 cognitive pipeline.

    Orchestrates all stages from comprehension through delivery.
    Adapts compute based on query difficulty (Kahneman routing).

    Usage::

        pipeline = LaevateinnPipeline(llm_service)
        result = await pipeline.process(
            query="Design the auth flow for multi-tenant API",
            model_ids=["deepseek-r1:14b", "qwen2.5:14b-instruct"],
            intent_type="CODING",
        )
        print(result.delivery.response)
        print(result.delivery.confidence_score)

    Args:
        llm_service: Daena's LLM service for model calls.
    """

    def __init__(self, llm_service: LLMService) -> None:
        self._llm = llm_service
        self._dce = DeepComprehensionEngine(llm_service)
        self._dcs = DynamicComputeScaler()
        self._amd = AdversarialModelDebate(llm_service)
        self._rde = RecursiveDepthEngine(llm_service)
        self._gauntlet = ValidationGauntlet(llm_service)
        self._delivery = JobsDeliveryEngine()

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
        """Run the full Laevateinn pipeline on a query.

        Args:
            query: Raw user query.
            model_ids: Available model IDs for the pipeline.
            intent_type: Daena's intent classification.
            system_prompt: Optional system prompt context.
            context: Conversation context for enrichment.
            force_difficulty: Override automatic difficulty.
            skip_stages: Set of stage names to skip (for testing).

        Returns:
            LaevateinnTrace with full pipeline execution trace.
        """
        start = time.perf_counter_ns()
        trace = LaevateinnTrace(query=query)
        skip = skip_stages or set()

        # ── Stage 1: Deep Comprehension ─────────────────────────
        if "dce" not in skip:
            logger.info("apex_stage_1_dce", query=query[:80])
            use_llm = force_difficulty in (Difficulty.HARD, Difficulty.BRUTAL) if force_difficulty else False
            trace.comprehension = await self._dce.comprehend(
                query, use_llm=use_llm, context=context,
            )
            trace.stages_executed.append("dce")

        # ── Stage 2: Dynamic Compute Scaling ────────────────────
        if "dcs" not in skip:
            logger.info("apex_stage_2_dcs")
            trace.compute_profile = self._dcs.scale(
                trace.comprehension,
                intent_type=intent_type,
                available_models=len(model_ids),
                force_difficulty=force_difficulty,
            )
            trace.stages_executed.append("dcs")
        else:
            # Default compute profile
            trace.compute_profile = ComputeProfile(
                difficulty=Difficulty.STANDARD,
                system=__import__("app.services.laevateinn.types", fromlist=["CognitiveSystem"]).CognitiveSystem.SYSTEM_2,
                num_models=1,
                recursion_depth=1,
                validation_level="feynman_only",
                amd_rounds=0,
                target_latency_ms=3000,
            )

        compute = trace.compute_profile

        # ── Stage 3: Adversarial Model Debate ───────────────────
        if "amd" not in skip and model_ids:
            logger.info(
                "apex_stage_3_amd",
                models=len(model_ids),
                amd_rounds=compute.amd_rounds,
            )
            # Use comprehension-enriched query if available
            enriched_query = query
            if trace.comprehension:
                enriched_query = trace.comprehension.real_question or query

            trace.debate = await self._amd.debate(
                enriched_query,
                model_ids,
                compute,
                system_prompt=system_prompt,
            )
            trace.stages_executed.append("amd")

        if not trace.debate or not trace.debate.winner_answer:
            # No answer yet -- pipeline incomplete
            trace.total_latency_ms = int(
                (time.perf_counter_ns() - start) / 1_000_000
            )
            return trace

        answer = trace.debate.winner_answer
        primary_model = trace.debate.winner_model

        # ── Stage 4: Recursive Depth Engine ─────────────────────
        if "rde" not in skip and compute.recursion_depth > 0:
            logger.info(
                "apex_stage_4_rde",
                depth=compute.recursion_depth,
            )
            # Use a different model for verification if available
            ver_model = ""
            for mid in model_ids:
                if mid != primary_model:
                    ver_model = mid
                    break

            trace.depth = await self._rde.recursive_solve(
                trace.comprehension.real_question if trace.comprehension else query,
                answer,
                compute,
                model_id=primary_model,
                verification_model_id=ver_model,
            )
            answer = trace.depth.final_answer
            trace.stages_executed.append("rde")

        # ── Stage 5: Validation Gauntlet ────────────────────────
        if "validation" not in skip and compute.validation_level != "none":
            logger.info("apex_stage_5_validation")
            trace.validation = await self._gauntlet.validate(
                query,
                answer,
                depth_result=trace.depth,
                compute=compute,
                model_id=primary_model,
            )
            trace.stages_executed.append("validation")

            # If validation fails with low confidence, try one more RDE pass
            if (
                trace.validation
                and not trace.validation.passed
                and trace.depth
                and trace.depth.depth_used < compute.recursion_depth
            ):
                logger.info("apex_validation_retry", reason="low_confidence")
                # Additional RDE pass with validation failure context
                retry_depth = await self._rde.recursive_solve(
                    query, answer, compute,
                    model_id=primary_model,
                )
                answer = retry_depth.final_answer
                trace.depth = retry_depth

        # ── Stage 6: Jobs Delivery ──────────────────────────────
        if "delivery" not in skip:
            logger.info("apex_stage_6_delivery")
            trace.delivery = self._delivery.deliver(
                answer,
                query,
                comprehension=trace.comprehension,
                validation=trace.validation,
                depth=trace.depth,
            )
            trace.stages_executed.append("delivery")

        # ── Finalize trace ──────────────────────────────────────
        trace.total_latency_ms = int(
            (time.perf_counter_ns() - start) / 1_000_000
        )

        # Sum up costs
        if trace.debate:
            trace.total_cost_usd += trace.debate.total_cost_usd

        logger.info(
            "apex_pipeline_complete",
            stages=trace.stages_executed,
            difficulty=compute.difficulty.value,
            confidence=trace.delivery.confidence_score if trace.delivery else 0,
            latency_ms=trace.total_latency_ms,
        )

        return trace

    # ── Quick mode for trivial queries ──────────────────────────

    async def quick_answer(
        self,
        query: str,
        model_id: str,
        *,
        system_prompt: str = "",
    ) -> DeliveryResult:
        """Bypass most of Laevateinn for trivial queries (System 1).

        Only runs DCE (heuristic) + single model + delivery.
        Target latency: <1 second.
        """
        # Quick comprehension (heuristic only, no LLM)
        comprehension = await self._dce.comprehend(query, use_llm=False)

        # Single model answer
        from app.services.providers.base import GenerateRequest, LLMMessage

        messages = []
        if system_prompt:
            messages.append(LLMMessage(role="system", content=system_prompt))

        # Use the enriched query from DCE
        enriched = comprehension.real_question or query
        messages.append(LLMMessage(role="user", content=enriched))

        request = GenerateRequest(
            messages=messages,
            model_id=model_id,
            temperature=0.7,
            max_tokens=1024,
        )

        result = await self._llm.generate_direct(request)

        # Quick delivery (no validation)
        return self._delivery.deliver(
            result.content, query, comprehension=comprehension,
        )
