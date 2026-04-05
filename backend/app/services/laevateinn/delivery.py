"""Stage 6: Jobs Delivery Engine + Speculative Pre-computation.

Formats the validated answer for delivery:
    - Max 3 key points (unless depth requested)
    - Remove hedges, replace with confidence scores
    - Format matched to cognitive load
    - Predict 3 follow-up questions (Speculative Pre-computation)

Named after Steve Jobs: "Design is not just what it looks like.
Design is how it works." The delivery layer shapes HOW the answer
reaches the user.
"""

from __future__ import annotations

import re
import time

from app.core.logging import get_logger
from app.services.laevateinn.types import (
    ComprehensionResult,
    DeliveryResult,
    DepthResult,
    ValidationResult,
)

logger = get_logger(__name__)

# Hedge phrases to replace with direct language
_HEDGE_REPLACEMENTS: list[tuple[str, str]] = [
    (r"\bI think\b", ""),
    (r"\bI believe\b", ""),
    (r"\bprobably\b", "likely"),
    (r"\bmaybe\b", ""),
    (r"\bperhaps\b", ""),
    (r"\bit seems like\b", ""),
    (r"\bit appears that\b", ""),
    (r"\bI'm not sure but\b", ""),
    (r"\bcould potentially\b", "can"),
    (r"\bmight possibly\b", "may"),
    (r"\bto be honest\b", ""),
    (r"\bin my opinion\b", ""),
    (r"\bI would say\b", ""),
]


class JobsDeliveryEngine:
    """Stage 6 of APEX: format and deliver the answer.

    Responsible for:
        1. Removing hedging language
        2. Extracting key points
        3. Adding confidence scores
        4. Matching format to query type
        5. Generating speculative follow-up predictions
    """

    def deliver(
        self,
        answer: str,
        query: str,
        comprehension: ComprehensionResult | None = None,
        validation: ValidationResult | None = None,
        depth: DepthResult | None = None,
    ) -> DeliveryResult:
        """Format answer for delivery.

        Args:
            answer: The validated answer from the pipeline.
            query: Original query for context.
            comprehension: DCE output for format matching.
            validation: Gauntlet output for confidence.
            depth: RDE output for confidence.

        Returns:
            DeliveryResult with formatted response and metadata.
        """
        start = time.perf_counter_ns()

        # Step 1: Remove hedges
        clean_answer = self._remove_hedges(answer)

        # Step 2: Extract key points
        key_points = self._extract_key_points(clean_answer)

        # Step 3: Calculate confidence
        confidence = self._aggregate_confidence(validation, depth)

        # Step 4: Determine format type
        format_type = self._determine_format(comprehension)

        # Step 5: Generate speculative follow-ups
        followups = self._predict_followups(query, clean_answer, comprehension)

        # Step 6: Format final response
        formatted = self._format_response(
            clean_answer, key_points, confidence, format_type,
        )

        elapsed_ms = int((time.perf_counter_ns() - start) / 1_000_000)

        logger.info(
            "delivery_complete",
            format=format_type,
            confidence=confidence,
            key_points=len(key_points),
            followups=len(followups),
            elapsed_ms=elapsed_ms,
        )

        return DeliveryResult(
            response=formatted,
            confidence_score=confidence,
            key_points=key_points,
            speculative_followups=followups,
            format_type=format_type,
        )

    # ── Hedge removal ───────────────────────────────────────────

    def _remove_hedges(self, text: str) -> str:
        """Remove hedging language for direct, confident delivery."""
        result = text
        for pattern, replacement in _HEDGE_REPLACEMENTS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)

        # Clean up double spaces from removals
        result = re.sub(r"\s{2,}", " ", result)
        result = re.sub(r"\s+([.,;:!?])", r"\1", result)

        return result.strip()

    # ── Key point extraction ────────────────────────────────────

    def _extract_key_points(self, text: str, max_points: int = 3) -> list[str]:
        """Extract the most important points from the answer.

        Heuristic: prioritize numbered items, bullet points, sentences
        containing strong signal words.
        """
        points: list[str] = []

        # Check for existing structure (numbered lists, bullets)
        structured = re.findall(
            r"(?:^\s*[\d]+[.)]\s*|^\s*[-*]\s*)(.+)",
            text,
            re.MULTILINE,
        )
        if structured:
            return [s.strip() for s in structured[:max_points]]

        # Fall back to sentence-level extraction
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())

        # Score sentences by signal word density
        signal_words = {
            "key", "important", "critical", "essential", "main",
            "primary", "because", "therefore", "result", "conclusion",
            "first", "second", "third", "must", "should", "need",
        }

        scored = []
        for s in sentences:
            s = s.strip()
            if len(s.split()) < 5:
                continue
            words = set(s.lower().split())
            score = len(words & signal_words)
            scored.append((score, s))

        scored.sort(key=lambda x: x[0], reverse=True)
        points = [s for _, s in scored[:max_points]]

        return points if points else [text[:200].strip()]

    # ── Confidence aggregation ──────────────────────────────────

    def _aggregate_confidence(
        self,
        validation: ValidationResult | None,
        depth: DepthResult | None,
    ) -> float:
        """Aggregate confidence from validation and depth results."""
        scores: list[float] = []

        if validation:
            scores.append(validation.confidence)
        if depth:
            scores.append(depth.confidence)

        if not scores:
            return 0.5  # No validation data -- medium confidence

        # Weighted average (validation slightly more important)
        if len(scores) == 2:
            return scores[0] * 0.55 + scores[1] * 0.45
        return scores[0]

    # ── Format determination ────────────────────────────────────

    def _determine_format(
        self, comprehension: ComprehensionResult | None,
    ) -> str:
        """Determine the best response format based on query type."""
        if not comprehension:
            return "standard"

        from app.services.laevateinn.types import BloomLevel

        # Technical queries get technical format
        if comprehension.bloom_level in (BloomLevel.APPLY, BloomLevel.ANALYZE):
            return "technical"

        # Creative queries get creative format
        if comprehension.bloom_level == BloomLevel.CREATE:
            return "creative"

        # Simple recall gets concise format
        if comprehension.bloom_level == BloomLevel.REMEMBER:
            return "concise"

        return "standard"

    # ── Speculative follow-up prediction ────────────────────────

    def _predict_followups(
        self,
        query: str,
        answer: str,
        comprehension: ComprehensionResult | None,
    ) -> list[str]:
        """Predict the 3 most likely follow-up questions.

        Heuristic-based prediction (LLM-based SPC is in the
        Self-Evolution Engine, Stage 7).
        """
        followups: list[str] = []
        query_lower = query.lower()

        # Pattern: "What is X?" -> "How to use X?" -> "X vs Y?"
        if re.search(r"\bwhat\s+is\b", query_lower):
            topic = re.sub(r".*what\s+is\s+", "", query_lower).strip("? ")
            followups.append(f"How do I use {topic} in practice?")
            followups.append(f"What are the alternatives to {topic}?")
            followups.append(f"What are common mistakes when using {topic}?")

        # Pattern: "How to X?" -> "Troubleshooting X" -> "Best practices for X"
        elif re.search(r"\bhow\s+(do|can|to)\b", query_lower):
            topic = re.sub(r".*how\s+(?:do|can|to)\s+(?:I\s+)?", "", query_lower).strip("? ")
            followups.append(f"What if {topic} fails?")
            followups.append(f"What are best practices for {topic}?")
            followups.append(f"Can you show an example of {topic}?")

        # Pattern: "Fix/debug X" -> "Prevent X" -> "Monitor X"
        elif re.search(r"\bfix\b|\bdebug\b|\berror\b|\bbug\b", query_lower):
            followups.append("How do I prevent this issue in the future?")
            followups.append("What monitoring should I set up?")
            followups.append("Are there related issues I should check?")

        # Generic follow-ups
        else:
            followups.append("Can you give me a practical example?")
            followups.append("What are the trade-offs to consider?")
            followups.append("What should I do next?")

        return followups[:3]

    # ── Response formatting ─────────────────────────────────────

    def _format_response(
        self,
        answer: str,
        key_points: list[str],
        confidence: float,
        format_type: str,
    ) -> str:
        """Format the final response based on type and confidence."""
        # For now, return the answer as-is with confidence metadata
        # The full formatting (with confidence badges, etc.) will be
        # implemented when we wire into the Daena frontend
        return answer
