"""LLM Service — orchestration layer for multi-provider LLM calls.

Sits between the API layer and provider adapters.  Given a
RoutingDecision (from ModelRouter), this service:

    1. Calls the primary model via its provider adapter
    2. On failure, walks the fallback chain
    3. For COUNCIL mode, fans out to multiple providers in parallel
    4. Tracks cost, latency, and token counts
    5. Publishes events for audit / cost tracking

The service does NOT own routing logic — that's ModelRouter's job.
It does NOT own governance checks — those happen upstream in the
chat service or governance middleware.

Usage::

    llm_service = LLMService(registry)
    response = await llm_service.generate(request, routing_decision)

    async for chunk in llm_service.stream(request, routing_decision):
        yield chunk
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field, replace as _dc_replace
from typing import Any

from app.core.constants import RoutingMode
from app.core.events import event_bus
from app.core.exceptions import ProviderUnavailableError
from app.core.logging import get_logger
from app.services.model_router import ModelCandidate, RoutingDecision
from app.services.providers.base import (
    BaseProvider,
    GenerateRequest,
    LLMChunk,
    LLMResponse,
)

logger = get_logger(__name__)


# ── Response wrapper for multi-model calls ─────────────────────

@dataclass(slots=True)
class OrchestratedResponse:
    """Extended response that includes orchestration metadata.

    Wraps one or more LLMResponse objects (single for STANDARD,
    multiple for COUNCIL) with routing and timing information.
    """

    primary: LLMResponse
    mode: RoutingMode
    routing_decision: RoutingDecision
    council_responses: list[LLMResponse] = field(default_factory=list)
    total_cost_usd: float = 0.0
    total_latency_ms: int = 0
    attempts: int = 1
    fallback_used: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


# ── LLM Service ───────────────────────────────────────────────

class LLMService:
    """Orchestrate LLM calls across providers with fallback + fan-out.

    Requires a ModelRegistry instance for provider lookups.
    The registry must be initialised before the service is used.

    For QUINTESSENCE mode, call ``set_quintessence_engine()`` after
    constructing both LLMService and QuintessenceEngine to wire them.
    """

    def __init__(self, registry: Any) -> None:
        # Type is Any to avoid circular import; expects ModelRegistry
        self._registry = registry
        self._quintessence: Any | None = None  # QuintessenceEngine (late-bound)

    def set_quintessence_engine(self, engine: Any) -> None:
        """Late-bind the QuintessenceEngine to avoid circular dependency.

        Args:
            engine: A QuintessenceEngine instance (typed Any to avoid import).
        """
        self._quintessence = engine

    # ── Public: direct generate (used by Laevateinn pipeline stages) ──

    async def generate_direct(
        self,
        request: GenerateRequest,
    ) -> LLMResponse:
        """Call an LLM provider directly with automatic failover.

        Used by Laevateinn pipeline stages that need a model call without
        going through the full routing/governance stack. If the primary
        provider fails, walks the fallback chain (SOVEREIGN > TACTICAL > LOCAL)
        until one succeeds.

        The health tracker records successes and failures so repeated
        failures trigger circuit breaking (skip the dead provider entirely).
        """
        from app.services.runtimes.health_tracker import get_health_tracker

        tracker = get_health_tracker()

        # Build ordered provider list: requested first, then all others
        providers_to_try: list[tuple[str, BaseProvider]] = []

        if request.model_id:
            primary = self._registry.get_provider_for_model(request.model_id)
            if primary is not None:
                providers_to_try.append((request.model_id, primary))

        # Add all other available providers as fallbacks
        for p_enum in self._registry.available_providers:
            prov = self._registry.get_provider(p_enum)
            if prov is None:
                continue
            # Skip if already in the list
            if any(prov is existing for _, existing in providers_to_try):
                continue
            providers_to_try.append((p_enum.value, prov))

        if not providers_to_try:
            raise ProviderUnavailableError("No LLM providers available for direct call")

        last_error: Exception | None = None

        for provider_id, provider in providers_to_try:
            # Skip providers with open circuit breaker
            if not tracker.is_available(provider_id):
                if tracker.should_probe(provider_id):
                    # Cooldown expired -- allow one probe attempt
                    tracker.enter_half_open(provider_id)
                else:
                    continue

            try:
                # On cross-provider failover, reset model_id so the fallback
                # provider picks its OWN default instead of inheriting the
                # primary's model string. Without this, e.g. a Groq failure
                # on "moonshotai/kimi-k2-instruct" passes that exact model
                # name to Gemini, which builds /v1beta/models/moonshotai/
                # kimi-k2-instruct:generateContent and returns 404. The
                # primary attempt (first entry in providers_to_try) keeps
                # its originally-requested model_id.
                is_failover = providers_to_try[0][0] != provider_id
                if is_failover and request.model_id:
                    # GenerateRequest is a frozen dataclass, use dataclasses.replace
                    failover_request = _dc_replace(request, model_id=None)
                else:
                    failover_request = request

                result = await provider.generate(failover_request)
                tracker.record_success(provider_id)

                # Log if this was a failover (not the first provider)
                if is_failover:
                    logger.info(
                        "llm.failover_used",
                        primary=providers_to_try[0][0],
                        fallback=provider_id,
                        original_model=request.model_id,
                        fallback_model=result.model_id,
                        reason=str(last_error)[:100] if last_error else "primary_unavailable",
                    )

                return result

            except Exception as exc:
                last_error = exc
                error_msg = str(exc)
                category = tracker.classify_error(error_msg)
                tracker.record_failure(provider_id, error_msg, category)

                logger.warning(
                    "llm.direct_provider_failed",
                    provider=provider_id,
                    error=error_msg[:200],
                    category=category.value,
                    remaining=len(providers_to_try) - providers_to_try.index((provider_id, provider)) - 1,
                )

        # All providers failed
        raise ProviderUnavailableError(
            f"All {len(providers_to_try)} providers failed. "
            f"Last error: {last_error}"
        )

    # ── Public: single-shot generate ───────────────────────────

    async def generate(
        self,
        request: GenerateRequest,
        decision: RoutingDecision,
    ) -> OrchestratedResponse:
        """Generate a complete response using the routing decision.

        For STANDARD mode: call primary, fallback on failure.
        For COUNCIL mode: fan out to council_models in parallel.
        For QUINTESSENCE: delegate to Quintessence engine (future).
        """
        start = time.monotonic()

        if decision.mode == RoutingMode.COUNCIL and decision.council_models:
            result = await self._generate_council(request, decision)
        elif decision.mode == RoutingMode.QUINTESSENCE:
            result = await self._generate_quintessence(request, decision)
        else:
            result = await self._generate_with_fallback(request, decision)

        result.total_latency_ms = self._elapsed(start)

        # Publish event for cost tracking / audit
        await self._publish_completion_event(result)

        return result

    # ── Public: streaming ──────────────────────────────────────

    async def stream(
        self,
        request: GenerateRequest,
        decision: RoutingDecision,
    ) -> AsyncIterator[LLMChunk]:
        """Stream response tokens from the selected model.

        Attempts the primary model first.  If the stream fails to
        *start* (connection error, auth failure), tries fallbacks.
        Once tokens have started flowing, mid-stream errors surface
        as an error chunk rather than retrying.

        COUNCIL mode streaming is not supported — falls back to
        primary-only streaming.
        """
        chain = [decision.primary, *decision.fallback_chain]
        last_error: Exception | None = None

        for candidate in chain:
            provider = self._get_provider(candidate)
            if provider is None:
                continue

            adapted = self._adapt_request(request, candidate)

            try:
                async for chunk in provider.stream(adapted):
                    yield chunk
                # Stream completed successfully
                return
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "llm.stream_failed",
                    model=candidate.model_id,
                    provider=candidate.provider.value,
                    error=str(exc),
                )
                # Try next in chain
                continue

        # All candidates exhausted
        if last_error is not None:
            yield LLMChunk(
                content=f"[Error: all providers failed — {last_error}]",
                model_id=decision.primary.model_id,
                provider=decision.primary.provider,
                finish_reason="error",
            )
        else:
            yield LLMChunk(
                content="[Error: no providers available]",
                model_id=decision.primary.model_id,
                provider=decision.primary.provider,
                finish_reason="error",
            )

    # ── Internal: standard generate with fallback ──────────────

    async def _generate_with_fallback(
        self,
        request: GenerateRequest,
        decision: RoutingDecision,
    ) -> OrchestratedResponse:
        """Try primary model, then walk fallback chain on failure."""
        chain = [decision.primary, *decision.fallback_chain]
        attempts = 0
        last_error: Exception | None = None

        for candidate in chain:
            provider = self._get_provider(candidate)
            if provider is None:
                continue

            adapted = self._adapt_request(request, candidate)
            attempts += 1

            try:
                response = await provider.generate(adapted)
                return OrchestratedResponse(
                    primary=response,
                    mode=decision.mode,
                    routing_decision=decision,
                    total_cost_usd=response.cost_usd,
                    attempts=attempts,
                    fallback_used=attempts > 1,
                    metadata={
                        "model": candidate.model_id,
                        "provider": candidate.provider.value,
                    },
                )
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "llm.generate_failed",
                    model=candidate.model_id,
                    provider=candidate.provider.value,
                    error=str(exc),
                    attempt=attempts,
                )

        # All candidates exhausted
        error_msg = str(last_error) if last_error else "no healthy providers"
        logger.error("llm.all_failed", attempts=attempts, error=error_msg)
        raise ProviderUnavailableError(
            f"All {attempts} provider(s) failed: {error_msg}"
        )

    # ── Internal: council fan-out ──────────────────────────────

    async def _generate_council(
        self,
        request: GenerateRequest,
        decision: RoutingDecision,
    ) -> OrchestratedResponse:
        """Call multiple models in parallel for COUNCIL mode.

        Each council model gets the same request.  Failures are
        logged but don't block other models — we proceed with
        whatever responses we get.  If ALL fail, raises.

        The synthesis step (merging multiple responses into one
        coherent answer) is handled by the Council Engine, not here.
        This method just collects the raw responses.
        """
        tasks: list[tuple[ModelCandidate, asyncio.Task[LLMResponse]]] = []

        for candidate in decision.council_models:
            provider = self._get_provider(candidate)
            if provider is None:
                continue
            adapted = self._adapt_request(request, candidate)
            task = asyncio.create_task(provider.generate(adapted))
            tasks.append((candidate, task))

        if not tasks:
            raise ProviderUnavailableError(
                "No providers available for council mode"
            )

        responses: list[LLMResponse] = []
        total_cost = 0.0

        gather_results = await asyncio.gather(
            *[t for _, t in tasks], return_exceptions=True,
        )
        for (candidate, _), result in zip(tasks, gather_results):
            if isinstance(result, BaseException):
                logger.warning(
                    "llm.council_member_failed",
                    model=candidate.model_id,
                    provider=candidate.provider.value,
                    error=str(result),
                )
                continue
            responses.append(result)
            total_cost += result.cost_usd

        if not responses:
            raise ProviderUnavailableError(
                "All council members failed to respond"
            )

        # Primary is the first successful response; rest are council
        primary = responses[0]
        council_rest = responses[1:] if len(responses) > 1 else []

        return OrchestratedResponse(
            primary=primary,
            mode=RoutingMode.COUNCIL,
            routing_decision=decision,
            council_responses=council_rest,
            total_cost_usd=total_cost,
            attempts=len(tasks),
            metadata={
                "council_size": len(responses),
                "council_requested": len(decision.council_models),
                "council_failed": len(tasks) - len(responses),
            },
        )

    # ── Internal: quintessence deliberation ──────────────────

    async def _generate_quintessence(
        self,
        request: GenerateRequest,
        decision: RoutingDecision,
    ) -> OrchestratedResponse:
        """Run Quintessence expert × LLM matrix deliberation.

        1. Fan out to council models (reuse _generate_council logic).
        2. Delegate to QuintessenceEngine for expert synthesis.
        3. Wrap the result as an OrchestratedResponse.

        Falls back to standard generate if QuintessenceEngine is not wired
        or the council fan-out returns no responses.
        """
        if self._quintessence is None:
            logger.warning(
                "llm.quintessence_not_wired",
                fallback="standard",
            )
            result = await self._generate_with_fallback(request, decision)
            result.mode = RoutingMode.STANDARD
            return result

        # Step 1: Collect raw responses from council models
        if not decision.council_models:
            result = await self._generate_with_fallback(request, decision)
            result.mode = RoutingMode.STANDARD
            return result

        council_result = await self._generate_council(request, decision)
        raw_responses = [council_result.primary, *council_result.council_responses]

        if not raw_responses:
            result = await self._generate_with_fallback(request, decision)
            result.mode = RoutingMode.STANDARD
            return result

        # Step 2: Extract intent from request metadata (default AMBIGUOUS)
        query_intent = (request.metadata or {}).get("intent", "AMBIGUOUS")
        query_text = ""
        for msg in reversed(request.messages):
            if msg.role == "user":
                query_text = msg.content
                break

        # Step 3: Delegate to QuintessenceEngine
        try:
            qr = await self._quintessence.deliberate(
                query=query_text,
                responses=raw_responses,
                query_intent=query_intent,
            )

            # Build a synthetic LLMResponse for the meta-synthesis
            synthesis_response = LLMResponse(
                content=qr.synthesis,
                model_id="quintessence-synthesis",
                provider=decision.primary.provider,
                cost_usd=qr.total_cost_usd,
                token_count_input=0,
                token_count_output=0,
            )

            return OrchestratedResponse(
                primary=synthesis_response,
                mode=RoutingMode.QUINTESSENCE,
                routing_decision=decision,
                council_responses=raw_responses,
                total_cost_usd=council_result.total_cost_usd + qr.total_cost_usd,
                attempts=council_result.attempts,
                metadata={
                    "quintessence_confidence": qr.confidence,
                    "quintessence_agreement": qr.meta_agreement,
                    "expert_count": len(qr.expert_syntheses),
                    "council_size": len(raw_responses),
                    "intent": query_intent,
                },
            )
        except Exception:
            logger.exception("llm.quintessence_failed")
            # Degrade to council result (already have it)
            return council_result

    # ── Helpers ────────────────────────────────────────────────

    def _get_provider(self, candidate: ModelCandidate) -> BaseProvider | None:
        """Look up the provider instance from the registry."""
        provider = self._registry.get_provider(candidate.provider)
        if provider is None:
            logger.debug(
                "llm.provider_not_available",
                provider=candidate.provider.value,
            )
        return provider

    @staticmethod
    def _adapt_request(
        request: GenerateRequest, candidate: ModelCandidate,
    ) -> GenerateRequest:
        """Override model_id on the request to match the candidate."""
        if request.model_id == candidate.model_id:
            return request
        return GenerateRequest(
            messages=request.messages,
            model_id=candidate.model_id,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            top_p=request.top_p,
            stop_sequences=request.stop_sequences,
            system_prompt=request.system_prompt,
            stream=request.stream,
            metadata=request.metadata,
        )

    async def _publish_completion_event(
        self, result: OrchestratedResponse,
    ) -> None:
        """Publish an event for cost tracking and audit."""
        try:
            await event_bus.publish(
                "llm.completion",
                model_id=result.primary.model_id,
                provider=result.primary.provider.value,
                mode=result.mode.value,
                cost_usd=result.total_cost_usd,
                latency_ms=result.total_latency_ms,
                input_tokens=result.primary.token_count_input,
                output_tokens=result.primary.token_count_output,
                fallback_used=result.fallback_used,
                attempts=result.attempts,
            )
        except Exception:
            # Event publishing must never break the response flow
            logger.exception("llm.event_publish_failed")

    @staticmethod
    def _elapsed(start: float) -> int:
        return int((time.monotonic() - start) * 1000)
