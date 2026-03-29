"""Subscription Awareness Service: tracks runtime auth status and limits.

Each runtime adapter has auth requirements (API key, CLI login, subscription).
This service monitors subscription state, detects rate limits and expirations,
and provides status info to the UI and auto-routing engine.

When a runtime is rate-limited or expired:
  1. UI shows status: "Claude Code: Rate limited (resets in 2h)"
  2. Auto-routing skips that runtime
  3. Suggests alternatives: "Codex is available for this task"
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


class SubscriptionTier(str, Enum):
    """Subscription level for a runtime."""
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    MAX = "max"
    ENTERPRISE = "enterprise"
    UNKNOWN = "unknown"


class AuthMethod(str, Enum):
    """How a runtime authenticates."""
    NONE = "none"
    API_KEY = "api_key"
    CLI_LOGIN = "cli_login"
    OAUTH = "oauth"


@dataclass
class RuntimeSubscription:
    """Subscription state for a single runtime.

    Attributes:
        runtime_id: Which runtime this tracks.
        auth_method: How this runtime authenticates.
        is_authenticated: Whether credentials are valid.
        subscription_tier: Current subscription level.
        rate_limited: Currently rate-limited.
        rate_limit_resets_at: When rate limit resets (ISO timestamp).
        daily_limit: Max requests/tokens per day (0 = unlimited).
        daily_used: Current day's usage.
        monthly_limit: Max requests/tokens per month (0 = unlimited).
        monthly_used: Current month's usage.
        expires_at: When subscription expires (None = no expiry).
        last_checked: Last health check timestamp.
        setup_instructions: How to set up this runtime.
        setup_command: CLI command for setup.
    """

    runtime_id: str = ""
    auth_method: AuthMethod = AuthMethod.NONE
    is_authenticated: bool = False
    subscription_tier: SubscriptionTier = SubscriptionTier.UNKNOWN
    rate_limited: bool = False
    rate_limit_resets_at: str | None = None
    daily_limit: int = 0
    daily_used: int = 0
    monthly_limit: int = 0
    monthly_used: int = 0
    expires_at: str | None = None
    last_checked: str = ""
    setup_instructions: str = ""
    setup_command: str = ""

    @property
    def is_available(self) -> bool:
        """Whether this runtime can accept requests right now."""
        if not self.is_authenticated:
            return False
        if self.rate_limited:
            return False
        if self.daily_limit > 0 and self.daily_used >= self.daily_limit:
            return False
        return not (
            self.monthly_limit > 0
            and self.monthly_used >= self.monthly_limit
        )

    @property
    def status_message(self) -> str:
        """Human-readable status for UI display."""
        if not self.is_authenticated:
            return "Not authenticated"
        if self.rate_limited:
            if self.rate_limit_resets_at:
                return f"Rate limited (resets at {self.rate_limit_resets_at})"
            return "Rate limited"
        if self.daily_limit > 0:
            remaining = self.daily_limit - self.daily_used
            if remaining <= 0:
                return "Daily limit reached"
            return f"{remaining} requests remaining today"
        return "Available"

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API responses."""
        return {
            "runtime_id": self.runtime_id,
            "auth_method": self.auth_method.value,
            "is_authenticated": self.is_authenticated,
            "subscription_tier": self.subscription_tier.value,
            "is_available": self.is_available,
            "rate_limited": self.rate_limited,
            "rate_limit_resets_at": self.rate_limit_resets_at,
            "daily_limit": self.daily_limit,
            "daily_used": self.daily_used,
            "monthly_limit": self.monthly_limit,
            "monthly_used": self.monthly_used,
            "expires_at": self.expires_at,
            "status_message": self.status_message,
            "last_checked": self.last_checked,
            "setup_instructions": self.setup_instructions,
            "setup_command": self.setup_command,
        }


# ── Default runtime subscription profiles ──

_DEFAULT_SUBSCRIPTIONS: dict[str, dict[str, Any]] = {
    "claude_code": {
        "auth_method": AuthMethod.CLI_LOGIN,
        "subscription_tier": SubscriptionTier.PRO,
        "setup_instructions": (
            "Claude Code requires an Anthropic account with Pro or Max subscription."
        ),
        "setup_command": "claude login",
    },
    "codex": {
        "auth_method": AuthMethod.API_KEY,
        "subscription_tier": SubscriptionTier.PRO,
        "setup_instructions": "OpenAI Codex requires an API key with billing enabled.",
        "setup_command": "export OPENAI_API_KEY=<your-key>",
    },
    "gemini_cli": {
        "auth_method": AuthMethod.CLI_LOGIN,
        "subscription_tier": SubscriptionTier.FREE,
        "setup_instructions": "Gemini CLI requires a Google account.",
        "setup_command": "gemini login",
    },
    "grok_cli": {
        "auth_method": AuthMethod.API_KEY,
        "subscription_tier": SubscriptionTier.PRO,
        "setup_instructions": "Grok CLI requires an xAI API key.",
        "setup_command": "export GROK_API_KEY=<your-key>",
    },
    "ollama": {
        "auth_method": AuthMethod.NONE,
        "subscription_tier": SubscriptionTier.FREE,
        "is_authenticated": True,
        "setup_instructions": "Ollama runs locally. Install from ollama.com.",
        "setup_command": "ollama serve",
    },
}


class SubscriptionService:
    """Tracks runtime subscription state and availability.

    Used by:
    - RuntimeRegistry: skip unavailable runtimes during selection
    - UI: show subscription status in Runtime Swapper
    - Auto-routing: suggest alternatives for rate-limited runtimes

    Usage::

        service = SubscriptionService()
        service.initialize_defaults()
        sub = service.get("claude_code")
        if not sub.is_available:
            alt = service.suggest_alternative("claude_code", "code_generation")
    """

    def __init__(self) -> None:
        self._subscriptions: dict[str, RuntimeSubscription] = {}

    def initialize_defaults(self) -> None:
        """Load default subscription profiles for all known runtimes."""
        for runtime_id, profile in _DEFAULT_SUBSCRIPTIONS.items():
            sub = RuntimeSubscription(runtime_id=runtime_id)
            for key, value in profile.items():
                if hasattr(sub, key):
                    setattr(sub, key, value)
            sub.last_checked = datetime.now(UTC).isoformat()
            self._subscriptions[runtime_id] = sub

        logger.info(
            "subscription.defaults_loaded",
            count=len(self._subscriptions),
        )

    def get(self, runtime_id: str) -> RuntimeSubscription | None:
        """Get subscription state for a runtime."""
        return self._subscriptions.get(runtime_id)

    def get_all(self) -> list[RuntimeSubscription]:
        """Get all tracked subscriptions."""
        return list(self._subscriptions.values())

    def get_available(self) -> list[RuntimeSubscription]:
        """Get only available (non-rate-limited, authenticated) runtimes."""
        return [s for s in self._subscriptions.values() if s.is_available]

    def set_authenticated(
        self,
        runtime_id: str,
        authenticated: bool,
        tier: SubscriptionTier | None = None,
    ) -> RuntimeSubscription | None:
        """Update authentication state for a runtime.

        Args:
            runtime_id: Runtime to update.
            authenticated: Whether credentials are valid.
            tier: Optional subscription tier update.

        Returns:
            Updated subscription, or None if not found.
        """
        sub = self._subscriptions.get(runtime_id)
        if not sub:
            return None

        sub.is_authenticated = authenticated
        if tier:
            sub.subscription_tier = tier
        sub.last_checked = datetime.now(UTC).isoformat()

        logger.info(
            "subscription.auth_updated",
            runtime_id=runtime_id,
            authenticated=authenticated,
        )
        return sub

    def set_rate_limited(
        self,
        runtime_id: str,
        limited: bool,
        resets_at: str | None = None,
    ) -> RuntimeSubscription | None:
        """Mark a runtime as rate-limited.

        Args:
            runtime_id: Runtime to update.
            limited: Whether rate limit is active.
            resets_at: ISO timestamp when limit resets.

        Returns:
            Updated subscription, or None if not found.
        """
        sub = self._subscriptions.get(runtime_id)
        if not sub:
            return None

        sub.rate_limited = limited
        sub.rate_limit_resets_at = resets_at if limited else None
        sub.last_checked = datetime.now(UTC).isoformat()

        logger.info(
            "subscription.rate_limit",
            runtime_id=runtime_id,
            limited=limited,
        )
        return sub

    def record_usage(
        self,
        runtime_id: str,
        count: int = 1,
    ) -> RuntimeSubscription | None:
        """Record usage against daily/monthly limits.

        Args:
            runtime_id: Runtime that was used.
            count: Number of requests to record.

        Returns:
            Updated subscription, or None if not found.
        """
        sub = self._subscriptions.get(runtime_id)
        if not sub:
            return None

        sub.daily_used += count
        sub.monthly_used += count
        return sub

    def suggest_alternative(
        self,
        unavailable_runtime_id: str,
        task_type: str = "",
    ) -> str | None:
        """Suggest an available alternative runtime.

        Args:
            unavailable_runtime_id: Runtime that is unavailable.
            task_type: Optional task type for better matching.

        Returns:
            ID of suggested alternative, or None if nothing available.
        """
        available = [
            s for s in self._subscriptions.values()
            if s.is_available and s.runtime_id != unavailable_runtime_id
        ]
        if not available:
            return None

        # Prefer free runtimes as fallback
        free = [
            s for s in available
            if s.subscription_tier == SubscriptionTier.FREE
        ]
        if free:
            return free[0].runtime_id

        return available[0].runtime_id

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of all subscription states."""
        subs = self.get_all()
        return {
            "total": len(subs),
            "authenticated": sum(1 for s in subs if s.is_authenticated),
            "available": sum(1 for s in subs if s.is_available),
            "rate_limited": sum(1 for s in subs if s.rate_limited),
            "runtimes": [s.to_dict() for s in subs],
        }
