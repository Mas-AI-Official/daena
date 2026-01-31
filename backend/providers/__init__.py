"""
Moltbot-style provider adapters: Discord, Telegram (or Slack).
Credentials from env only. Provider messages never call tools directly;
they create ToolRequests that go through the Execution Layer (allowlist, approval, audit).
"""

from backend.providers.base import ProviderBase, ProviderStatus, InboundMessage
from backend.providers.registry import get_provider_registry

__all__ = ["ProviderBase", "ProviderStatus", "InboundMessage", "get_provider_registry"]
