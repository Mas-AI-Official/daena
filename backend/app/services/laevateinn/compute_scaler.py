"""Stage 2: Dynamic Compute Scaler + Kahneman Router.

Allocates compute resources proportional to query difficulty.
Trivial queries get fast, cheap responses. Brutal queries get
all available models with full recursive validation.

This is APEX's structural advantage over any single model:
single models use the same compute budget for every query.
APEX scales compute to difficulty.

Integrates with Daena's ModelRouter by providing a ComputeProfile
that overrides the default routing decision.
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING

from app.core.logging import get_logger
from app.services.laevateinn.types import (
    BloomLevel,
    CognitiveSystem,
    ComputeProfile,
    ComprehensionResult,
    Difficulty,
)

if TYPE_CHECKING:
    from app.services.query_understanding import IntentType

logger = get_logger(__name__)

# Bloom's level to difficulty score mapping
_BLOOM_SCORES: dict[BloomLevel, int] = {
    BloomLevel.REMEMBER: 0,
    BloomLevel.UNDERSTAND: 1,
    BloomLevel.APPLY: 2,
    BloomLevel.ANALYZE: 3,
    BloomLevel.EVALUATE: 3,
    BloomLevel.CREATE: 4,
}

# Intent type to difficulty score mapping (uses Daena's IntentType)
_INTENT_SCORES: dict[str, int] = {
    "SIMPLE": 0,
    "SEARCH": 1,
    "CODING": 2,
    "ANALYSIS": 3,
    "CREATIVE": 2,
    "MULTI_STEP": 3,
    "DANGEROUS": 3,
    "TOOL_USE": 2,
    "AMBIGUOUS": 2,
}

# Compute profiles per difficulty level
_PROFILES: dict[Difficulty, dict] = {
    Difficulty.TRIVIAL: {
        "num_models": 1,
        "recursion_depth": 0,
        "validation_level": "none",
        "amd_rounds": 0,
        "target_latency_ms": 500,
    },
    Difficulty.STANDARD: {
        "num_models": 1,
        "recursion_depth": 1,
        "validation_level": "feynman_only",
        "amd_rounds": 0,
        "target_latency_ms": 3000,
    },
    Difficulty.HARD: {
        "num_models": 3,
        "recursion_depth": 3,
        "validation_level": "full_gauntlet",
        "amd_rounds": 2,
        "target_latency_ms": 15000,
    },
    Difficulty.BRUTAL: {
        "num_models": 99,  # "all" -- capped by available models
        "recursion_depth": 5,
        "validation_level": "full_gauntlet_with_cove",
        "amd_rounds": 3,
        "target_latency_ms": 45000,
    },
}


class DynamicComputeScaler:
    """Stage 2 of APEX: allocate compute proportional to difficulty.

    Implements Kahneman dual-process routing:
        System 1: fast, intuitive (trivial/standard queries)
        System 2: slow, deliberate (hard/brutal queries)
    """

    def scale(
        self,
        comprehension: ComprehensionResult,
        intent_type: str = "AMBIGUOUS",
        *,
        available_models: int = 1,
        force_difficulty: Difficulty | None = None,
    ) -> ComputeProfile:
        """Determine compute allocation for a query.

        Args:
            comprehension: Output from DCE Stage 1.
            intent_type: Daena's IntentType classification.
            available_models: Number of models currently available.
            force_difficulty: Override automatic difficulty estimation.

        Returns:
            ComputeProfile with resource allocation.
        """
        start = time.perf_counter_ns()

        if force_difficulty:
            difficulty = force_difficulty
        else:
            difficulty = self._estimate_difficulty(comprehension, intent_type)

        system = self._kahneman_route(difficulty, comprehension.bloom_level)

        profile_data = _PROFILES[difficulty]
        actual_models = min(profile_data["num_models"], available_models)

        profile = ComputeProfile(
            difficulty=difficulty,
            system=system,
            num_models=actual_models,
            recursion_depth=profile_data["recursion_depth"],
            validation_level=profile_data["validation_level"],
            amd_rounds=profile_data["amd_rounds"],
            target_latency_ms=profile_data["target_latency_ms"],
        )

        elapsed_ms = int((time.perf_counter_ns() - start) / 1_000_000)

        logger.info(
            "dcs_complete",
            difficulty=difficulty.value,
            system=system.value,
            models=actual_models,
            depth=profile.recursion_depth,
            elapsed_ms=elapsed_ms,
        )

        return profile

    def _estimate_difficulty(
        self,
        comprehension: ComprehensionResult,
        intent_type: str,
    ) -> Difficulty:
        """Estimate query difficulty from multiple signals.

        Scoring:
            - Bloom's level: 0-4 points
            - Intent type: 0-3 points
            - Syntactic complexity: 0-2 points
            - Ambiguity (multiple interpretations): 0-1 point
        """
        score = 0

        # Bloom's level
        score += _BLOOM_SCORES.get(comprehension.bloom_level, 1)

        # Intent type
        score += _INTENT_SCORES.get(intent_type, 2)

        # Syntactic complexity
        score += self._syntactic_complexity(comprehension.original_query)

        # Ambiguity bonus: multiple high-probability interpretations
        high_prob = [
            i for i in comprehension.interpretations if i.probability > 0.25
        ]
        if len(high_prob) >= 3:
            score += 1

        # Multiple sub-questions indicate compound complexity
        if len(comprehension.sub_questions) >= 3:
            score += 1

        # Map score to difficulty
        if score <= 2:
            return Difficulty.TRIVIAL
        if score <= 5:
            return Difficulty.STANDARD
        if score <= 8:
            return Difficulty.HARD
        return Difficulty.BRUTAL

    def _syntactic_complexity(self, query: str) -> int:
        """Score syntactic complexity of the query (0-2)."""
        score = 0
        words = query.split()

        # Long queries are more complex
        if len(words) > 50:
            score += 1
        elif len(words) > 100:
            score += 2

        # Nested clauses indicate complexity
        clause_markers = re.findall(
            r"\b(if|when|while|unless|although|because|since|whereas)\b",
            query,
            re.IGNORECASE,
        )
        if len(clause_markers) >= 2:
            score += 1

        return min(score, 2)

    def _kahneman_route(
        self,
        difficulty: Difficulty,
        bloom: BloomLevel,
    ) -> CognitiveSystem:
        """Kahneman dual-process routing.

        System 1 (fast, intuitive):
            - Trivial difficulty
            - Remember/Understand Bloom levels
            - Pattern-matching queries

        System 2 (slow, deliberate):
            - Hard/Brutal difficulty
            - Analyze/Evaluate/Create Bloom levels
            - Novel or ambiguous queries
        """
        if difficulty in (Difficulty.TRIVIAL,):
            return CognitiveSystem.SYSTEM_1

        if difficulty in (Difficulty.HARD, Difficulty.BRUTAL):
            return CognitiveSystem.SYSTEM_2

        # Standard: depends on Bloom's level
        if bloom in (BloomLevel.REMEMBER, BloomLevel.UNDERSTAND):
            return CognitiveSystem.SYSTEM_1

        return CognitiveSystem.SYSTEM_2
