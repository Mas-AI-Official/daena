"""Laevateinn Cognitive OS v3 -- Complete Beyond-Mythos Architecture.

The most advanced reasoning pipeline in any publicly deployable system.
17 stages, 7 unique beyond-Mythos capabilities, 4 loop-back paths.

Architecture:
    Stage 0:   Failure Memory -- learn from past mistakes across sessions
    Stage 1:   DCE + Recursive Constraint Decomposition (5-level deep)
    Stage 1.5: Epistemic State Tracker + Meta-Strategy Selection
    Stage 2:   Dynamic Compute Scaler (Kahneman routing)
    Stage 3:   Adversarial Model Debate with disagreement-focused rounds
    Stage 3.5: Cross-Domain Analogy Engine
    Stage 4:   Recursive Depth Engine + Chain-of-Verification
    Stage 4.5: Causal Reasoning Graph -- structural verification
    Stage 5:   Validation Gauntlet (6 tests)
    Stage 5.5: Counterfactual Engine -- "what if different?"
    Stage 6:   Adversarial Verification Gate -- prove yourself wrong
    Stage 6.5: Outcome Simulator -- predict consequences
    Stage 7:   Consensus Gradient -- per-section confidence heat map
    Stage 8:   Confidence Calibration -- scores from historical accuracy
    Stage 9:   Jobs Delivery Engine
    Stage 10:  Self-Evolution (async)

Beyond-Mythos capabilities (unique to Laevateinn):
    1. Epistemic State Tracking -- SHAPE of uncertainty, not just level
    2. Causal Reasoning Graph -- verify logic STRUCTURE, not just facts
    3. Adversarial Verification Gate -- active falsification
    4. Disagreement-Focused Debate -- argue specific conflicts
    5. Recursive Constraint Decomposition -- 5-level deep gap finding
    6. Failure Memory -- causal models from past failures
    7. Counterfactual Reasoning -- explore alternative conclusions
    8. Outcome Simulation -- predict consequences before delivery
    9. Cross-Domain Analogy -- import solutions from unrelated fields
    10. Confidence Calibration -- empirically calibrated scores
    11. Consensus Gradient -- per-section confidence heat map
    12. Meta-Strategy Selection -- choose reasoning approach first
"""

from app.services.laevateinn.adversarial_gate import AdversarialVerificationGate
from app.services.laevateinn.analogy_engine import AnalogyEngine
from app.services.laevateinn.calibration import ConfidenceCalibrator
from app.services.laevateinn.causal_graph import CausalReasoningGraph
from app.services.laevateinn.code_verifier import CodeVerifier
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
from app.services.laevateinn.pipeline import LaevateinnPipeline
from app.services.laevateinn.speculative import SpeculativePrecomputer
from app.services.laevateinn.tool_augmented import ToolAugmentedReasoner
from app.services.laevateinn.validation import ValidationGauntlet

__all__ = [
    # Main pipeline
    "LaevateinnPipeline",
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
