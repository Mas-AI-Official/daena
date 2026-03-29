"""Health Monitor -- runtime and tool availability checking with graceful fallback.

The CRITICAL missing piece: when Ollama is offline, when an MCP server is down,
when a cloud API key is expired, the system should RECOVER, not CRASH.

Three responsibilities:
1. Provider health: is this LLM provider actually responding?
2. Tool health: is this tool/MCP server actually callable?
3. Fallback explanation: tell the user WHY a different model/tool was used

The health monitor is the bridge between "tests pass" and "demos don't crash."
"""

from __future__ import annotations

import asyncio
import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class HealthState(str, Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"     # responding but slow or partial
    UNREACHABLE = "unreachable"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class HealthCheck:
    """Result of a single health check."""

    target: str              # "ollama", "anthropic", "tool:jira", etc.
    state: HealthState
    latency_ms: float = 0.0
    error: str | None = None
    checked_at: float = field(default_factory=time.time)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FallbackEvent:
    """Records when and why a fallback was triggered."""

    original_target: str     # what was requested
    fallback_target: str     # what was actually used
    reason: str              # human-readable explanation
    timestamp: float = field(default_factory=time.time)
    cost_impact: str = ""    # e.g., "free -> $0.25/1M" or "no cost change"


class HealthMonitor:
    """Monitors health of LLM providers and tools, manages fallback chain.

    Usage:
        monitor = HealthMonitor()
        monitor.register_provider("ollama", check_fn=ping_ollama)
        monitor.register_provider("anthropic", check_fn=ping_anthropic)

        # Before routing:
        health = await monitor.check_provider("ollama")
        if health.state == HealthState.UNREACHABLE:
            fallback = monitor.get_best_fallback("ollama")

        # After fallback:
        monitor.record_fallback(FallbackEvent(...))
        events = monitor.get_fallback_history()  # show in UI
    """

    def __init__(self) -> None:
        self._provider_health: dict[str, HealthCheck] = {}
        self._tool_health: dict[str, HealthCheck] = {}
        self._fallback_history: list[FallbackEvent] = []
        self._check_fns: dict[str, Any] = {}
        self._lock = threading.Lock()

        # Fallback chain: ordered list of providers from cheapest to most expensive
        self._provider_fallback_chain: list[str] = [
            "ollama",           # free, local
            "groq",             # cheap, fast cloud
            "gemini_flash",     # very cheap cloud
            "anthropic_haiku",  # cheap, high quality
            "openai_mini",      # cheap OpenAI
            "anthropic_sonnet", # mid-tier
            "openai_gpt4o",     # expensive but reliable
        ]

    # ── Provider Health ───────────────────────────────────────

    def register_provider(
        self,
        provider_id: str,
        check_fn: Any = None,
    ) -> None:
        """Register a provider with optional health check function."""
        with self._lock:
            self._provider_health[provider_id] = HealthCheck(
                target=provider_id,
                state=HealthState.UNKNOWN,
                checked_at=0,  # force first check to bypass cache
            )
            if check_fn:
                self._check_fns[provider_id] = check_fn

    async def check_provider(self, provider_id: str) -> HealthCheck:
        """Check if a provider is healthy. Returns cached result if recent."""
        with self._lock:
            cached = self._provider_health.get(provider_id)
            if cached and (time.time() - cached.checked_at) < 30:
                return cached  # cache for 30 seconds

        check_fn = self._check_fns.get(provider_id)
        if check_fn:
            start = time.perf_counter()
            try:
                result = await check_fn()
                latency = (time.perf_counter() - start) * 1000
                health = HealthCheck(
                    target=provider_id,
                    state=HealthState.HEALTHY if result else HealthState.DEGRADED,
                    latency_ms=round(latency, 1),
                )
            except Exception as e:
                latency = (time.perf_counter() - start) * 1000
                health = HealthCheck(
                    target=provider_id,
                    state=HealthState.UNREACHABLE,
                    latency_ms=round(latency, 1),
                    error=str(e),
                )
        else:
            # No check function: assume unknown
            health = HealthCheck(
                target=provider_id,
                state=HealthState.UNKNOWN,
            )

        with self._lock:
            self._provider_health[provider_id] = health
        return health

    def set_provider_health(
        self,
        provider_id: str,
        state: HealthState,
        error: str | None = None,
    ) -> None:
        """Manually set provider health (e.g., after a failed LLM call)."""
        with self._lock:
            self._provider_health[provider_id] = HealthCheck(
                target=provider_id,
                state=state,
                error=error,
            )

    def get_provider_health(self, provider_id: str) -> HealthCheck:
        """Get last known health for a provider."""
        with self._lock:
            return self._provider_health.get(
                provider_id,
                HealthCheck(target=provider_id, state=HealthState.UNKNOWN),
            )

    def get_all_provider_health(self) -> dict[str, HealthCheck]:
        """Get health status of all registered providers."""
        with self._lock:
            return dict(self._provider_health)

    # ── Tool Health ───────────────────────────────────────────

    def set_tool_health(
        self,
        tool_id: str,
        state: HealthState,
        error: str | None = None,
    ) -> None:
        """Record tool health after an execution attempt."""
        with self._lock:
            self._tool_health[tool_id] = HealthCheck(
                target=f"tool:{tool_id}",
                state=state,
                error=error,
            )

    def get_tool_health(self, tool_id: str) -> HealthCheck:
        """Get last known health for a tool."""
        with self._lock:
            return self._tool_health.get(
                tool_id,
                HealthCheck(target=f"tool:{tool_id}", state=HealthState.UNKNOWN),
            )

    def is_tool_healthy(self, tool_id: str) -> bool:
        """Quick check: is this tool likely to work?"""
        health = self.get_tool_health(tool_id)
        return health.state in (HealthState.HEALTHY, HealthState.UNKNOWN)

    # ── Fallback Chain ────────────────────────────────────────

    def get_best_fallback(
        self,
        failed_provider: str,
        exclude: list[str] | None = None,
    ) -> str | None:
        """Find the next best provider after a failure.

        Walks the fallback chain, skipping the failed provider and
        any providers known to be unreachable.
        """
        exclude_set = set(exclude or [])
        exclude_set.add(failed_provider)

        with self._lock:
            for provider_id in self._provider_fallback_chain:
                if provider_id in exclude_set:
                    continue
                health = self._provider_health.get(provider_id)
                if health and health.state == HealthState.UNREACHABLE:
                    continue
                return provider_id

        return None

    def get_fallback_chain(self) -> list[str]:
        """Return the full fallback chain (for display/config)."""
        return list(self._provider_fallback_chain)

    def set_fallback_chain(self, chain: list[str]) -> None:
        """Override the fallback chain (user-configurable)."""
        self._provider_fallback_chain = list(chain)

    # ── Fallback History ──────────────────────────────────────

    def record_fallback(self, event: FallbackEvent) -> None:
        """Record a fallback event for user visibility."""
        with self._lock:
            self._fallback_history.append(event)

    def get_fallback_history(self, limit: int = 20) -> list[FallbackEvent]:
        """Get recent fallback events (shown in UI as notifications)."""
        with self._lock:
            return list(self._fallback_history[-limit:])

    def get_fallback_summary(self) -> dict[str, Any]:
        """Summary of fallback activity for dashboard."""
        with self._lock:
            total = len(self._fallback_history)
            if not total:
                return {"total_fallbacks": 0, "providers_affected": []}

            affected = set()
            for event in self._fallback_history:
                affected.add(event.original_target)

            return {
                "total_fallbacks": total,
                "providers_affected": sorted(affected),
                "last_fallback": self._fallback_history[-1].reason if self._fallback_history else None,
            }

    # ── Graceful Error Messages ───────────────────────────────

    @staticmethod
    def format_fallback_message(event: FallbackEvent) -> str:
        """Format a user-friendly fallback notification.

        Instead of: "ConnectionError: Connection refused"
        Show: "Ollama is offline. Routed to Claude Haiku ($0.25/1M). Your query was handled successfully."
        """
        return (
            f"{event.original_target} is unavailable. "
            f"Routed to {event.fallback_target}. "
            f"{event.cost_impact}. "
            f"Reason: {event.reason}"
        )

    @staticmethod
    def format_tool_unavailable(tool_id: str, error: str) -> str:
        """Format a user-friendly tool unavailability message.

        Instead of: "RuntimeError: MCP server connection refused"
        Show: "Jira is currently unavailable. Your request was queued. The agent will retry or adapt."
        """
        return (
            f"Tool '{tool_id}' is currently unavailable ({error}). "
            "The agent will adapt and use available tools."
        )

    # ── Cleanup ───────────────────────────────────────────────

    def clear_history(self) -> None:
        with self._lock:
            self._fallback_history.clear()

    def clear_all(self) -> None:
        with self._lock:
            self._provider_health.clear()
            self._tool_health.clear()
            self._fallback_history.clear()
