"""Base agent protocol for DaenaBot computer-control agents.

All DaenaBot agents implement this interface.  They are stateless,
do NOT inherit BaseService (no DB access), and return result dicts
that _dispatch_tool() stores in ToolExecution.tool_result.

Agents trust they are pre-authorised — governance is evaluated
BEFORE dispatch in ExecutionService.execute_tool().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class BaseAgent(ABC):
    """Abstract base for all DaenaBot agents."""

    agent_name: str  # e.g. "file", "terminal", "browser"

    # Maps operation → governance action_type string.
    # Used by _dispatch_tool / _resolve_action_type to determine
    # the correct risk classification before calling the agent.
    OPERATION_ACTION_MAP: dict[str, str]

    @abstractmethod
    async def execute(
        self, operation: str, params: dict[str, Any],
    ) -> dict[str, Any]:
        """Route to the correct operation method.

        Args:
            operation: The operation to perform (e.g. "read_file").
            params: Operation-specific parameters.

        Returns:
            Standardised result dict from ``_result()``.

        Raises:
            ValueError: If *operation* is not supported.
        """

    # ── helpers ────────────────────────────────────────────────

    def _result(
        self,
        operation: str,
        output: Any = None,
        *,
        success: bool = True,
        error: str | None = None,
    ) -> dict[str, Any]:
        """Build a standardised result dict."""
        return {
            "agent": self.agent_name,
            "success": success,
            "operation": operation,
            "output": output,
            "error": error,
        }

    def _error(self, operation: str, error: str) -> dict[str, Any]:
        """Shorthand for a failed result."""
        return self._result(operation, success=False, error=error)
