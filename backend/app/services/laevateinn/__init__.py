"""Laevateinn Cognitive OS v4 -- Meta-Questioning Architecture.

The most advanced reasoning pipeline in any publicly deployable system.
20 stages, 15 unique beyond-Mythos capabilities, 7 loop-back paths.

Architecture:
    Stage 0:    Failure Memory -- learn from past mistakes across sessions
    Stage 0.5:  Socratic Inversion -- upgrade the QUESTION before answering
    Stage 1:    DCE + Recursive Constraint Decomposition (5-level deep)
    Stage 1.5:  Epistemic State Tracker + Meta-Strategy Selection
    Stage 1.75: Question Quality Auditor -- Meta-Level 3 cognition
    Stage 2:    Dynamic Compute Scaler (Kahneman routing)
    Stage 3:    Adversarial Model Debate with disagreement-focused rounds
    Stage 3.5:  Cross-Domain Analogy Engine
    Stage 4:    Recursive Depth Engine + Chain-of-Verification
    Stage 4.5:  Causal Reasoning Graph -- structural verification
    Stage 5:    Validation Gauntlet (6 tests)
    Stage 5.25: Cognitive Separation -- falsification || construction
    Stage 5.5:  Counterfactual Engine -- "what if different?"
    Stage 6:    Adversarial Verification Gate -- prove yourself wrong
    Stage 6.5:  Outcome Simulator -- predict consequences
    Stage 7:    Consensus Gradient -- per-section confidence heat map
    Stage 8:    Confidence Calibration -- scores from historical accuracy
    Stage 9:    Jobs Delivery Engine
    Stage 10:   Self-Evolution (async)

Beyond-Mythos capabilities (unique to Laevateinn):
    1.  Socratic Inversion -- upgrade questions before answering
    2.  Question Quality Audit -- Meta-Level 3: audit the auditor
    3.  Cognitive Separation -- isolated bug-finding vs solution-finding
    4.  Epistemic State Tracking -- SHAPE of uncertainty, not just level
    5.  Causal Reasoning Graph -- verify logic STRUCTURE, not just facts
    6.  Adversarial Verification Gate -- active falsification
    7.  Disagreement-Focused Debate -- argue specific conflicts
    8.  Recursive Constraint Decomposition -- 5-level deep gap finding
    9.  Failure Memory -- causal models from past failures
    10. Counterfactual Reasoning -- explore alternative conclusions
    11. Outcome Simulation -- predict consequences before delivery
    12. Cross-Domain Analogy -- import solutions from unrelated fields
    13. Confidence Calibration -- empirically calibrated scores
    14. Consensus Gradient -- per-section confidence heat map
    15. Meta-Strategy Selection -- choose reasoning approach first
"""

from app.services.laevateinn.adversarial_gate import AdversarialVerificationGate
from app.services.laevateinn.analogy_engine import AnalogyEngine
from app.services.laevateinn.calibration import ConfidenceCalibrator
from app.services.laevateinn.causal_graph import CausalReasoningGraph
from app.services.laevateinn.code_verifier import CodeVerifier
from app.services.laevateinn.cognitive_separation import CognitiveSeparationEngine
from app.services.laevateinn.comprehension import DeepComprehensionEngine
from app.services.laevateinn.compute_scaler import DynamicComputeScaler
from app.services.laevateinn.consensus_gradient import ConsensusGradientEngine
from app.services.laevateinn.counterfactual import CounterfactualEngine
from app.services.laevateinn.debate import AdversarialModelDebate
from app.services.laevateinn.deep_think import DeepThinkEngine
from app.services.laevateinn.delivery import JobsDeliveryEngine
from app.services.laevateinn.depth_engine import RecursiveDepthEngine
from app.services.laevateinn.epistemic_tracker import EpistemicStateTracker
from app.services.laevateinn.episodic_memory import EpisodicMemory
from app.services.laevateinn.failure_memory import FailureMemoryEngine
from app.services.laevateinn.interaction_logger import InteractionLogger
from app.services.laevateinn.knowledge_graph import PersistentKnowledgeGraph
from app.services.laevateinn.meta_monitor import MetaMonitor
from app.services.laevateinn.outcome_simulator import OutcomeSimulator
from app.services.laevateinn.perspective_oscillator import PerspectiveOscillator
from app.services.laevateinn.pipeline import LaevateinnPipeline
from app.services.laevateinn.question_auditor import QuestionQualityAuditor
from app.services.laevateinn.socratic_inversion import SocraticInversionEngine
from app.services.laevateinn.speculative import SpeculativePrecomputer
from app.services.laevateinn.tool_augmented import ToolAugmentedReasoner
from app.services.laevateinn.validation import ValidationGauntlet

__all__ = [
    # Main pipeline
    "LaevateinnPipeline",
    # Meta-Questioning engines (Level 3 cognition -- unique to Laevateinn)
    "SocraticInversionEngine",
    "QuestionQualityAuditor",
    "CognitiveSeparationEngine",
    "PerspectiveOscillator",
    # Core stages (1-9)
    "DeepComprehensionEngine",
    "DynamicComputeScaler",
    "AdversarialModelDebate",
    "RecursiveDepthEngine",
    "ValidationGauntlet",
    "JobsDeliveryEngine",
    # Beyond-Mythos engines
    "EpistemicStateTracker",
    "CausalReasoningGraph",
    "AdversarialVerificationGate",
    "FailureMemoryEngine",
    "CounterfactualEngine",
    "OutcomeSimulator",
    "AnalogyEngine",
    "ConfidenceCalibrator",
    "ConsensusGradientEngine",
    # Supporting modules
    "CodeVerifier",
    "DeepThinkEngine",
    "EpisodicMemory",
    "InteractionLogger",
    "ToolAugmentedReasoner",
    # Self-Evolution
    "PersistentKnowledgeGraph",
    "MetaMonitor",
    "SpeculativePrecomputer",
]
