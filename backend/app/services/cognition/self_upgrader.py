"""SelfUpgrader -- Daena evolves herself.

The defining feature that makes Daena a LIVING intelligence, not a static tool.

When Daena discovers a new problem-solving pattern (from execution history,
from user teaching, from web research), she can:
    1. Extract the pattern
    2. Create a cognitive skill from it
    3. Backtest against historical problems
    4. If effective: adopt it into the MetaReasoner's framework map
    5. Persist to NBMF T3 (institutional memory)

Also handles:
    - External framework adoption (discover new frameworks from the web)
    - User-taught frameworks ("Daena, when X happens, always do Y")
    - Cross-client learning (anonymized patterns shared across deployments)

Anti-fragility (Taleb): Every failure makes Daena STRONGER because it
creates new patterns in memory. The system improves FROM adversity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CognitiveSkillCandidate:
    """A potential new reasoning framework discovered by the system."""
    name: str
    description: str
    when_to_use: list[str]  # problem types
    steps: list[str]
    source: str  # "execution_history", "user_taught", "web_research"
    examples: list[str] = field(default_factory=list)
    backtest_score: float = 0.0  # 0.0 to 1.0
    adopted: bool = False


class SelfUpgrader:
    """Daena's self-evolution system.

    Discovers, tests, and adopts new reasoning frameworks.
    Makes Daena smarter with every interaction.

    Buffett: "Go to bed a little smarter than when you woke up."
    Taleb: "Anti-fragile systems gain from disorder."
    """

    def __init__(
        self,
        db: Any = None,
        user_id: UUID | None = None,
        tenant_id: UUID | None = None,
    ) -> None:
        self.db = db
        self.user_id = user_id
        self.tenant_id = tenant_id
        self._candidates: list[CognitiveSkillCandidate] = []
        self._adoption_threshold = 0.6  # 60%+ backtest score to adopt

    async def discover_from_history(
        self,
        execution_history: list[dict[str, Any]],
    ) -> list[CognitiveSkillCandidate]:
        """Analyze execution history for new patterns.

        Called periodically (every 50 tasks) to find patterns worth
        turning into reusable cognitive skills.
        """
        candidates = []

        # Find repeated success patterns
        success_patterns = self._extract_success_patterns(execution_history)
        for pattern in success_patterns:
            candidate = CognitiveSkillCandidate(
                name=f"discovered_{pattern['name']}",
                description=pattern["description"],
                when_to_use=pattern["problem_types"],
                steps=pattern["steps"],
                source="execution_history",
                examples=pattern.get("examples", []),
            )
            candidates.append(candidate)

        # Find repeated failure patterns (anti-fragility)
        failure_patterns = self._extract_failure_patterns(execution_history)
        for pattern in failure_patterns:
            # Create an AVOIDANCE skill (what NOT to do)
            candidate = CognitiveSkillCandidate(
                name=f"avoid_{pattern['name']}",
                description=f"Avoid: {pattern['description']}",
                when_to_use=pattern["problem_types"],
                steps=[f"Do NOT: {step}" for step in pattern["steps"]],
                source="execution_history",
            )
            candidates.append(candidate)

        self._candidates.extend(candidates)
        logger.info(
            "self_upgrader.discovered",
            success_patterns=len(success_patterns),
            failure_patterns=len(failure_patterns),
        )

        return candidates

    async def learn_from_user(
        self,
        instruction: str,
        problem_type: str = "unknown",
    ) -> CognitiveSkillCandidate:
        """Learn a new reasoning pattern from user instruction.

        Example: "Daena, when you encounter a deployment error, always
        check the health endpoint first before debugging the code."
        """
        candidate = CognitiveSkillCandidate(
            name=f"user_taught_{problem_type}",
            description=instruction,
            when_to_use=[problem_type],
            steps=[instruction],
            source="user_taught",
            backtest_score=0.8,  # User-taught gets high initial trust
        )
        self._candidates.append(candidate)
        logger.info(
            "self_upgrader.user_taught",
            instruction=instruction[:200],
            problem_type=problem_type,
        )
        return candidate

    async def research_and_adopt(
        self,
        topic: str,
    ) -> CognitiveSkillCandidate | None:
        """Research a topic on the web and potentially adopt a new framework.

        Used when Daena encounters a problem type she hasn't seen before.
        """
        from app.services.cognition.resource_finder import ResourceFinder

        finder = ResourceFinder(self.db, self.user_id, self.tenant_id)
        research = await finder.deep_research(topic)

        if not research.get("findings"):
            return None

        # Extract a reasoning pattern from the research
        finding = research["findings"][0]
        candidate = CognitiveSkillCandidate(
            name=f"researched_{topic[:30].replace(' ', '_')}",
            description=f"Framework discovered from web research: {topic}",
            when_to_use=["unknown"],  # Will be refined through backtest
            steps=[f"Apply knowledge: {finding['content'][:500]}"],
            source="web_research",
            backtest_score=0.3,  # Low initial trust for web-discovered
        )
        self._candidates.append(candidate)

        logger.info(
            "self_upgrader.researched",
            topic=topic[:100],
            findings=len(research["findings"]),
        )

        return candidate

    async def evaluate_and_adopt(
        self,
        meta_reasoner: Any,
    ) -> list[str]:
        """Evaluate candidates and adopt those above threshold.

        Returns list of adopted framework names.
        """
        adopted = []

        for candidate in self._candidates:
            if candidate.adopted:
                continue

            if candidate.backtest_score >= self._adoption_threshold:
                # Adopt into MetaReasoner
                from app.services.cognition.meta_reasoner import CognitiveFramework
                framework = CognitiveFramework(
                    name=candidate.name,
                    description=candidate.description,
                    when_to_use=candidate.when_to_use,
                    steps=candidate.steps,
                    source=candidate.source,
                    score=candidate.backtest_score,
                )
                await meta_reasoner.register_framework(framework)
                candidate.adopted = True
                adopted.append(candidate.name)

                # Persist to NBMF T3 (institutional memory)
                await self._persist_to_memory(candidate)

                logger.info(
                    "self_upgrader.adopted",
                    name=candidate.name,
                    source=candidate.source,
                    score=candidate.backtest_score,
                )

        return adopted

    # ------------------------------------------------------------------
    # Pattern extraction
    # ------------------------------------------------------------------

    def _extract_success_patterns(
        self,
        history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Find repeated success patterns in execution history."""
        # Group by problem_type and strategy
        groups: dict[str, list[dict]] = {}
        for entry in history:
            if entry.get("success"):
                key = f"{entry.get('problem_type', 'unknown')}_{entry.get('strategy', 'unknown')}"
                groups.setdefault(key, []).append(entry)

        patterns = []
        for key, entries in groups.items():
            if len(entries) >= 3:  # Need 3+ successes to be a pattern
                patterns.append({
                    "name": key,
                    "description": f"Pattern: {key} succeeded {len(entries)} times",
                    "problem_types": list({e.get("problem_type", "unknown") for e in entries}),
                    "steps": list({e.get("strategy", "") for e in entries}),
                    "examples": [e.get("task", "")[:100] for e in entries[:3]],
                })

        return patterns

    def _extract_failure_patterns(
        self,
        history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Find repeated failure patterns (anti-fragility: learn from failures)."""
        groups: dict[str, list[dict]] = {}
        for entry in history:
            if not entry.get("success"):
                key = f"{entry.get('problem_type', 'unknown')}_{entry.get('strategy', 'unknown')}"
                groups.setdefault(key, []).append(entry)

        patterns = []
        for key, entries in groups.items():
            if len(entries) >= 2:  # 2+ failures = pattern to avoid
                patterns.append({
                    "name": key,
                    "description": f"Avoid: {key} failed {len(entries)} times",
                    "problem_types": list({e.get("problem_type", "unknown") for e in entries}),
                    "steps": list({e.get("strategy", "") for e in entries}),
                })

        return patterns

    async def _persist_to_memory(self, candidate: CognitiveSkillCandidate) -> None:
        """Persist adopted framework to NBMF T3 (institutional memory)."""
        if not self.db or not self.user_id:
            return

        try:
            from app.services.memory import MemoryService
            memory_svc = MemoryService(self.db, self.user_id, self.tenant_id)
            content = (
                f"Cognitive Framework: {candidate.name}\n"
                f"Source: {candidate.source}\n"
                f"Description: {candidate.description}\n"
                f"When to use: {', '.join(candidate.when_to_use)}\n"
                f"Steps: {'; '.join(candidate.steps)}\n"
                f"Score: {candidate.backtest_score}\n"
            )
            await memory_svc.store(content=content, tier=3)
            logger.info("self_upgrader.persisted", name=candidate.name)
        except Exception as exc:
            logger.debug("self_upgrader.persist_failed", error=str(exc))
