"""Subscription authentication model for CLI-based runtimes.

Daena's auth priority: CLI subscription > MCP servers > local models > API keys.
Users bring their existing subscriptions (Claude Max, ChatGPT Pro, Gemini Pro)
instead of paying per-token API fees. API keys are optional fallback only.

Each adapter implements check_subscription() to probe its CLI auth status.
The registry uses SubscriptionAuth results to prioritize routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AuthMethod(Enum):
    """How a runtime authenticates."""
    SUBSCRIPTION = "subscription"   # CLI login (claude, codex, gemini)
    API_KEY = "api_key"             # Environment variable API key
    OAUTH = "oauth"                 # OAuth2 flow (Google, GitHub)
    LOCAL = "local"                 # No auth needed (Ollama)
    MCP = "mcp"                     # MCP server connection


class SubscriptionStatus(Enum):
    """Current subscription auth state."""
    AUTHENTICATED = "authenticated"     # Active session, ready to use
    NOT_AUTHENTICATED = "not_authenticated"  # CLI installed but not logged in
    EXPIRED = "expired"                 # Session expired, needs re-login
    UNKNOWN = "unknown"                 # Could not determine status


@dataclass
class SubscriptionAuth:
    """Result of checking a runtime's subscription/auth status.

    Returned by BaseRuntimeAdapter.check_subscription(). The registry
    uses this to prioritize runtimes with active subscriptions over
    those requiring API keys.
    """
    method: AuthMethod
    status: SubscriptionStatus
    user_display: str | None = None       # e.g., "max@mas-ai.co"
    plan_name: str | None = None          # e.g., "Claude Max", "ChatGPT Pro"
    setup_command: str | None = None      # e.g., "claude login"
    login_url: str | None = None          # e.g., "https://claude.ai/login"
    requires_api_key_fallback: bool = False  # True if no subscription available
    detail: str | None = None             # Extra info for diagnostics

    @property
    def is_authenticated(self) -> bool:
        """Whether this runtime has an active auth session."""
        return self.status == SubscriptionStatus.AUTHENTICATED

    @property
    def priority_score(self) -> int:
        """Higher = higher routing priority.

        Subscription (authenticated) = 100
        Local (no auth needed)       = 80
        MCP (connected)              = 70
        OAuth (authenticated)        = 60
        API key                      = 20
        Not authenticated            = 0
        """
        if self.status != SubscriptionStatus.AUTHENTICATED:
            if self.method == AuthMethod.LOCAL:
                return 80  # Local always available
            return 0

        return {
            AuthMethod.SUBSCRIPTION: 100,
            AuthMethod.LOCAL: 80,
            AuthMethod.MCP: 70,
            AuthMethod.OAUTH: 60,
            AuthMethod.API_KEY: 20,
        }.get(self.method, 10)

    def to_dict(self) -> dict:
        """Serialize for API/frontend."""
        return {
            "method": self.method.value,
            "status": self.status.value,
            "user_display": self.user_display,
            "plan_name": self.plan_name,
            "setup_command": self.setup_command,
            "login_url": self.login_url,
            "is_authenticated": self.is_authenticated,
            "priority_score": self.priority_score,
        }
