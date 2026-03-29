"""Gemini CLI adapter (Google).

Wraps the `gemini` CLI for deep search, long context analysis, and
research tasks. Gemini has free deep search and a very large context
window, making it ideal for research-heavy tasks.

CLI reference: gemini "task" or gws (Google Workspace CLI)
"""

from __future__ import annotations

import asyncio
import shutil
from collections.abc import AsyncIterator
from typing import Any

from app.core.logging import get_logger
from app.services.runtimes.base_adapter import (
    BaseRuntimeAdapter,
    RuntimeCapability,
    RuntimeStatus,
)

logger = get_logger(__name__)


class GeminiCLIAdapter(BaseRuntimeAdapter):
    """Adapter for Google Gemini CLI."""

    def __init__(self) -> None:
        super().__init__(
            runtime_id="gemini_cli",
            display_name="Gemini CLI (Google)",
        )
        self._processes: dict[str, asyncio.subprocess.Process] = {}

    async def check_installed(self) -> bool:
        """Check if gemini CLI is installed (binary exists on PATH)."""
        # gemini --version hangs when not authenticated, so just check binary presence
        return shutil.which("gemini") is not None

    async def check_health(self) -> RuntimeStatus:
        """Check if gemini CLI is available."""
        if not await self.check_installed():
            return RuntimeStatus.NOT_INSTALLED
        return RuntimeStatus.ONLINE

    async def get_capabilities(self) -> RuntimeCapability:
        """Gemini excels at research, long context, and deep search."""
        return RuntimeCapability(
            complex_reasoning=8.0,
            code_generation=7.5,
            code_editing=6.5,
            file_operations=7.0,
            web_research=9.5,
            data_analysis=8.5,
            browser_automation=5.0,
            simple_chat=7.5,
            bulk_operations=6.0,
            cost_per_1k_tokens=0.00025,  # Gemini Flash pricing
        )

    async def execute(
        self, task: str, context: dict[str, Any],
    ) -> AsyncIterator[str]:
        """Spawn gemini CLI and stream output."""
        cwd = context.get("working_directory", ".")
        session_id = context.get("session_id", "unknown")

        cmd = ["gemini", "-p", task]

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
        """Kill a running gemini process."""
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
            "description": (
                "Gemini CLI uses your Google account "
                "(free with Gemini Pro upgrade available)"
            ),
            "setup_command": "gemini auth login",
            "login_url": "https://gemini.google.com",
            "subscription_plans": ["Google account (free)", "Gemini Advanced ($20/mo)"],
            "cost_to_user": "$0 (free tier or included in subscription)",
            "api_key_fallback": {
                "env_var": "GOOGLE_API_KEY",
                "description": "Optional: API key for pay-per-token usage",
            },
        }

    async def check_subscription(self):
        """Check if user has active Google auth via `gcloud auth list`."""
        from app.services.runtimes.subscription_auth import (
            AuthMethod,
            SubscriptionAuth,
            SubscriptionStatus,
        )

        try:
            # Try gemini auth first, fall back to gcloud auth
            proc = await asyncio.create_subprocess_exec(
                "gcloud", "auth", "list", "--format=value(account,status)",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10.0)
            output = stdout.decode("utf-8", errors="replace")

            if proc.returncode == 0 and output.strip():
                # Parse active account
                user_display = None
                for line in output.splitlines():
                    line = line.strip()
                    if line and ("ACTIVE" in line.upper() or "@" in line):
                        parts = line.split()
                        for part in parts:
                            if "@" in part:
                                user_display = part.strip()
                                break
                        if user_display:
                            break

                if user_display:
                    return SubscriptionAuth(
                        method=AuthMethod.SUBSCRIPTION,
                        status=SubscriptionStatus.AUTHENTICATED,
                        user_display=user_display,
                        plan_name="Google/Gemini",
                        setup_command="gemini auth login",
                        login_url="https://gemini.google.com",
                    )

            return SubscriptionAuth(
                method=AuthMethod.SUBSCRIPTION,
                status=SubscriptionStatus.NOT_AUTHENTICATED,
                setup_command="gemini auth login",
                login_url="https://gemini.google.com",
                plan_name="Google/Gemini",
            )
        except (TimeoutError, FileNotFoundError, OSError):
            return SubscriptionAuth(
                method=AuthMethod.SUBSCRIPTION,
                status=SubscriptionStatus.UNKNOWN,
                setup_command="gemini auth login",
                detail="Could not check Google auth status",
            )
