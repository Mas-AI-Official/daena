"""Laevateinn Cognitive OS -- The Intelligence Multiplier.

Daena's cognitive engine: self-evolving intelligence layer that wraps any LLM
to make it smarter through meta-reasoning, multi-model orchestration,
adversarial validation, and self-tuning.

Named after the mythical Norse sword -- the weapon that cuts through illusion.

Architecture (7+ stages):
    Stage 1: Deep Comprehension Engine (DCE)
    Stage 2: Dynamic Compute Scaler (DCS) + Kahneman Router
    Stage 3: Parallel Execution + Adversarial Model Debate (AMD)
    Stage 4: Recursive Depth Engine (RDE) + Chain-of-Verification (CoVe)
    Stage 5: Validation Gauntlet
    Stage 6: Jobs Delivery Engine
    Stage 7: Self-Evolution Engine
    + CodeVerifier: execute code mid-reasoning
    + DeepThink: extended thinking mode
    + EpisodicMemory: experience-based recall
    + InteractionLogger: accumulate training data
    + ToolAugmented reasoning: search/tools in RDE loop
"""

from app.services.laevateinn.comprehension import DeepComprehensionEngine
from app.services.laevateinn.compute_scaler import DynamicComputeScaler
from app.services.laevateinn.debate import AdversarialModelDebate
from app.services.laevateinn.depth_engine import RecursiveDepthEngine
from app.services.laevateinn.validation import ValidationGauntlet
from app.services.laevateinn.delivery import JobsDeliveryEngine
from app.services.laevateinn.pipeline import LaevateinnPipeline
from app.services.laevateinn.code_verifier import CodeVerifier
from app.services.laevateinn.deep_think import DeepThinkEngine
from app.services.laevateinn.episodic_memory import EpisodicMemory
from app.services.laevateinn.interaction_logger import InteractionLogger
from app.services.laevateinn.tool_augmented import ToolAugmentedReasoner
from app.services.laevateinn.knowledge_graph import PersistentKnowledgeGraph
from app.services.laevateinn.meta_monitor import MetaMonitor
from app.services.laevateinn.speculative import SpeculativePrecomputer

__all__ = [
    # Core pipeline (Stages 1-6)
    "DeepComprehensionEngine",
    "DynamicComputeScaler",
    "AdversarialModelDebate",
    "RecursiveDepthEngine",
    "ValidationGauntlet",
    "JobsDeliveryEngine",
    "LaevateinnPipeline",
    # Gap-filling modules
    "CodeVerifier",
    "DeepThinkEngine",
    "EpisodicMemory",
    "InteractionLogger",
    "ToolAugmentedReasoner",
    # Phase 4: Self-Evolution
    "PersistentKnowledgeGraph",
    "MetaMonitor",
    "SpeculativePrecomputer",
]
