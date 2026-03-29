"""Cost Estimator: per-runtime cost estimation and tracking.

Estimates task cost before execution (for CostPreflight) and tracks
actual cost after execution (for audit). Each runtime has different
pricing: Ollama is free, Claude Code uses Anthropic pricing, Codex
uses OpenAI pricing, etc.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CostEstimate:
    """Pre-execution cost estimate for governance check."""
    runtime_id: str
    estimated_tokens: int
    estimated_cost_usd: float
    confidence: float  # 0.0-1.0, how confident the estimate is
    breakdown: dict[str, float]  # e.g. {"input": 0.01, "output": 0.02}
    is_free: bool = False


# Known pricing per runtime (USD per 1K tokens, approximate).
# Updated as runtimes change pricing.
RUNTIME_PRICING: dict[str, dict[str, float]] = {
    "claude_code": {
        "input_per_1k": 0.003,   # Sonnet-level
        "output_per_1k": 0.015,
        "description": "Anthropic Claude Code CLI (Pro/Max subscription)",
    },
    "codex": {
        "input_per_1k": 0.003,   # Codex pricing
        "output_per_1k": 0.012,
        "description": "OpenAI Codex CLI",
    },
    "gemini_cli": {
        "input_per_1k": 0.00025,  # Gemini Flash pricing
        "output_per_1k": 0.001,
        "description": "Google Gemini CLI",
    },
    "grok_cli": {
        "input_per_1k": 0.005,
        "output_per_1k": 0.015,
        "description": "xAI Grok CLI",
    },
    "ollama": {
        "input_per_1k": 0.0,
        "output_per_1k": 0.0,
        "description": "Local Ollama (free, runs on user hardware)",
    },
    "mcp_bridge": {
        "input_per_1k": 0.0,
        "output_per_1k": 0.0,
        "description": "MCP Server (cost depends on underlying tool)",
    },
}


class CostEstimator:
    """Estimates and tracks runtime execution costs."""

    def __init__(self) -> None:
        self._pricing = dict(RUNTIME_PRICING)
        self._session_totals: dict[str, float] = {}  # session_id -> total_usd

    def estimate(
        self,
        runtime_id: str,
        estimated_tokens: int,
        input_ratio: float = 0.3,
    ) -> CostEstimate:
        """Estimate cost before execution.

        Args:
            runtime_id: Which runtime will execute.
            estimated_tokens: Estimated total tokens (input + output).
            input_ratio: Fraction of tokens that are input (default 30%).

        Returns:
            CostEstimate with breakdown.
        """
        pricing = self._pricing.get(runtime_id, {})
        input_per_1k = pricing.get("input_per_1k", 0.0)
        output_per_1k = pricing.get("output_per_1k", 0.0)

        input_tokens = int(estimated_tokens * input_ratio)
        output_tokens = estimated_tokens - input_tokens

        input_cost = (input_tokens / 1000) * input_per_1k
        output_cost = (output_tokens / 1000) * output_per_1k
        total = input_cost + output_cost

        is_free = (input_per_1k == 0 and output_per_1k == 0)

        return CostEstimate(
            runtime_id=runtime_id,
            estimated_tokens=estimated_tokens,
            estimated_cost_usd=round(total, 6),
            confidence=0.7 if not is_free else 1.0,
            breakdown={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "input_cost_usd": round(input_cost, 6),
                "output_cost_usd": round(output_cost, 6),
            },
            is_free=is_free,
        )

    def record_actual(
        self,
        session_id: str,
        runtime_id: str,
        actual_input_tokens: int,
        actual_output_tokens: int,
    ) -> float:
        """Record actual cost after execution.

        Returns:
            Actual cost in USD.
        """
        pricing = self._pricing.get(runtime_id, {})
        input_cost = (actual_input_tokens / 1000) * pricing.get("input_per_1k", 0.0)
        output_cost = (actual_output_tokens / 1000) * pricing.get("output_per_1k", 0.0)
        total = round(input_cost + output_cost, 6)

        self._session_totals[session_id] = (
            self._session_totals.get(session_id, 0.0) + total
        )

        return total

    def session_total(self, session_id: str) -> float:
        """Get cumulative cost for a session."""
        return self._session_totals.get(session_id, 0.0)

    def update_pricing(self, runtime_id: str, pricing: dict[str, float]) -> None:
        """Update pricing for a runtime (e.g., when API costs change)."""
        self._pricing[runtime_id] = pricing
        logger.info(
            "cost_estimator.pricing_updated",
            runtime_id=runtime_id,
            input_per_1k=pricing.get("input_per_1k"),
            output_per_1k=pricing.get("output_per_1k"),
        )
