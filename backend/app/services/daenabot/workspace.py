"""Workspace: persistent context for DaenaBot actions within a session.

Tracks results from previous actions so multi-step plans can
chain outputs (e.g., read file then summarize content).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ActionResult:
    """Result from a single action execution."""

    step_index: int
    agent: str
    operation: str
    success: bool
    output: Any = None
    error: str | None = None


class Workspace:
    """Persistent context for DaenaBot actions within a session."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.results: list[ActionResult] = []
        self.working_directory: str = "."

    def add_result(self, result: ActionResult) -> None:
        """Record an action result."""
        self.results.append(result)
        logger.info(
            "workspace.result_added",
            session_id=self.session_id,
            step=result.step_index,
            agent=result.agent,
            success=result.success,
        )

    def get_last_output(self) -> Any:
        """Get the output from the most recent successful action."""
        for result in reversed(self.results):
            if result.success and result.output is not None:
                return result.output
        return None

    def get_context_summary(self) -> str:
        """Format previous results as context for LLM or next step."""
        if not self.results:
            return ""

        parts: list[str] = []
        for r in self.results:
            status = "OK" if r.success else f"FAILED: {r.error}"
            output_preview = ""
            if r.output is not None:
                output_str = str(r.output)
                output_preview = (
                    output_str[:500] if len(output_str) > 500 else output_str
                )
            parts.append(
                f"Step {r.step_index}: {r.agent}.{r.operation} -> {status}"
                + (f"\n  Output: {output_preview}" if output_preview else "")
            )
        return "\n".join(parts)

    @property
    def all_succeeded(self) -> bool:
        """Check if all recorded actions succeeded."""
        return all(r.success for r in self.results) if self.results else True

    @property
    def has_failures(self) -> bool:
        """Check if any action failed."""
        return any(not r.success for r in self.results)
