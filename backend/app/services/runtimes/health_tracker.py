"""Runtime Health Tracker -- circuit breaker for LLM provider failover.

Tracks per-provider health with a state machine that enables automatic
failover when a provider goes down, and auto-recovery when it comes back.

State machine per provider:
    HEALTHY -> DEGRADED (2 consecutive failures)
    DEGRADED -> CIRCUIT_OPEN (5 total failures in window)
    CIRCUIT_OPEN -> HALF_OPEN (after cooldown expires)
    HALF_OPEN -> HEALTHY (if probe succeeds)
    HALF_OPEN -> CIRCUIT_OPEN (if probe fails, cooldown doubles)

Error categories determine cooldown duration:
    TRANSIENT (timeout, 503): 60s
    RATE_LIMITED (429): 60s
    SUBSCRIPTION_EXHAUSTED (402, usage cap): 300s
    AUTH_FAILURE (401, 403): permanent until config change

Pure in-memory. Zero latency on happy path. No I/O.

Usage::

    tracker = get_health_tracker()
    if tracker.is_available("ANTHROPIC"):
        try:
            result = await provider.generate(request)
            tracker.record_success("ANTHROPIC")
        except ProviderError as e:
            tracker.record_failure("ANTHROPIC", str(e), ErrorCategory.TRANSIENT)
            # try next provider...
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class ErrorCategory(str, Enum):
    """Classification of provider errors for cooldown strategy."""
    TRANSIENT = "transient"           # timeout, 503, connection refused
    RATE_LIMITED = "rate_limited"     # 429
    SUBSCRIPTION_EXHAUSTED = "subscription_exhausted"  # 402, usage cap
    AUTH_FAILURE = "auth_failure"     # 401, 403
    UNKNOWN = "unknown"


class HealthPhase(str, Enum):
    """Circuit breaker state."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"         # some failures, still trying
    CIRCUIT_OPEN = "circuit_open" # stopped sending requests
    HALF_OPEN = "half_open"       # probing for recovery


# Cooldown durations by error category (seconds)
_COOLDOWN_BY_CATEGORY = {
    ErrorCategory.TRANSIENT: 60.0,
    ErrorCategory.RATE_LIMITED: 60.0,
    ErrorCategory.SUBSCRIPTION_EXHAUSTED: 300.0,
    ErrorCategory.AUTH_FAILURE: 3600.0,  # effectively permanent
    ErrorCategory.UNKNOWN: 60.0,
}

# Thresholds
_FAILURE_THRESHOLD_DEGRADED = 2    # consecutive failures to enter DEGRADED
_FAILURE_THRESHOLD_CIRCUIT = 5     # total failures in window to open circuit
_FAILURE_WINDOW_SECONDS = 120.0    # rolling window for failure counting
_MAX_COOLDOWN_SECONDS = 600.0      # cap for exponential backoff


@dataclass
class ProviderHealthState:
    """Health state for a single provider."""

    provider_id: str
    phase: HealthPhase = HealthPhase.HEALTHY
    consecutive_failures: int = 0
    total_failures_in_window: int = 0
    failure_timestamps: list[float] = field(default_factory=list)
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    last_error_category: ErrorCategory = ErrorCategory.UNKNOWN
    last_error_message: str = ""
    circuit_opened_at: float = 0.0
    recovery_cooldown: float = 60.0
    next_probe_at: float = 0.0
    failover_count: int = 0  # total times this provider caused a failover

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider_id": self.provider_id,
            "phase": self.phase.value,
            "consecutive_failures": self.consecutive_failures,
            "total_failures_in_window": self.total_failures_in_window,
            "last_error_category": self.last_error_category.value,
            "last_error_message": self.last_error_message[:200],
            "failover_count": self.failover_count,
            "recovery_cooldown": self.recovery_cooldown,
        }


class RuntimeHealthTracker:
    """Centralized circuit breaker for all LLM providers.

    Thread-safe (single async event loop). Zero I/O on happy path.
    """

    def __init__(self) -> None:
        self._states: dict[str, ProviderHealthState] = {}

    def _get_state(self, provider_id: str) -> ProviderHealthState:
        """Get or create health state for a provider."""
        if provider_id not in self._states:
            self._states[provider_id] = ProviderHealthState(
                provider_id=provider_id,
            )
        return self._states[provider_id]

    def _prune_old_failures(self, state: ProviderHealthState) -> None:
        """Remove failures outside the rolling window."""
        now = time.monotonic()
        cutoff = now - _FAILURE_WINDOW_SECONDS
        state.failure_timestamps = [
            t for t in state.failure_timestamps if t > cutoff
        ]
        state.total_failures_in_window = len(state.failure_timestamps)

    def record_success(self, provider_id: str) -> None:
        """Record a successful call. Resets failure state."""
        state = self._get_state(provider_id)
        was_degraded = state.phase != HealthPhase.HEALTHY

        state.consecutive_failures = 0
        state.last_success_time = time.monotonic()

        if state.phase == HealthPhase.HALF_OPEN:
            # Recovery probe succeeded -- back to healthy
            state.phase = HealthPhase.HEALTHY
            state.recovery_cooldown = _COOLDOWN_BY_CATEGORY.get(
                state.last_error_category, 60.0,
            )
            logger.info(
                "health_tracker.recovered",
                provider=provider_id,
                was_phase=state.phase.value,
            )
        elif state.phase == HealthPhase.DEGRADED:
            state.phase = HealthPhase.HEALTHY

        if was_degraded:
            logger.info(
                "health_tracker.healthy",
                provider=provider_id,
            )

    def record_failure(
        self,
        provider_id: str,
        error_message: str,
        category: ErrorCategory = ErrorCategory.UNKNOWN,
    ) -> None:
        """Record a failed call. May trigger state transitions."""
        now = time.monotonic()
        state = self._get_state(provider_id)

        state.consecutive_failures += 1
        state.failure_timestamps.append(now)
        state.last_failure_time = now
        state.last_error_category = category
        state.last_error_message = error_message
        state.failover_count += 1

        self._prune_old_failures(state)

        old_phase = state.phase

        # State transitions
        if state.phase == HealthPhase.HALF_OPEN:
            # Probe failed -- back to circuit open with doubled cooldown
            state.phase = HealthPhase.CIRCUIT_OPEN
            state.recovery_cooldown = min(
                state.recovery_cooldown * 2,
                _MAX_COOLDOWN_SECONDS,
            )
            state.circuit_opened_at = now
            state.next_probe_at = now + state.recovery_cooldown

        elif state.total_failures_in_window >= _FAILURE_THRESHOLD_CIRCUIT:
            # Too many failures -- open circuit
            state.phase = HealthPhase.CIRCUIT_OPEN
            state.circuit_opened_at = now
            state.recovery_cooldown = _COOLDOWN_BY_CATEGORY.get(
                category, 60.0,
            )
            state.next_probe_at = now + state.recovery_cooldown

        elif state.consecutive_failures >= _FAILURE_THRESHOLD_DEGRADED:
            state.phase = HealthPhase.DEGRADED

        if state.phase != old_phase:
            logger.warning(
                "health_tracker.state_change",
                provider=provider_id,
                old=old_phase.value,
                new=state.phase.value,
                consecutive=state.consecutive_failures,
                window_total=state.total_failures_in_window,
                error_category=category.value,
                cooldown=state.recovery_cooldown,
            )

    def is_available(self, provider_id: str) -> bool:
        """Check if a provider is available for requests.

        Returns True for HEALTHY, DEGRADED, and HALF_OPEN.
        Returns False for CIRCUIT_OPEN.
        """
        state = self._states.get(provider_id)
        if state is None:
            return True  # unknown provider = assume healthy
        return state.phase != HealthPhase.CIRCUIT_OPEN

    def should_probe(self, provider_id: str) -> bool:
        """Check if a CIRCUIT_OPEN provider should be probed for recovery."""
        state = self._states.get(provider_id)
        if state is None:
            return False
        if state.phase != HealthPhase.CIRCUIT_OPEN:
            return False
        return time.monotonic() >= state.next_probe_at

    def enter_half_open(self, provider_id: str) -> None:
        """Transition CIRCUIT_OPEN -> HALF_OPEN for a recovery probe."""
        state = self._get_state(provider_id)
        if state.phase == HealthPhase.CIRCUIT_OPEN:
            state.phase = HealthPhase.HALF_OPEN
            logger.info(
                "health_tracker.half_open",
                provider=provider_id,
            )

    def get_state(self, provider_id: str) -> ProviderHealthState | None:
        return self._states.get(provider_id)

    def get_all_states(self) -> dict[str, ProviderHealthState]:
        return dict(self._states)

    def classify_error(self, error_message: str) -> ErrorCategory:
        """Classify an error message into a category."""
        msg = error_message.lower()

        if any(w in msg for w in ("timeout", "timed out", "deadline")):
            return ErrorCategory.TRANSIENT
        if any(w in msg for w in ("503", "server busy", "overloaded", "connection refused")):
            return ErrorCategory.TRANSIENT
        if "429" in msg or "rate limit" in msg or "too many" in msg:
            return ErrorCategory.RATE_LIMITED
        if any(w in msg for w in (
            "subscription", "limit", "quota", "402",
            "usage cap", "billing", "exhausted",
        )):
            return ErrorCategory.SUBSCRIPTION_EXHAUSTED
        if any(w in msg for w in ("401", "403", "unauthorized", "forbidden", "auth")):
            return ErrorCategory.AUTH_FAILURE

        return ErrorCategory.UNKNOWN


# ── Module-level singleton ───────────────────────────────────

_health_tracker: RuntimeHealthTracker | None = None


def get_health_tracker() -> RuntimeHealthTracker:
    """Get or create the singleton health tracker."""
    global _health_tracker
    if _health_tracker is None:
        _health_tracker = RuntimeHealthTracker()
    return _health_tracker
