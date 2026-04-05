"""Laevateinn v2 API endpoints -- Mysterious cognitive pipeline.

Exposes the Laevateinn pipeline for:
    - Direct query processing with full trace
    - Quick answers for trivial queries
    - Individual stage access (DCE, DCS, Validation)
    - Pipeline configuration and status

All endpoints require authentication and are rate-limited
by the tenant's subscription tier.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/apex", tags=["apex"])


# ── Request/Response schemas ─────────────────────────────────

class LaevateinnQueryRequest(BaseModel):
    """Request to process a query through the Laevateinn pipeline."""
    query: str = Field(..., min_length=1, max_length=10000)
    model_ids: list[str] = Field(default_factory=list)
    intent_type: str = Field(default="AMBIGUOUS")
    system_prompt: str = Field(default="")
    context: str = Field(default="")
    force_difficulty: str | None = Field(default=None)
    skip_stages: list[str] = Field(default_factory=list)


class LaevateinnQuickRequest(BaseModel):
    """Request for a quick Laevateinn answer (trivial queries)."""
    query: str = Field(..., min_length=1, max_length=5000)
    model_id: str = Field(default="")
    system_prompt: str = Field(default="")


class ComprehensionRequest(BaseModel):
    """Request to run only the Deep Comprehension Engine."""
    query: str = Field(..., min_length=1, max_length=10000)
    use_llm: bool = Field(default=False)
    context: str = Field(default="")


class ComprehensionResponse(BaseModel):
    """Response from the Deep Comprehension Engine."""
    original_query: str
    compressed_query: str
    sub_questions: list[str]
    hidden_assumptions: list[str]
    noise_eliminated: str
    real_question: str
    bloom_level: str
    interpretations: list[dict[str, Any]]
    processing_time_ms: int


class LaevateinnTraceResponse(BaseModel):
    """Response with full Laevateinn pipeline trace."""
    query: str
    stages_executed: list[str]
    difficulty: str | None = None
    cognitive_system: str | None = None
    confidence: float = 0.0
    response: str = ""
    key_points: list[str] = []
    speculative_followups: list[str] = []
    total_latency_ms: int = 0
    total_cost_usd: float = 0.0
    debate_winner: str | None = None
    depth_used: int = 0
    validation_passed: bool | None = None
    validation_failures: list[str] = []


class LaevateinnStatusResponse(BaseModel):
    """Laevateinn pipeline status and configuration."""
    version: str = "2.0"
    codename: str = "Mysterious"
    stages: list[str]
    available_models: list[str]
    capabilities: dict[str, bool]


# ── Endpoints ────────────────────────────────────────────────

@router.post("/process", response_model=LaevateinnTraceResponse)
async def process_query(
    request: LaevateinnQueryRequest,
    user: Any = Depends(get_current_user),
) -> LaevateinnTraceResponse:
    """Process a query through the full Laevateinn cognitive pipeline.

    Runs all 6 stages (DCE, DCS, AMD, RDE, Validation, Delivery)
    with compute allocation based on query difficulty.
    """
    from app.services.laevateinn.pipeline import LaevateinnPipeline
    from app.services.laevateinn.types import Difficulty

    # Resolve force_difficulty
    difficulty = None
    if request.force_difficulty:
        try:
            difficulty = Difficulty(request.force_difficulty.upper())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid difficulty: {request.force_difficulty}. "
                       f"Valid: TRIVIAL, STANDARD, HARD, BRUTAL",
            )

    # Get LLM service from app state
    from app.core.config import get_settings
    # Pipeline will be initialized by the dependency injection system
    # For now, return a placeholder until fully wired
    try:
        # Import at runtime to avoid circular imports
        from app.api.deps import get_llm_service
        llm_service = get_llm_service()

        pipeline = LaevateinnPipeline(llm_service)
        trace = await pipeline.process(
            query=request.query,
            model_ids=request.model_ids,
            intent_type=request.intent_type,
            system_prompt=request.system_prompt,
            context=request.context,
            force_difficulty=difficulty,
            skip_stages=set(request.skip_stages),
        )

        return LaevateinnTraceResponse(
            query=trace.query,
            stages_executed=trace.stages_executed,
            difficulty=trace.compute_profile.difficulty.value if trace.compute_profile else None,
            cognitive_system=trace.compute_profile.system.value if trace.compute_profile else None,
            confidence=trace.delivery.confidence_score if trace.delivery else 0,
            response=trace.delivery.response if trace.delivery else "",
            key_points=trace.delivery.key_points if trace.delivery else [],
            speculative_followups=trace.delivery.speculative_followups if trace.delivery else [],
            total_latency_ms=trace.total_latency_ms,
            total_cost_usd=trace.total_cost_usd,
            debate_winner=trace.debate.winner_model if trace.debate else None,
            depth_used=trace.depth.depth_used if trace.depth else 0,
            validation_passed=trace.validation.passed if trace.validation else None,
            validation_failures=trace.validation.failure_reasons if trace.validation else [],
        )
    except ImportError:
        logger.warning("apex_llm_service_not_available")
        raise HTTPException(
            status_code=503,
            detail="Laevateinn pipeline not fully initialized. LLM service unavailable.",
        )


@router.post("/quick", response_model=LaevateinnTraceResponse)
async def quick_answer(
    request: LaevateinnQuickRequest,
    user: Any = Depends(get_current_user),
) -> LaevateinnTraceResponse:
    """Quick Laevateinn answer for trivial queries (System 1).

    Bypasses AMD, RDE, and full validation. Target: <1 second.
    """
    from app.services.laevateinn.pipeline import LaevateinnPipeline

    try:
        from app.api.deps import get_llm_service
        llm_service = get_llm_service()

        pipeline = LaevateinnPipeline(llm_service)
        result = await pipeline.quick_answer(
            query=request.query,
            model_id=request.model_id or "llama3.1:latest",
            system_prompt=request.system_prompt,
        )

        return LaevateinnTraceResponse(
            query=request.query,
            stages_executed=["dce", "quick_generate", "delivery"],
            difficulty="TRIVIAL",
            cognitive_system="SYSTEM_1",
            confidence=result.confidence_score,
            response=result.response,
            key_points=result.key_points,
            speculative_followups=result.speculative_followups,
        )
    except ImportError:
        raise HTTPException(status_code=503, detail="LLM service unavailable.")


@router.post("/comprehend", response_model=ComprehensionResponse)
async def comprehend_query(
    request: ComprehensionRequest,
    user: Any = Depends(get_current_user),
) -> ComprehensionResponse:
    """Run only the Deep Comprehension Engine on a query.

    Useful for understanding query intent without generating an answer.
    """
    from app.services.laevateinn.comprehension import DeepComprehensionEngine

    dce = DeepComprehensionEngine()
    result = await dce.comprehend(
        request.query,
        use_llm=request.use_llm,
        context=request.context,
    )

    return ComprehensionResponse(
        original_query=result.original_query,
        compressed_query=result.compressed_query,
        sub_questions=result.sub_questions,
        hidden_assumptions=result.hidden_assumptions,
        noise_eliminated=result.noise_eliminated,
        real_question=result.real_question,
        bloom_level=result.bloom_level.value,
        interpretations=[
            {"text": i.text, "probability": i.probability, "reasoning": i.reasoning}
            for i in result.interpretations
        ],
        processing_time_ms=result.processing_time_ms,
    )


@router.get("/status", response_model=LaevateinnStatusResponse)
async def get_apex_status(
    user: Any = Depends(get_current_user),
) -> LaevateinnStatusResponse:
    """Get Laevateinn pipeline status and available capabilities."""
    models: list[str] = []
    try:
        from app.api.deps import get_model_registry
        registry = get_model_registry()
        model_list = await registry.list_all_models()
        models = [m.model_id for m in model_list]
    except Exception:
        pass

    return LaevateinnStatusResponse(
        version="2.0",
        codename="Mysterious",
        stages=[
            "Deep Comprehension Engine (DCE)",
            "Dynamic Compute Scaler (DCS)",
            "Adversarial Model Debate (AMD)",
            "Recursive Depth Engine (RDE)",
            "Validation Gauntlet",
            "Jobs Delivery Engine",
        ],
        available_models=models,
        capabilities={
            "dce": True,
            "dcs": True,
            "amd": len(models) >= 2,
            "rde": True,
            "validation": True,
            "delivery": True,
            "self_evolution": False,  # Phase 4 roadmap
            "speculative_precompute": False,  # Needs background task
        },
    )
