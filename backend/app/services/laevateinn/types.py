"""Laevateinn v2 shared types and data structures."""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field
from typing import Any


class Difficulty(str, enum.Enum):
    """Laevateinn difficulty classification for dynamic compute scaling."""
    TRIVIAL = "TRIVIAL"      # 1 model, 0 recursion, skip validation
    STANDARD = "STANDARD"    # 1 model, 1 validation pass
    HARD = "HARD"            # 3 models parallel, 2 recursive loops
    BRUTAL = "BRUTAL"        # ALL models, 5 recursive loops, full AMD


class BloomLevel(str, enum.Enum):
    """Bloom's taxonomy level for cognitive routing."""
    REMEMBER = "REMEMBER"    # Recall facts
    UNDERSTAND = "UNDERSTAND"  # Explain concepts
    APPLY = "APPLY"          # Use in new contexts
    ANALYZE = "ANALYZE"      # Break down, compare
    EVALUATE = "EVALUATE"    # Judge, critique
    CREATE = "CREATE"        # Design, produce


class CognitiveSystem(str, enum.Enum):
    """Kahneman dual-process routing."""
    SYSTEM_1 = "SYSTEM_1"   # Fast, intuitive, pattern-match
    SYSTEM_2 = "SYSTEM_2"   # Slow, deliberate, analytical


@dataclass(slots=True)
class ComprehensionResult:
    """Output of the Deep Comprehension Engine."""
    original_query: str
    compressed_query: str           # Feynman: one clear sentence
    sub_questions: list[str]        # Polya decomposition
    hidden_assumptions: list[str]   # Surfaced assumptions
    noise_eliminated: str           # Musk: first principles only
    real_question: str              # Tesla: the REAL question
    interpretations: list[Interpretation]  # ACH multi-interpretation
    bloom_level: BloomLevel
    processing_time_ms: int = 0


@dataclass(frozen=True, slots=True)
class Interpretation:
    """A single interpretation from ACH analysis."""
    text: str
    probability: float  # P(intent|context+history)
    reasoning: str


@dataclass(slots=True)
class ComputeProfile:
    """Dynamic compute allocation for a query."""
    difficulty: Difficulty
    system: CognitiveSystem
    num_models: int
    recursion_depth: int
    validation_level: str       # none, feynman_only, full_gauntlet, full_with_cove
    amd_rounds: int
    target_latency_ms: int
    estimated_cost_usd: float = 0.0


@dataclass(slots=True)
class DebateRound:
    """A single round of adversarial model debate."""
    round_num: int
    model_id: str
    content: str
    role: str  # "answer" | "critique" | "defense" | "judgment"
    confidence: float = 0.0
    latency_ms: int = 0


@dataclass(slots=True)
class DebateResult:
    """Output of the Adversarial Model Debate."""
    winner_model: str
    winner_answer: str
    winner_reasoning: str
    confidence: float
    rounds: list[DebateRound] = field(default_factory=list)
    all_answers: dict[str, str] = field(default_factory=dict)
    total_latency_ms: int = 0
    total_cost_usd: float = 0.0


@dataclass(slots=True)
class VerificationQuestion:
    """A question generated for Chain-of-Verification."""
    question: str
    expected_type: str  # "factual" | "logical" | "temporal"
    independent_answer: str = ""
    consistent_with_original: bool = True


@dataclass(slots=True)
class DepthResult:
    """Output of the Recursive Depth Engine."""
    final_answer: str
    depth_used: int
    max_depth: int
    confidence: float
    verification_questions: list[VerificationQuestion] = field(default_factory=list)
    inconsistencies_found: list[str] = field(default_factory=list)
    revisions: list[str] = field(default_factory=list)
    total_latency_ms: int = 0


@dataclass(slots=True)
class ValidationResult:
    """Output of the Validation Gauntlet."""
    passed: bool
    confidence: float
    feynman_explanation: str = ""
    popper_falsifications: list[str] = field(default_factory=list)
    buffett_failure_modes: list[str] = field(default_factory=list)
    hacker_challenges: list[str] = field(default_factory=list)
    cove_verified: bool = False
    temporal_valid: bool = True
    failure_reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DeliveryResult:
    """Output of the Jobs Delivery Engine."""
    response: str
    confidence_score: float
    key_points: list[str]
    speculative_followups: list[str] = field(default_factory=list)
    format_type: str = "standard"  # standard | technical | creative | concise


@dataclass(slots=True)
class LaevateinnTrace:
    """Full trace of an Laevateinn pipeline execution."""
    query: str
    comprehension: ComprehensionResult | None = None
    compute_profile: ComputeProfile | None = None
    debate: DebateResult | None = None
    depth: DepthResult | None = None
    validation: ValidationResult | None = None
    delivery: DeliveryResult | None = None
    total_latency_ms: int = 0
    total_cost_usd: float = 0.0
    stages_executed: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
