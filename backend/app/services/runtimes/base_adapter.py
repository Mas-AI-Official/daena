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
  - Structured probe (Phase 4b PR 2): real round-trip producing the
    6 V2 truth dimensions (detected / configured / reachable /
    authenticated / callable) plus failure_dim + failure_reason.

All methods are async to support concurrent health checks and
parallel task execution across multiple runtimes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime, timezone
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
class RuntimeProbeResult:
    """Phase 4b PR 2: Structured probe outcome for the V2 truth model.

    Replaces the lying "binary exists == online" pattern in legacy
    check_health(). All 5 truth dims map directly to ConnectionV2
    columns; ``failure_dim`` names which dim is now false (per ADR-002
    D-001 per-dim failure storage). ``last_checked_at`` defaults to
    UTC now.

    Truth contract (founder-locked, ADR-002 + Phase 4b PR 2 spec):
      - detected = True iff binary/server exists at expected location
      - configured = True iff per-kind config schema validates
      - reachable = True iff a transport-level handshake succeeded
        (TCP connect, HTTP 2xx/3xx/4xx, MCP initialize OK, CLI exits
        with version on stdout)
      - authenticated = True iff a credential check passes (token
        valid, OAuth not expired, subscription active)
      - callable = True ONLY iff a harmless real round-trip succeeds
        end-to-end. detected/reachable/authenticated alone never
        flip this dim true.
    """

    detected: bool = False
    configured: bool = False
    reachable: bool = False
    authenticated: bool | None = None  # None = unknown / not applicable
    callable: bool = False

    failure_dim: str | None = None  # which dim failed first
    failure_reason: str | None = None  # plain-English (no secrets)
    duration_ms: int = 0
    last_checked_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Optional auxiliary signal: capabilities discovered during probe
    # (e.g. MCP tools list, model list). Opaque per-kind; consumed by
    # ConnectionRegistryV2 capability side-table writer.
    capabilities: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "detected": self.detected,
            "configured": self.configured,
            "reachable": self.reachable,
            "authenticated": self.authenticated,
            "callable": self.callable,
            "failure_dim": self.failure_dim,
            "failure_reason": self.failure_reason,
            "duration_ms": self.duration_ms,
            "last_checked_at": self.last_checked_at.isoformat(),
            "capabilities_count": len(self.capabilities),
        }


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

    async def probe(self) -> RuntimeProbeResult:
        """Phase 4b PR 2: Structured probe. Default is honest-but-shallow.

        Subclasses (claude_code, codex, gemini_cli, grok_cli, mcp_bridge)
        override this with real round-trip semantics. The default here
        does NOT lie -- it derives only ``detected`` from check_installed
        and leaves callable=False so legacy adapters that haven't been
        rewritten yet cannot be misread as "callable" by the V2
        registry.

        Returns:
            RuntimeProbeResult with detected/callable populated. Other
            dims default False (or None for authenticated when not
            applicable).
        """
        import time as _time

        start = _time.perf_counter()
        try:
            installed = await self.check_installed()
        except Exception as exc:  # noqa: BLE001 -- contract: never raise
            return RuntimeProbeResult(
                detected=False,
                failure_dim="detected",
                failure_reason=f"check_installed raised: {type(exc).__name__}",
                duration_ms=int((_time.perf_counter() - start) * 1000),
            )
        return RuntimeProbeResult(
            detected=bool(installed),
            failure_dim=None if installed else "detected",
            failure_reason=None if installed else "binary not found",
            duration_ms=int((_time.perf_counter() - start) * 1000),
        )

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.runtime_id!r}>"
