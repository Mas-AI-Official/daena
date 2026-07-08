"""Runtime Registry: discovers, monitors, and routes to available runtimes.

Central orchestration point for the Runtime Adapter Layer. On startup,
scans for installed runtimes, monitors their health periodically, and
selects the optimal runtime for each task via capability scoring.

The registry is initialized once during app startup (events.py) and
shared across the application as a singleton.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.core.logging import get_logger
from app.services.runtimes.base_adapter import (
    BaseRuntimeAdapter,
    RuntimeCapability,
    RuntimeStatus,
)

logger = get_logger(__name__)

# How often to re-check health (seconds)
HEALTH_CHECK_INTERVAL = 60.0

# Stale threshold: if last check was longer ago than this, force re-check
HEALTH_STALE_THRESHOLD = 120.0


class NoRuntimeAvailableError(Exception):
    """Raised when no runtime is available for a task."""


class RuntimeRegistry:
    """Discovers, monitors, and routes to available runtimes.

    Usage::

        registry = RuntimeRegistry()
        registry.register(ClaudeCodeAdapter())
        registry.register(OllamaRuntimeAdapter())

        await registry.discover_all()

        best = await registry.select_runtime("code_generation")
        adapter = registry.get_adapter(best)
    """

    def __init__(self) -> None:
        self._adapters: dict[str, BaseRuntimeAdapter] = {}
        self._health_cache: dict[str, RuntimeStatus] = {}
        self._last_health_check: dict[str, float] = {}
        self._capabilities_cache: dict[str, RuntimeCapability] = {}
        self._installed_cache: dict[str, bool] = {}
        # Per-runtime timestamp of the last ``check_installed`` call,
        # used to re-run discovery after the TTL expires. Without this,
        # a user who installs Claude CLI / Codex / Ollama AFTER the
        # backend boots would have to restart to be seen. With it,
        # new runtimes appear on the next eligible request (~30s
        # worst case, ``RUNTIME_DISCOVERY_TTL``).
        self._last_discovery_check: dict[str, float] = {}
        self._subscription_cache: dict[str, Any] = {}  # runtime_id -> SubscriptionAuth
        # 30s TTL: short enough that toggling runtimes feels instant,
        # long enough that the health endpoint polled every few
        # seconds doesn't re-probe the filesystem / PATH every time.
        self._RUNTIME_DISCOVERY_TTL: float = 30.0

    def register(self, adapter: BaseRuntimeAdapter) -> None:
        """Register a runtime adapter."""
        self._adapters[adapter.runtime_id] = adapter
        self._health_cache[adapter.runtime_id] = RuntimeStatus.OFFLINE
        logger.info(
            "runtime.registered",
            runtime_id=adapter.runtime_id,
            display_name=adapter.display_name,
        )

    def unregister(self, runtime_id: str) -> None:
        """Remove a runtime adapter."""
        self._adapters.pop(runtime_id, None)
        self._health_cache.pop(runtime_id, None)
        self._last_health_check.pop(runtime_id, None)
        self._capabilities_cache.pop(runtime_id, None)
        self._installed_cache.pop(runtime_id, None)
        self._subscription_cache.pop(runtime_id, None)

    def get_adapter(self, runtime_id: str) -> BaseRuntimeAdapter | None:
        """Get a registered adapter by ID."""
        return self._adapters.get(runtime_id)

    @property
    def registered_ids(self) -> list[str]:
        """All registered runtime IDs."""
        return list(self._adapters.keys())

    @property
    def online_ids(self) -> list[str]:
        """Runtime IDs currently online."""
        return [
            rid for rid, status in self._health_cache.items()
            if status == RuntimeStatus.ONLINE
        ]

    # -- Discovery --

    async def discover_all(self) -> dict[str, bool]:
        """Check which registered runtimes are installed. Called on startup."""
        results: dict[str, bool] = {}
        tasks = []
        for rid, adapter in self._adapters.items():
            tasks.append(self._check_installed(rid, adapter))

        done = await asyncio.gather(*tasks, return_exceptions=True)
        for result in done:
            if isinstance(result, tuple):
                rid, installed = result
                results[rid] = installed

        # Phase 2 efficiency (2026-04-24): only emit at INFO when the
        # installed set CHANGES. The 60s discovery loop was logging an
        # identical INFO line 1440x/day. Quiet observation -> DEBUG;
        # state-change -> INFO so audit + alerts still surface real
        # signals (a runtime appearing or disappearing).
        installed_set = frozenset(r for r, ok in results.items() if ok)
        previous_set = getattr(self, "_last_install_set", None)
        if previous_set != installed_set:
            logger.info(
                "runtime.discovery_changed",
                installed=sorted(installed_set),
                not_installed=sorted(r for r, ok in results.items() if not ok),
                added=sorted(installed_set - (previous_set or frozenset())),
                removed=sorted((previous_set or frozenset()) - installed_set),
            )
            self._last_install_set = installed_set
        else:
            logger.debug(
                "runtime.discovery_complete",
                installed=sorted(installed_set),
                not_installed=sorted(r for r, ok in results.items() if not ok),
            )
        return results

    async def _check_installed(
        self, runtime_id: str, adapter: BaseRuntimeAdapter,
    ) -> tuple[str, bool]:
        """Check installation for one adapter."""
        try:
            installed = await adapter.check_installed()
        except Exception:
            installed = False
        previous = self._installed_cache.get(runtime_id)
        self._installed_cache[runtime_id] = installed
        self._last_discovery_check[runtime_id] = time.monotonic()
        # Only log when the installed-state actually flips; periodic
        # re-scans that confirm the same state should stay quiet.
        if previous is not None and previous != installed:
            logger.info(
                "runtime.install_state_changed",
                runtime_id=runtime_id,
                installed=installed,
                previous=previous,
            )
        return runtime_id, installed

    async def ensure_install_fresh(self, runtime_id: str) -> bool:
        """Re-run ``check_installed`` if the last check is older than TTL.

        Call this from any code path that branches on whether a
        runtime is installed (fallback chain, capability probes,
        `/runtimes` endpoint). Returns the fresh installed state.
        """
        last = self._last_discovery_check.get(runtime_id, 0.0)
        if (time.monotonic() - last) > self._RUNTIME_DISCOVERY_TTL:
            adapter = self._adapters.get(runtime_id)
            if adapter is not None:
                _, installed = await self._check_installed(runtime_id, adapter)
                return installed
        return self._installed_cache.get(runtime_id, False)

    async def rediscover_all(self) -> dict[str, bool]:
        """Force a fresh discovery of every registered runtime.

        Used by the manual "Refresh" button on the Connections page
        and by periodic schedulers. Bypasses the TTL entirely.
        """
        # Reset timestamps so ``_check_installed`` is forced.
        self._last_discovery_check.clear()
        return await self.discover_all()

    # -- Health Monitoring --

    async def check_health_all(self) -> dict[str, RuntimeStatus]:
        """Check health of all installed runtimes."""
        results: dict[str, RuntimeStatus] = {}
        tasks = []
        for rid, adapter in self._adapters.items():
            if self._installed_cache.get(rid, False):
                tasks.append(self._check_health(rid, adapter))

        done = await asyncio.gather(*tasks, return_exceptions=True)
        for result in done:
            if isinstance(result, tuple):
                rid, status = result
                results[rid] = status

        return results

    async def _check_health(
        self, runtime_id: str, adapter: BaseRuntimeAdapter,
    ) -> tuple[str, RuntimeStatus]:
        """Check health for one adapter."""
        try:
            status = await adapter.check_health()
        except Exception:
            status = RuntimeStatus.ERROR
        self._health_cache[runtime_id] = status
        self._last_health_check[runtime_id] = time.monotonic()
        return runtime_id, status

    async def ensure_health_fresh(self, runtime_id: str) -> RuntimeStatus:
        """Return cached health if fresh, otherwise re-check."""
        last = self._last_health_check.get(runtime_id, 0)
        if (time.monotonic() - last) > HEALTH_STALE_THRESHOLD:
            adapter = self._adapters.get(runtime_id)
            if adapter and self._installed_cache.get(runtime_id, False):
                _, status = await self._check_health(runtime_id, adapter)
                return status
        return self._health_cache.get(runtime_id, RuntimeStatus.OFFLINE)

    def get_health(self, runtime_id: str) -> RuntimeStatus:
        """Get cached health status (no I/O)."""
        return self._health_cache.get(runtime_id, RuntimeStatus.OFFLINE)

    # -- Capability Caching --

    async def get_capabilities(self, runtime_id: str) -> RuntimeCapability:
        """Get capabilities for a runtime (cached after first call)."""
        if runtime_id in self._capabilities_cache:
            return self._capabilities_cache[runtime_id]
        adapter = self._adapters.get(runtime_id)
        if adapter is None:
            return RuntimeCapability()
        caps = await adapter.get_capabilities()
        self._capabilities_cache[runtime_id] = caps
        return caps

    # -- Subscription Auth Cache --

    async def check_subscription(self, runtime_id: str):
        """Check subscription status for a runtime (cached)."""
        if runtime_id in self._subscription_cache:
            return self._subscription_cache[runtime_id]
        adapter = self._adapters.get(runtime_id)
        if adapter is None:
            return None
        try:
            auth = await adapter.check_subscription()
            self._subscription_cache[runtime_id] = auth
            logger.info(
                "runtime.subscription_checked",
                runtime_id=runtime_id,
                status=getattr(auth, "status", None),
            )
            return auth
        except Exception as exc:
            logger.warning(
                "runtime.subscription_check_failed",
                runtime_id=runtime_id,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            return None

    async def check_subscriptions_all(self) -> dict[str, Any]:
        """Check subscription status for all installed runtimes."""
        import asyncio as _asyncio

        results = {}
        tasks = []
        for rid in self._adapters:
            if self._installed_cache.get(rid, False):
                tasks.append((rid, self._adapters[rid].check_subscription()))

        if not tasks:
            logger.info("runtime.no_installed_runtimes_for_subscription_check")
            return results

        rids = [t[0] for t in tasks]
        coros = [t[1] for t in tasks]
        logger.info("runtime.checking_subscriptions", rids=rids)
        done = await _asyncio.gather(*coros, return_exceptions=True)

        for rid, result in zip(rids, done, strict=False):
            if isinstance(result, Exception):
                logger.warning(
                    "runtime.subscription_gather_error",
                    runtime_id=rid,
                    error=str(result),
                    error_type=type(result).__name__,
                )
            else:
                self._subscription_cache[rid] = result
                results[rid] = result
                logger.info(
                    "runtime.subscription_gathered",
                    runtime_id=rid,
                    status=getattr(result, "status", None),
                )

        return results

    # -- Runtime Selection (Mind Selection Engine) --

    async def select_runtime(
        self,
        task_type: str,
        *,
        user_preference: str | None = None,
        auto_mode: bool = True,
        cost_ceiling: float | None = None,
        exclude: list[str] | None = None,
    ) -> str:
        """Select the best runtime for a task type.

        Subscription-first priority:
            1. User preference (if specified and online)
            2. CLI with active subscription (highest auth priority + capability)
            3. Connected MCP servers
            4. Local models (Ollama)
            5. API key fallback (lowest auth priority)

        Auth priority is layered on top of capability scores so that
        subscription-authenticated runtimes are strongly preferred over
        API-key-only runtimes, even if the latter has higher raw scores.

        Args:
            task_type: Capability field name (e.g. "code_generation").
            user_preference: Runtime ID the user prefers.
            auto_mode: If True, auto-select best runtime.
            cost_ceiling: Max $/1K tokens. None = no limit.
            exclude: Runtime IDs to exclude from selection.

        Returns:
            runtime_id of the selected runtime.

        Raises:
            NoRuntimeAvailableError: If no runtime can handle the task.
        """
        exclude_set = set(exclude or [])

        # 1. User preference (highest priority -- user is always in control)
        if user_preference and user_preference not in exclude_set:
            health = await self.ensure_health_fresh(user_preference)
            if health == RuntimeStatus.ONLINE:
                return user_preference

        if not auto_mode and user_preference:
            raise NoRuntimeAvailableError(
                f"Preferred runtime '{user_preference}' is not available "
                f"(status: {self.get_health(user_preference).value})"
            )

        # 2. Score all online runtimes with auth priority weighting
        # Formula: (auth_priority * 10) + capability_score
        # Subscription(100)*10 + 7.0 = 1007 >> API_key(20)*10 + 9.5 = 209.5
        scores: dict[str, float] = {}
        for rid in self._adapters:
            if rid in exclude_set:
                continue
            health = self._health_cache.get(rid, RuntimeStatus.OFFLINE)
            if health != RuntimeStatus.ONLINE:
                continue

            caps = await self.get_capabilities(rid)

            # Cost filter
            if cost_ceiling is not None and caps.cost_per_1k_tokens > cost_ceiling:
                continue

            capability_score = caps.score_for(task_type)

            # Auth priority weighting
            sub_auth = self._subscription_cache.get(rid)
            # Auth priority: cached score or neutral 50 if not probed yet
            auth_priority = sub_auth.priority_score if sub_auth is not None else 50

            # Weighted score: auth dominates, capability breaks ties
            scores[rid] = (auth_priority * 10) + capability_score

        if scores:
            return max(scores, key=scores.get)  # type: ignore[arg-type]

        # 3. Fallback to local runtimes (always free). vllm serves the
        # local llama.cpp llama-server (OpenAI-compat); ollama is kept
        # for backward compat only.
        for local_rid in ("vllm", "ollama"):
            if local_rid in exclude_set:
                continue
            local_health = self._health_cache.get(local_rid, RuntimeStatus.OFFLINE)
            if local_health == RuntimeStatus.ONLINE:
                return local_rid

        raise NoRuntimeAvailableError(
            f"No runtimes available for task type '{task_type}'. "
            f"Online runtimes: {self.online_ids}"
        )

    # -- Execute with Fallback Chain --

    async def execute_with_fallback(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        timeout: float = 300.0,
    ) -> dict[str, Any]:
        """Try each runtime in priority order until one succeeds.

        Fallback chain: claude_code -> codex -> gemini_cli -> grok_cli
        -> vllm -> ollama
        """
        context = context or {}
        priority_order = ["claude_code", "codex", "gemini_cli", "grok_cli", "vllm", "ollama"]
        last_error = None

        for rid in priority_order:
            adapter = self._adapters.get(rid)
            if not adapter:
                continue
            if not self._installed_cache.get(rid, False):
                continue

            try:
                output_lines: list[str] = []
                async for line in adapter.execute(task=task, context=context):
                    output_lines.append(line)

                output = "\n".join(output_lines)
                if output and "[error" not in output.lower()[:50]:
                    return {
                        "success": True,
                        "output": output,
                        "runtime": rid,
                    }
                last_error = output[:200] if output else "No output"

            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "runtime.fallback_attempt_failed",
                    runtime=rid,
                    error=last_error[:100],
                )
                continue

        return {
            "success": False,
            "error": f"All runtimes failed. Last error: {last_error}",
            "runtime": None,
        }

    # -- Summary for SwarmPlanner --

    async def get_capabilities_summary(self) -> str:
        """Human-readable summary of all online runtimes and their strengths."""
        lines = []
        for rid in self.online_ids:
            caps = await self.get_capabilities(rid)
            adapter = self._adapters[rid]
            best_tasks = sorted(
                caps.to_dict().items(),
                key=lambda x: x[1],
                reverse=True,
            )[:3]
            strengths = ", ".join(
                f"{t}={s:.1f}" for t, s in best_tasks if s > 0
            )
            cost_str = (
                f"${caps.cost_per_1k_tokens:.4f}/1K"
                if caps.cost_per_1k_tokens > 0
                else "free"
            )
            lines.append(
                f"  {adapter.display_name} ({rid}): {strengths} [{cost_str}]"
            )
        if not lines:
            return "No runtimes currently online."
        return "Available runtimes:\n" + "\n".join(lines)

    # -- Serialization --

    def to_dict(self) -> dict[str, Any]:
        """Serialize registry state for API/frontend."""
        runtimes = []
        for rid, adapter in self._adapters.items():
            caps = self._capabilities_cache.get(rid, RuntimeCapability())
            sub_auth = self._subscription_cache.get(rid)
            runtimes.append({
                "runtime_id": rid,
                "display_name": adapter.display_name,
                "installed": self._installed_cache.get(rid, False),
                "status": self._health_cache.get(rid, RuntimeStatus.OFFLINE).value,
                "capabilities": caps.to_dict(),
                "auth_requirements": adapter.get_auth_requirements(),
                "subscription": sub_auth.to_dict() if sub_auth else None,
            })
        return {
            "runtimes": runtimes,
            "online_count": len(self.online_ids),
            "total_count": len(self._adapters),
        }
