"""LearningService -- outcome tracking and skill auto-extraction.

Closes the learning loop in Daena's execution pipeline:
    1. Track outcomes of every DaenaBot action
    2. Evaluate success/failure patterns
    3. Auto-extract reusable skills from successful multi-step workflows
    4. Feed learnings back into Skill Refinery (T0 memory -> refinement)
    5. Track failure patterns to improve future planning

This service connects:
    - Workspace (action results) -> LearningService (evaluation)
    - LearningService -> SkillRefinery (skill extraction)
    - LearningService -> NBMF Memory (pattern storage)

Does NOT auto-apply changes. Learned patterns are stored as T0 memories
and must go through the standard promotion pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.core.logging import get_logger

logger = get_logger(__name__)

# Thresholds for learning extraction
_MIN_STEPS_FOR_SKILL = 3  # Need at least 3 successful steps to extract a skill
_SUCCESS_RATE_THRESHOLD = 0.8  # 80% success rate to consider a pattern worth learning
_MAX_STORED_PATTERNS = 500  # Cap in-memory pattern storage


@dataclass
class ActionOutcome:
    """Tracked outcome of a DaenaBot action."""

    action_id: str
    session_id: str
    agent: str
    operation: str
    params: dict[str, Any]
    success: bool
    output_preview: str = ""
    error: str | None = None
    duration_ms: int = 0
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    governance_tier: int = 0
    user_feedback: str | None = None  # "good" | "bad" | None


@dataclass
class LearnedPattern:
    """A pattern extracted from successful action sequences."""

    pattern_id: str
    pattern_type: str  # "workflow" | "tool_usage" | "error_recovery"
    description: str
    steps: list[dict[str, Any]]
    success_count: int = 0
    failure_count: int = 0
    confidence: float = 0.0
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    last_used: str = ""
    tags: list[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else 0.0


class LearningService:
    """Tracks action outcomes and extracts reusable patterns.

    Usage::

        learning = LearningService()

        # Track an outcome
        await learning.track_outcome(ActionOutcome(
            action_id="abc-123",
            session_id="session-1",
            agent="web_crawler",
            operation="extract_page",
            params={"url": "https://example.com"},
            success=True,
            output_preview="Page content...",
            duration_ms=1500,
        ))

        # After a multi-step workflow completes
        skills = await learning.extract_skills_from_session("session-1")

        # Get suggestions for improving future actions
        suggestions = learning.get_suggestions("web_crawler", "extract_page")
    """

    def __init__(self) -> None:
        self._outcomes: list[ActionOutcome] = []
        self._patterns: dict[str, LearnedPattern] = {}
        self._session_outcomes: dict[str, list[ActionOutcome]] = {}

    async def track_outcome(self, outcome: ActionOutcome) -> None:
        """Record an action outcome for learning.

        Args:
            outcome: The outcome to track.
        """
        self._outcomes.append(outcome)

        # Index by session
        if outcome.session_id not in self._session_outcomes:
            self._session_outcomes[outcome.session_id] = []
        self._session_outcomes[outcome.session_id].append(outcome)

        # Cap storage
        if len(self._outcomes) > _MAX_STORED_PATTERNS * 10:
            self._outcomes = self._outcomes[-_MAX_STORED_PATTERNS * 5:]

        logger.info(
            "learning.outcome_tracked",
            agent=outcome.agent,
            operation=outcome.operation,
            success=outcome.success,
            session_id=outcome.session_id,
        )

        # Update pattern confidence if this matches a known pattern
        await self._update_patterns(outcome)

    async def track_user_feedback(
        self,
        action_id: str,
        feedback: str,
    ) -> None:
        """Record user feedback on an action outcome.

        Args:
            action_id: ID of the action.
            feedback: "good" or "bad".
        """
        for outcome in reversed(self._outcomes):
            if outcome.action_id == action_id:
                outcome.user_feedback = feedback
                logger.info(
                    "learning.feedback_recorded",
                    action_id=action_id,
                    feedback=feedback,
                )
                return

    async def extract_skills_from_session(
        self,
        session_id: str,
    ) -> list[dict[str, Any]]:
        """Extract reusable skills from a session's action history.

        Analyzes the sequence of actions in a session, identifies
        successful multi-step patterns, and creates skill candidates
        for the Skill Refinery.

        Args:
            session_id: Session to analyze.

        Returns:
            List of skill candidates (dict with name, description, steps, confidence).
        """
        outcomes = self._session_outcomes.get(session_id, [])
        if len(outcomes) < _MIN_STEPS_FOR_SKILL:
            return []

        # Calculate session success rate
        successes = sum(1 for o in outcomes if o.success)
        success_rate = successes / len(outcomes)

        if success_rate < _SUCCESS_RATE_THRESHOLD:
            logger.info(
                "learning.session_too_low_success",
                session_id=session_id,
                success_rate=success_rate,
            )
            return []

        # Build skill candidate from successful action sequence
        steps = []
        for o in outcomes:
            if o.success:
                steps.append({
                    "agent": o.agent,
                    "operation": o.operation,
                    "params_template": self._generalize_params(o.params),
                    "expected_output": o.output_preview[:200],
                })

        # Create pattern
        pattern = LearnedPattern(
            pattern_id=f"auto_{session_id[:8]}_{len(self._patterns)}",
            pattern_type="workflow",
            description=self._describe_pattern(steps),
            steps=steps,
            success_count=successes,
            confidence=success_rate,
            tags=list({o.agent for o in outcomes if o.success}),
        )
        self._patterns[pattern.pattern_id] = pattern

        skill_candidate = {
            "name": pattern.description[:100],
            "description": pattern.description,
            "steps": steps,
            "confidence": success_rate,
            "pattern_id": pattern.pattern_id,
            "source": "auto_extracted",
            "session_id": session_id,
        }

        logger.info(
            "learning.skill_extracted",
            session_id=session_id,
            pattern_id=pattern.pattern_id,
            steps=len(steps),
            confidence=success_rate,
        )

        return [skill_candidate]

    def get_suggestions(
        self,
        agent: str,
        operation: str,
    ) -> list[dict[str, Any]]:
        """Get improvement suggestions based on past outcomes.

        Args:
            agent: Agent name.
            operation: Operation name.

        Returns:
            List of suggestions with type, description, and confidence.
        """
        # Find outcomes for this agent+operation
        relevant = [
            o for o in self._outcomes
            if o.agent == agent and o.operation == operation
        ]

        if not relevant:
            return []

        suggestions: list[dict[str, Any]] = []

        # Check failure rate
        failures = [o for o in relevant if not o.success]
        if failures:
            failure_rate = len(failures) / len(relevant)
            if failure_rate > 0.3:
                common_errors = {}
                for f in failures:
                    err = f.error or "unknown"
                    common_errors[err] = common_errors.get(err, 0) + 1

                top_error = max(common_errors, key=common_errors.get)
                suggestions.append({
                    "type": "error_pattern",
                    "description": (
                        f"{agent}.{operation} has {failure_rate:.0%} failure rate. "
                        f"Most common error: {top_error}"
                    ),
                    "confidence": failure_rate,
                })

        # Check for timeout patterns
        slow_actions = [o for o in relevant if o.duration_ms > 30000]
        if slow_actions and len(slow_actions) / len(relevant) > 0.2:
            suggestions.append({
                "type": "performance",
                "description": (
                    f"{agent}.{operation} is frequently slow "
                    f"({len(slow_actions)}/{len(relevant)} actions > 30s). "
                    f"Consider reducing scope or adding timeout guards."
                ),
                "confidence": len(slow_actions) / len(relevant),
            })

        return suggestions

    def get_session_summary(self, session_id: str) -> dict[str, Any]:
        """Get a learning summary for a session.

        Args:
            session_id: Session to summarize.

        Returns:
            Dict with action count, success rate, patterns found, suggestions.
        """
        outcomes = self._session_outcomes.get(session_id, [])
        if not outcomes:
            return {"actions": 0, "success_rate": 0.0, "patterns": [], "suggestions": []}

        successes = sum(1 for o in outcomes if o.success)
        agents_used = list({o.agent for o in outcomes})
        operations_used = list({f"{o.agent}.{o.operation}" for o in outcomes})

        return {
            "actions": len(outcomes),
            "success_rate": successes / len(outcomes),
            "agents_used": agents_used,
            "operations_used": operations_used,
            "failures": [
                {"agent": o.agent, "operation": o.operation, "error": o.error}
                for o in outcomes if not o.success
            ],
            "total_duration_ms": sum(o.duration_ms for o in outcomes),
        }

    def get_stats(self) -> dict[str, Any]:
        """Get overall learning statistics."""
        total = len(self._outcomes)
        successes = sum(1 for o in self._outcomes if o.success)
        return {
            "total_actions_tracked": total,
            "success_rate": successes / total if total > 0 else 0.0,
            "sessions_tracked": len(self._session_outcomes),
            "patterns_learned": len(self._patterns),
            "top_agents": self._top_agents(),
        }

    # -- Internal ----------------------------------------------------------

    async def _update_patterns(self, outcome: ActionOutcome) -> None:
        """Update pattern confidence based on new outcome."""
        for pattern in self._patterns.values():
            # Check if this outcome matches a step in the pattern
            for step in pattern.steps:
                if (
                    step["agent"] == outcome.agent
                    and step["operation"] == outcome.operation
                ):
                    if outcome.success:
                        pattern.success_count += 1
                    else:
                        pattern.failure_count += 1
                    pattern.last_used = outcome.timestamp
                    pattern.confidence = pattern.success_rate
                    break

    @staticmethod
    def _generalize_params(params: dict[str, Any]) -> dict[str, str]:
        """Generalize concrete params into template placeholders."""
        template = {}
        for key, value in params.items():
            if isinstance(value, str) and (
                value.startswith("http") or "/" in value or "\\" in value
            ):
                template[key] = "{url_or_path}"
            elif isinstance(value, str) and "@" in value:
                template[key] = "{email}"
            elif isinstance(value, (int, float)):
                template[key] = "{number}"
            else:
                template[key] = f"{{{key}}}"
        return template

    @staticmethod
    def _describe_pattern(steps: list[dict[str, Any]]) -> str:
        """Generate a human-readable description of a step pattern."""
        if not steps:
            return "Empty pattern"

        parts = []
        for step in steps:
            parts.append(f"{step['agent']}.{step['operation']}")

        agents = list({s["agent"] for s in steps})
        return (
            f"Multi-step workflow using {', '.join(agents)}: "
            f"{' -> '.join(parts)}"
        )

    def _top_agents(self) -> list[dict[str, Any]]:
        """Get most-used agents with success rates."""
        agent_stats: dict[str, dict[str, int]] = {}
        for o in self._outcomes:
            if o.agent not in agent_stats:
                agent_stats[o.agent] = {"total": 0, "success": 0}
            agent_stats[o.agent]["total"] += 1
            if o.success:
                agent_stats[o.agent]["success"] += 1

        return sorted(
            [
                {
                    "agent": name,
                    "total": stats["total"],
                    "success_rate": stats["success"] / stats["total"],
                }
                for name, stats in agent_stats.items()
            ],
            key=lambda x: x["total"],
            reverse=True,
        )[:5]
