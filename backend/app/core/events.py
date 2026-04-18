"""In-process event bus for decoupled communication.

Lightweight pub/sub for internal events (governance decisions, model health
changes, audit entries). Not a replacement for Celery -- this is for
synchronous/async event propagation within a single process.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Callable, Coroutine
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

# Type alias for async event handlers
EventHandler = Callable[..., Coroutine[Any, Any, None]]


class EventBus:
    """Simple async event bus for internal pub/sub."""

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register an async handler for an event type.

        Args:
            event_type: Event name (e.g., "governance.decision_made").
            handler: Async callable to invoke when event fires.
        """
        self._handlers[event_type].append(handler)
        logger.debug("event_subscribed", event_type=event_type, handler=handler.__name__)

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove a handler from an event type."""
        self._handlers[event_type] = [
            h for h in self._handlers[event_type] if h is not handler
        ]

    async def publish(self, event_type: str, **kwargs: Any) -> None:
        """Fire an event, invoking all registered handlers concurrently.

        Args:
            event_type: Event name.
            **kwargs: Event payload passed to all handlers.
        """
        handlers = self._handlers.get(event_type, [])
        if not handlers:
            return

        logger.debug("event_published", event_type=event_type, handler_count=len(handlers))

        tasks = [asyncio.create_task(h(**kwargs)) for h in handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    "event_handler_error",
                    event_type=event_type,
                    handler=handlers[i].__name__,
                    error=str(result),
                )


# Singleton event bus
event_bus = EventBus()

# ── Runtime Registry singleton (V2) ────────────────────────────
# Initialized lazily on first access or during app startup.

_runtime_registry = None


def get_runtime_registry():
    """Get or create the singleton RuntimeRegistry.

    Registers all known runtime adapters on first call.
    Discovery and health checks happen separately via
    initialize_runtime_registry().
    """
    global _runtime_registry
    if _runtime_registry is not None:
        return _runtime_registry

    from app.services.runtimes.adapters.claude_code import ClaudeCodeAdapter
    from app.services.runtimes.adapters.codex import CodexAdapter
    from app.services.runtimes.adapters.gemini_cli import GeminiCLIAdapter
    from app.services.runtimes.adapters.grok_cli import GrokCLIAdapter
    from app.services.runtimes.adapters.ollama_adapter import OllamaRuntimeAdapter
    from app.services.runtimes.registry import RuntimeRegistry

    registry = RuntimeRegistry()
    registry.register(ClaudeCodeAdapter())
    registry.register(CodexAdapter())
    registry.register(GeminiCLIAdapter())
    registry.register(GrokCLIAdapter())
    registry.register(OllamaRuntimeAdapter())

    _runtime_registry = registry
    return registry


_mcp_registry = None


def get_mcp_registry():
    """Get or create the singleton MCPRegistry.

    Tools are discovered lazily when MCP connections are configured.
    """
    global _mcp_registry
    if _mcp_registry is not None:
        return _mcp_registry

    from app.services.mcp_registry import MCPRegistry

    _mcp_registry = MCPRegistry()
    return _mcp_registry


async def initialize_runtime_registry() -> dict[str, bool]:
    """Discover installed runtimes, check health, and probe subscriptions.

    Called during app startup after model registry init.
    Returns dict of {runtime_id: is_installed}.
    Also starts the recovery monitor for automatic failover recovery.
    """
    registry = get_runtime_registry()
    installed = await registry.discover_all()
    await registry.check_health_all()
    # Probe subscription status for all installed runtimes
    # so the registry can prioritize subscription-authenticated CLIs
    await registry.check_subscriptions_all()

    # Start the recovery monitor (probes dead providers in background)
    try:
        from app.services.runtimes.recovery_monitor import get_recovery_monitor

        monitor = get_recovery_monitor()
        await monitor.start()
    except Exception:
        import logging
        logging.getLogger(__name__).warning("recovery_monitor.start_failed", exc_info=True)

    return installed
