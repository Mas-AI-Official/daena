"""Laevateinn v3 shared types and data structures."""

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
    constraint_tree: ConstraintTreeResult | None = None
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
    disagreement_points: list[DisagreementPoint] = field(default_factory=list)
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


class UncertaintyShape(str, enum.Enum):
    """Shape of epistemic uncertainty -- determines resolution strategy."""
    CONTRADICTORY = "CONTRADICTORY"    # Evidence conflicts -> deeper debate
    ABSENT = "ABSENT"                  # No evidence exists -> tool/search
    AMBIGUOUS = "AMBIGUOUS"            # Multiple valid readings -> re-comprehend
    COMPUTATIONAL = "COMPUTATIONAL"    # Can't verify analytically -> execute code
    CONFIDENT = "CONFIDENT"            # Low uncertainty -> proceed


class ReasoningStrategy(str, enum.Enum):
    """Meta-strategy for reasoning approach selection."""
    DEPTH_FIRST = "DEPTH_FIRST"              # Deep recursive analysis
    BREADTH_FIRST = "BREADTH_FIRST"          # Explore many options lightly
    CONSTRAINT_PROPAGATION = "CONSTRAINT_PROPAGATION"  # Narrow from constraints
    HYPOTHESIS_DRIVEN = "HYPOTHESIS_DRIVEN"  # Test/eliminate hypotheses
    ANALOGICAL = "ANALOGICAL"                # Import from other domains
    STANDARD = "STANDARD"                    # Default pipeline


@dataclass(slots=True)
class EpistemicState:
    """Tracked uncertainty state for a reasoning pass."""
    shape: UncertaintyShape
    confidence_floor: float          # Minimum plausible confidence
    confidence_ceiling: float        # Maximum plausible confidence
    evidence_for: list[str] = field(default_factory=list)
    evidence_against: list[str] = field(default_factory=list)
    missing_evidence: list[str] = field(default_factory=list)
    recommended_action: str = ""     # What to do about this uncertainty


@dataclass(slots=True)
class CausalNode:
    """A single claim in a causal reasoning graph."""
    claim: str
    node_id: int = 0
    verified: bool = False
    load_bearing: bool = False       # If false changes the conclusion
    confidence: float = 0.5


@dataclass(slots=True)
class CausalEdge:
    """A logical dependency between claims."""
    from_id: int
    to_id: int
    relationship: str                # "supports" | "contradicts" | "requires"
    valid: bool = True
    strength: float = 0.5


@dataclass(slots=True)
class CausalGraphResult:
    """Output of the Causal Reasoning Graph engine."""
    nodes: list[CausalNode] = field(default_factory=list)
    edges: list[CausalEdge] = field(default_factory=list)
    missing_nodes: list[str] = field(default_factory=list)  # Gaps in reasoning
    invalid_edges: list[str] = field(default_factory=list)  # Broken logic
    composition_valid: bool = True
    confidence: float = 0.5
    total_latency_ms: int = 0


@dataclass(slots=True)
class DisagreementPoint:
    """A specific point where models disagree during debate."""
    topic: str
    positions: dict[str, str] = field(default_factory=dict)  # model -> position
    resolution: str = ""
    resolved: bool = False


@dataclass(slots=True)
class AdversarialGateResult:
    """Output of the Adversarial Verification Gate (Stage 5.5)."""
    passed: bool
    counter_evidence_query: str = ""          # "If wrong, what would I see?"
    counter_evidence_found: list[str] = field(default_factory=list)
    counter_evidence_absent: bool = True      # True = no counter-evidence = GOOD
    confidence_boost: float = 0.0             # Added confidence if gate passes
    loops_back: bool = False                  # True = send back to RDE
    total_latency_ms: int = 0


@dataclass(slots=True)
class ConstraintNode:
    """A node in the recursive constraint decomposition tree."""
    constraint: str
    level: int                       # Decomposition depth (0 = root)
    parent_id: int = -1
    node_id: int = 0
    is_hard: bool = True             # Hard constraint vs soft/stated
    is_enforced: bool = True         # Actually enforced vs just stated
    gap: str = ""                    # The gap between stated and enforced
    children: list[int] = field(default_factory=list)


@dataclass(slots=True)
class ConstraintTreeResult:
    """Output of recursive constraint decomposition."""
    nodes: list[ConstraintNode] = field(default_factory=list)
    open_channels: list[str] = field(default_factory=list)   # Gaps found
    max_depth_reached: int = 0
    total_constraints: int = 0
    soft_constraints: int = 0        # Stated but not enforced
    total_latency_ms: int = 0


@dataclass(slots=True)
class FailureRecord:
    """A single failure with causal analysis."""
    query_hash: str                  # Hash of query that failed
    failure_type: str                # "factual" | "logical" | "structural" | "incomplete"
    root_cause: str                  # WHY it failed (causal, not just what)
    strategy_used: str               # Which ReasoningStrategy was active
    causal_chain: list[str] = field(default_factory=list)  # Chain of causes
    prevention_rule: str = ""        # How to prevent in future
    timestamp: float = field(default_factory=time.time)


@dataclass(slots=True)
class FailureMemoryResult:
    """Output of failure memory analysis."""
    relevant_failures: list[FailureRecord] = field(default_factory=list)
    strategy_adjustments: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    accumulated_patterns: int = 0


@dataclass(slots=True)
class CounterfactualResult:
    """Output of counterfactual reasoning."""
    original_conclusion: str
    alternatives: list[CounterfactualBranch] = field(default_factory=list)
    hidden_assumptions_found: list[str] = field(default_factory=list)
    confidence_impact: float = 0.0   # How much counterfactuals change confidence
    total_latency_ms: int = 0


@dataclass(slots=True)
class CounterfactualBranch:
    """A single 'what if the answer were different?' branch."""
    alternative_conclusion: str
    required_conditions: list[str] = field(default_factory=list)  # What must be true
    plausibility: float = 0.0        # How plausible these conditions are
    reveals: str = ""                # What hidden assumption this exposes


@dataclass(slots=True)
class SimulatedOutcome:
    """A single simulated outcome of following the answer."""
    scenario: str
    outcome: str
    severity: str = "low"            # "low" | "medium" | "high" | "catastrophic"
    probability: float = 0.5
    mitigation: str = ""


@dataclass(slots=True)
class OutcomeSimulationResult:
    """Output of outcome simulation."""
    outcomes: list[SimulatedOutcome] = field(default_factory=list)
    catastrophic_risks: list[str] = field(default_factory=list)
    safe_to_deliver: bool = True
    worst_case: str = ""
    total_latency_ms: int = 0


@dataclass(slots=True)
class Analogy:
    """A cross-domain analogy for reasoning transfer."""
    source_domain: str               # Where the pattern comes from
    target_domain: str               # Current problem domain
    structural_match: str            # What's structurally similar
    imported_insight: str            # What solution pattern transfers
    confidence: float = 0.5


@dataclass(slots=True)
class AnalogyResult:
    """Output of cross-domain analogy engine."""
    analogies: list[Analogy] = field(default_factory=list)
    best_analogy: str = ""
    insight_applied: str = ""        # How the best analogy was used
    total_latency_ms: int = 0


@dataclass(slots=True)
class CalibrationRecord:
    """A single calibration data point."""
    predicted_confidence: float
    was_correct: bool
    query_hash: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass(slots=True)
class CalibrationResult:
    """Output of confidence calibration analysis."""
    raw_confidence: float
    calibrated_confidence: float
    calibration_factor: float = 1.0  # Multiplier to adjust raw scores
    data_points: int = 0             # How many historical points inform this
    reliability: str = "low"         # "low" | "medium" | "high" based on data


@dataclass(slots=True)
class ConsensusGradient:
    """Per-section confidence gradient across an answer.

    Beyond Mythos: instead of one confidence score for the whole answer,
    map confidence at the paragraph/claim level. Some parts might be
    95% confident while others are 40%.
    """
    sections: list[ConsensusSection] = field(default_factory=list)
    overall_confidence: float = 0.5
    weakest_section: str = ""
    strongest_section: str = ""


@dataclass(slots=True)
class ConsensusSection:
    """A section of the answer with its own confidence."""
    content: str
    confidence: float
    source: str = ""                 # Which model/verification produced this
    contested: bool = False          # Was this section debated?


@dataclass(slots=True)
class LaevateinnTrace:
    """Full trace of a Laevateinn pipeline execution."""
    query: str
    comprehension: ComprehensionResult | None = None
    compute_profile: ComputeProfile | None = None
    debate: DebateResult | None = None
    depth: DepthResult | None = None
    causal_graph: CausalGraphResult | None = None
    validation: ValidationResult | None = None
    adversarial_gate: AdversarialGateResult | None = None
    epistemic_state: EpistemicState | None = None
    constraint_tree: ConstraintTreeResult | None = None
    failure_memory: FailureMemoryResult | None = None
    counterfactual: CounterfactualResult | None = None
    outcome_simulation: OutcomeSimulationResult | None = None
    analogy: AnalogyResult | None = None
    calibration: CalibrationResult | None = None
    consensus_gradient: ConsensusGradient | None = None
    delivery: DeliveryResult | None = None
    reasoning_strategy: ReasoningStrategy = ReasoningStrategy.STANDARD
    disagreement_points: list[DisagreementPoint] = field(default_factory=list)
    total_latency_ms: int = 0
    total_cost_usd: float = 0.0
    stages_executed: list[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    # ── Meta-Questioning engines (Level 3 cognition) ───────────
    socratic_inversion: SocraticInversionResult | None = None
    question_audit: QuestionAuditResult | None = None
    cognitive_separation: CognitiveSeparationResult | None = None


# ─── Socratic Inversion Engine types ──────────────────────────


class QuestionLevel(str, enum.Enum):
    """Socratic depth level of a question."""
    SURFACE = "SURFACE"            # What the user literally typed
    IMPLICIT = "IMPLICIT"          # What they actually mean
    STRUCTURAL = "STRUCTURAL"      # The structural problem behind the question
    GENERATIVE = "GENERATIVE"      # The question that, if answered, unlocks 10 others
    PARADIGMATIC = "PARADIGMATIC"  # The paradigm-level question (reframes the domain)


@dataclass(slots=True)
class QuestionUpgrade:
    """A single upgrade of a question to a deeper level."""
    original: str
    upgraded: str
    level: QuestionLevel
    technique_used: str            # Which thinker's method was applied
    information_gain: float        # Shannon: how much this reduces uncertainty (0-1)
    reasoning: str                 # Why this upgrade matters


@dataclass(slots=True)
class SocraticInversionResult:
    """Output of Socratic Inversion Engine (Stage 0.5).

    Instead of: question -> answer -> verify answer
    Does: question -> generate BETTER questions -> answer the better question

    Combines: Socrates (elenchus), Musk (first principles), Polya (decomposition),
    Shannon (information gain), Kahneman (substitution detection).
    """
    original_question: str
    upgraded_question: str          # The best question to actually answer
    upgrade_chain: list[QuestionUpgrade] = field(default_factory=list)
    depth_reached: QuestionLevel = QuestionLevel.SURFACE
    substitution_detected: bool = False  # Kahneman: was user asking easier question?
    substitution_explanation: str = ""
    inverted_form: str = ""        # Munger: "What would guarantee failure?"
    eliminated_questions: list[str] = field(default_factory=list)  # Taleb: via negativa
    anchor_detected: bool = False  # Kahneman: was there an anchoring bias?
    total_latency_ms: int = 0


# ─── Question Quality Auditor types ──────────────────────────


class QuestionDefect(str, enum.Enum):
    """Types of defects in a question or verification question."""
    DERIVATIVE = "DERIVATIVE"          # Question is derivative of the answer, not independent
    UNFALSIFIABLE = "UNFALSIFIABLE"    # No possible observation could show it wrong
    REDUNDANT = "REDUNDANT"            # Same question reworded
    LOW_INFORMATION = "LOW_INFORMATION"  # Answer won't change beliefs
    WRONG_LEVEL = "WRONG_LEVEL"        # Asks about symptoms, not causes
    SUBSTITUTED = "SUBSTITUTED"        # Answering an easier question instead
    MISSING_FRAME = "MISSING_FRAME"    # Entire perspective/frame not represented


@dataclass(slots=True)
class QuestionAssessment:
    """Assessment of a single question's quality."""
    question: str
    information_gain: float        # Shannon: expected uncertainty reduction (0-1)
    falsifiability: float          # Popper: how sharply it distinguishes hypotheses (0-1)
    independence: float            # Is it independent of the answer being checked? (0-1)
    defects: list[QuestionDefect] = field(default_factory=list)
    missing_perspectives: list[str] = field(default_factory=list)  # de Bono hats not covered
    suggested_replacement: str = ""  # A better question if defects found


@dataclass(slots=True)
class QuestionAuditResult:
    """Output of Question Quality Auditor (Stage 1.75).

    Meta-Level 3: Asks "Are we asking the RIGHT questions to check
    if we're asking the right question?"

    Combines: Shannon (information gain), Popper (falsifiability),
    de Bono (frame coverage), Hofstadter (meta-cognitive levels),
    Taleb (via negativa / question fragility).
    """
    questions_audited: int
    assessments: list[QuestionAssessment] = field(default_factory=list)
    overall_question_quality: float = 0.5  # Aggregate score (0-1)
    missing_question_types: list[str] = field(default_factory=list)  # Gaps in questioning
    frame_coverage: dict[str, bool] = field(default_factory=dict)  # de Bono hat coverage
    meta_level_reached: int = 0      # Hofstadter: highest meta-level achieved (0-3)
    via_negativa_eliminations: int = 0  # Taleb: how many bad questions removed
    upgraded_questions: list[str] = field(default_factory=list)  # Replacement questions
    loops_back: bool = False         # Should pipeline re-comprehend?
    total_latency_ms: int = 0


# ─── Cognitive Separation Engine types ────────────────────────


class CognitiveMode(str, enum.Enum):
    """Two fundamentally different cognitive operations."""
    FALSIFICATION = "FALSIFICATION"  # Bug-finding: what's WRONG?
    CONSTRUCTION = "CONSTRUCTION"    # Solution-finding: what's the FIX?


@dataclass(slots=True)
class FalsificationResult:
    """Result of the falsification (bug-finding) track.

    Pure Popper/Taleb: find what's wrong, don't fix it.
    Via negativa: eliminate wrong answers to constrain the space.
    """
    bugs_found: list[str] = field(default_factory=list)
    wrong_answers_eliminated: list[str] = field(default_factory=list)
    load_bearing_flaws: list[str] = field(default_factory=list)  # Flaws that break the conclusion
    non_load_bearing_flaws: list[str] = field(default_factory=list)  # Cosmetic issues
    strongest_counterargument: str = ""
    falsification_confidence: float = 0.5  # How confident are we in the bugs found?


@dataclass(slots=True)
class ConstructionResult:
    """Result of the construction (solution-finding) track.

    Pure Polya/Feynman: build the fix, don't re-diagnose.
    Uses decomposition, analogy, simplification.
    """
    proposed_fixes: list[str] = field(default_factory=list)
    technique_used: str = ""       # Polya heuristic or method applied
    simplified_version: str = ""   # Polya: solve the simpler case first
    construction_confidence: float = 0.5


@dataclass(slots=True)
class CognitiveSeparationResult:
    """Output of Cognitive Separation Engine (Stage 5.25).

    Splits verification into two INDEPENDENT parallel tracks:
    Track A (Falsification): Popper/Taleb/Munger -- find what's wrong
    Track B (Construction): Polya/Feynman/Boyd -- improve the solution

    These run INDEPENDENTLY. Track A cannot see Track B's output and vice versa.
    Only after both complete does a synthesis step merge findings.

    This prevents the common failure where verification biases toward
    confirming the existing answer rather than genuinely trying to break it.
    """
    falsification: FalsificationResult | None = None
    construction: ConstructionResult | None = None
    tracks_agreed: bool = True     # Did both tracks reach compatible conclusions?
    synthesis: str = ""            # Merged finding from both tracks
    answer_improved: bool = False  # Was the answer actually changed?
    improved_answer: str = ""      # The improved answer (if changed)
    total_latency_ms: int = 0
