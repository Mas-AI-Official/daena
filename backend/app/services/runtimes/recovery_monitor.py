"""Recovery Monitor -- background task that probes dead providers.

Periodically checks CIRCUIT_OPEN providers and attempts recovery.
When a provider comes back online, transitions it to HEALTHY so
the system automatically switches back to the primary brain.

Runs as an asyncio background task started during app startup.
Does NOT interfere with active requests.

Usage::

    monitor = RecoveryMonitor()
    await monitor.start()  # call during app lifespan startup
    # ... app runs ...
    await monitor.stop()   # call during app shutdown
"""

from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.services.runtimes.health_tracker import (
    HealthPhase,
    get_health_tracker,
)

logger = get_logger(__name__)

# How often to scan for providers needing recovery probes
PROBE_INTERVAL_SECONDS = 30.0


class RecoveryMonitor:
    """Background monitor that probes CIRCUIT_OPEN providers."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        """Start the recovery monitor background loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._probe_loop())
        logger.info("recovery_monitor.started")

    async def stop(self) -> None:
        """Stop the recovery monitor."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("recovery_monitor.stopped")

    async def _probe_loop(self) -> None:
        """Main loop: scan for providers needing recovery probes."""
        while self._running:
            try:
                await asyncio.sleep(PROBE_INTERVAL_SECONDS)
                await self._probe_all()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("recovery_monitor.loop_error")

    async def _probe_all(self) -> None:
        """Check all providers and probe ones ready for recovery."""
        tracker = get_health_tracker()
        states = tracker.get_all_states()

        for provider_id, state in states.items():
            if state.phase != HealthPhase.CIRCUIT_OPEN:
                continue

            if not tracker.should_probe(provider_id):
                continue

            # Transition to HALF_OPEN and probe
            tracker.enter_half_open(provider_id)
            success = await self._probe_provider(provider_id)

            if success:
                tracker.record_success(provider_id)
                logger.info(
                    "recovery_monitor.provider_recovered",
                    provider=provider_id,
                    downtime_s=round(
                        state.last_success_time - state.circuit_opened_at
                        if state.last_success_time > state.circuit_opened_at
                        else 0, 1,
                    ),
                )
            else:
                tracker.record_failure(
                    provider_id,
                    "recovery probe failed",
                    state.last_error_category,
                )
                logger.info(
                    "recovery_monitor.probe_failed",
                    provider=provider_id,
                    next_cooldown=state.recovery_cooldown,
                )

    async def _probe_provider(self, provider_id: str) -> bool:
        """Send a lightweight probe to check if a provider is alive.

        Uses the ModelRegistry to find the provider and sends a
        minimal generate request ("Say OK", max_tokens=5).
        """
        try:
            from app.core.events import get_runtime_registry
            from app.services.providers.base import GenerateRequest, LLMMessage

            # Try CLI health check first (fast, no API cost)
            rt_registry = get_runtime_registry()
            adapter = rt_registry.get_adapter(provider_id)
            if adapter is not None:
                installed = await adapter.check_installed()
                if not installed:
                    return False
                health = await adapter.check_health()
                from app.services.runtimes.base_adapter import RuntimeStatus
                return health == RuntimeStatus.ONLINE

            # For API providers: minimal generate request
            from app.services.model_registry import ModelRegistry

            registry = ModelRegistry()
            await registry.initialize()

            prov = None
            for p_enum in registry.available_providers:
                if p_enum.value == provider_id:
                    prov = registry.get_provider(p_enum)
                    break

            if prov is None:
                return False

            request = GenerateRequest(
                messages=[LLMMessage(role="user", content="Say OK")],
                temperature=0.0,
                max_tokens=5,
            )
            resp = await asyncio.wait_for(prov.generate(request), timeout=30.0)
            return bool(resp.content)

        except Exception as exc:
            logger.debug(
                "recovery_monitor.probe_error",
                provider=provider_id,
                error=str(exc)[:100],
            )
            return False


# Module-level singleton
_monitor: RecoveryMonitor | None = None


def get_recovery_monitor() -> RecoveryMonitor:
    """Get or create the singleton recovery monitor."""
    global _monitor
    if _monitor is None:
        _monitor = RecoveryMonitor()
    return _monitor
