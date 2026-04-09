"""Cognition Engine -- Daena's brain.

25 philosophical frameworks from humanity's greatest thinkers, orchestrated
by the OODA-R loop (Observe-Orient-Decide-Act-Reflect) to create a living
intelligence that thinks, learns, adapts, and grows.

Architecture:
    CognitiveOrchestrator -> OODAEngine -> [MetaReasoner, ToolUseLoop, existing services]

Key principle: Daena already has 80% of the infrastructure (DeepThink, Council,
Quintessence, SkillRefinery, LearningService, NBMF Memory, Autopilot).
This package WIRES them together as one brain with philosophical reasoning
frameworks providing the decision-making DNA.
"""

from app.services.cognition.ooda_engine import OODAEngine, CognitiveState, CognitiveResult
from app.services.cognition.meta_reasoner import MetaReasoner

__all__ = [
    "OODAEngine",
    "CognitiveState",
    "CognitiveResult",
    "MetaReasoner",
]
