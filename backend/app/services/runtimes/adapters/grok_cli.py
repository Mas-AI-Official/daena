"""Grok CLI adapter (xAI).

Wraps the `grok` CLI for quick search and real-time information tasks.
Grok has X/Twitter context and fast inference, useful for current events
and social media analysis.

CLI reference: grok "task"
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from app.core.logging import get_logger
from app.services.runtimes.base_adapter import (
    BaseRuntimeAdapter,
    RuntimeCapability,
    RuntimeStatus,
)

logger = get_logger(__name__)


class GrokCLIAdapter(BaseRuntimeAdapter):
    """Adapter for xAI Grok CLI."""

    def __init__(self) -> None:
        super().__init__(
            runtime_id="grok_cli",
            display_name="Grok (xAI)",
        )
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    async def check_installed(self) -> bool:
        """Check if grok CLI is installed."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "grok", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.wait(), timeout=10.0)
            return proc.returncode == 0
        except (TimeoutError, FileNotFoundError, OSError):
            return False

    async def check_health(self) -> RuntimeStatus:
        """Check if grok CLI is available."""
        if not await self.check_installed():
            return RuntimeStatus.NOT_INSTALLED
        return RuntimeStatus.ONLINE

    async def get_capabilities(self) -> RuntimeCapability:
        """Grok excels at quick search and real-time information."""
        return RuntimeCapability(
            complex_reasoning=7.0,
            code_generation=7.0,
            code_editing=6.0,
            file_operations=5.0,
            web_research=8.5,
            data_analysis=7.0,
            browser_automation=4.0,
            simple_chat=8.0,
            bulk_operations=4.0,
            cost_per_1k_tokens=0.005,
        )

    async def execute(
        self, task: str, context: dict[str, Any],
    ) -> AsyncIterator[str]:
        """Spawn grok CLI and stream output."""
        cwd = context.get("working_directory", ".")
        session_id = context.get("session_id", "unknown")

        cmd = ["grok", task]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
        )
        self._processes[session_id] = proc

        try:
            assert proc.stdout is not None
            async for line in proc.stdout:
                decoded = line.decode("utf-8", errors="replace").strip()
                if decoded:
                    yield decoded
        finally:
            self._processes.pop(session_id, None)
            if proc.returncode is None:
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=5.0)
                except TimeoutError:
                    proc.kill()

    async def cancel(self, session_id: str) -> bool:
        """Kill a running grok process."""
        proc = self._processes.get(session_id)
        if proc is None or proc.returncode is not None:
            return False
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=3.0)
        except TimeoutError:
            proc.kill()
        self._processes.pop(session_id, None)
        return True

    def get_auth_requirements(self) -> dict[str, Any]:
        return {
            "type": "subscription",
            "description": "Grok uses your X Premium+ subscription or xAI API key",
            "setup_command": "grok auth",
            "login_url": "https://x.com/i/premium_sign_up",
            "subscription_plans": ["X Premium+ ($16/mo)", "xAI API key"],
            "cost_to_user": "$0 (included in X Premium+)",
            "api_key_fallback": {
                "env_var": "XAI_API_KEY",
                "description": "Optional: xAI API key for pay-per-token usage",
            },
        }

    async def check_subscription(self):
        """Check if user has active Grok/xAI auth."""
        from app.services.runtimes.subscription_auth import (
            AuthMethod,
            SubscriptionAuth,
            SubscriptionStatus,
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                "grok", "auth", "status",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
            output = stdout.decode("utf-8", errors="replace").lower()

            if proc.returncode == 0 and ("logged in" in output or "authenticated" in output):
                return SubscriptionAuth(
                    method=AuthMethod.SUBSCRIPTION,
                    status=SubscriptionStatus.AUTHENTICATED,
                    plan_name="X Premium+",
                    setup_command="grok auth",
                    login_url="https://x.com/i/premium_sign_up",
                )

            return SubscriptionAuth(
                method=AuthMethod.SUBSCRIPTION,
                status=SubscriptionStatus.NOT_AUTHENTICATED,
                setup_command="grok auth",
                plan_name="X Premium+",
            )
        except (TimeoutError, FileNotFoundError, OSError):
            return SubscriptionAuth(
                method=AuthMethod.SUBSCRIPTION,
                status=SubscriptionStatus.UNKNOWN,
                setup_command="grok auth",
                detail="Could not check Grok CLI status",
            )
