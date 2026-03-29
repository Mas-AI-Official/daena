"""Abstract base class for all runtime adapters.

Every runtime (Claude Code, Codex, Gemini CLI, etc.) implements this
interface so the RuntimeRegistry and SwarmExecutor can treat them
uniformly. Each adapter wraps a CLI subprocess and exposes:
  - Installation check
  - Health/status monitoring
  - Capability scores (0-10 per task type)
  - Streaming task execution
  - Cancellation
  - Auth requirements (static description)
  - Subscription check (dynamic runtime probe)

All methods are async to support concurrent health checks and
parallel task execution across multiple runtimes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RuntimeStatus(Enum):
    """Current operational status of a runtime."""
    ONLINE = "online"
    OFFLINE = "offline"
    RATE_LIMITED = "rate_limited"
    ERROR = "error"
    NOT_INSTALLED = "not_installed"


@dataclass
class RuntimeCapability:
    """Capability scores (0.0-10.0) for each task type.

    Higher = better at that task type. Zero = cannot perform.
    Used by RuntimeRegistry.select_runtime() to pick the best
    runtime for a given task.
    """
    complex_reasoning: float = 0.0
    code_generation: float = 0.0
    code_editing: float = 0.0
    file_operations: float = 0.0
    web_research: float = 0.0
    data_analysis: float = 0.0
    browser_automation: float = 0.0
    simple_chat: float = 0.0
    bulk_operations: float = 0.0
    cost_per_1k_tokens: float = 0.0  # USD, 0 for local/free

    def score_for(self, task_type: str) -> float:
        """Get the capability score for a task type string."""
        return getattr(self, task_type, 0.0)

    def to_dict(self) -> dict[str, float]:
        """Serialize all scores to a dictionary."""
        return {
            "complex_reasoning": self.complex_reasoning,
            "code_generation": self.code_generation,
            "code_editing": self.code_editing,
            "file_operations": self.file_operations,
            "web_research": self.web_research,
            "data_analysis": self.data_analysis,
            "browser_automation": self.browser_automation,
            "simple_chat": self.simple_chat,
            "bulk_operations": self.bulk_operations,
            "cost_per_1k_tokens": self.cost_per_1k_tokens,
        }


@dataclass
class ExecutionReceipt:
    """Audit trail for every runtime execution.

    Created after each task completes (success or failure).
    Stored in governance audit log for traceability.
    """
    runtime_id: str
    task_description: str
    assigned_reason: str
    capability_score: float
    start_time: str
    end_time: str
    duration_ms: int
    token_count: int
    estimated_cost_usd: float
    status: str  # success, error, timeout, rejected, cancelled
    output_summary: str
    governance_tier: str
    approved_by: str | None = None  # "auto", "council", "user_override"
    error_detail: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for audit logging."""
        return {
            "runtime_id": self.runtime_id,
            "task_description": self.task_description,
            "assigned_reason": self.assigned_reason,
            "capability_score": self.capability_score,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "token_count": self.token_count,
            "estimated_cost_usd": self.estimated_cost_usd,
            "status": self.status,
            "output_summary": self.output_summary[:500],
            "governance_tier": self.governance_tier,
            "approved_by": self.approved_by,
            "error_detail": self.error_detail,
            "metadata": self.metadata,
        }


class BaseRuntimeAdapter(ABC):
    """Abstract base class all runtime adapters must implement.

    Subclasses wrap a specific CLI tool (Claude Code, Codex, etc.)
    and provide uniform access for the RuntimeRegistry.
    """

    def __init__(self, runtime_id: str, display_name: str) -> None:
        self.runtime_id = runtime_id
        self.display_name = display_name

    @abstractmethod
    async def check_installed(self) -> bool:
        """Check if this runtime's CLI is installed on the system."""

    @abstractmethod
    async def check_health(self) -> RuntimeStatus:
        """Probe current operational status."""

    @abstractmethod
    async def get_capabilities(self) -> RuntimeCapability:
        """Return capability scores for this runtime."""

    @abstractmethod
    async def execute(
        self, task: str, context: dict[str, Any],
    ) -> AsyncIterator[str]:
        """Execute a task and yield streaming output lines.

        Args:
            task: Natural language task description or structured command.
            context: Execution context (working_directory, session_id,
                     governance_tier, cost_ceiling, etc.)

        Yields:
            Output lines/chunks from the runtime subprocess.
        """

    @abstractmethod
    async def cancel(self, session_id: str) -> bool:
        """Cancel a running task for the given session."""

    @abstractmethod
    def get_auth_requirements(self) -> dict[str, Any]:
        """Describe what credentials/subscriptions this runtime needs (static)."""

    async def check_subscription(self) -> Any:
        """Check if this runtime has an active subscription/auth session.

        Returns a SubscriptionAuth instance. Override in subclasses that
        support CLI subscription login. Default returns UNKNOWN status
        for backwards compatibility.
        """
        from app.services.runtimes.subscription_auth import (
            AuthMethod,
            SubscriptionAuth,
            SubscriptionStatus,
        )

        return SubscriptionAuth(
            method=AuthMethod.API_KEY,
            status=SubscriptionStatus.UNKNOWN,
            detail="check_subscription not implemented for this adapter",
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.runtime_id!r}>"
