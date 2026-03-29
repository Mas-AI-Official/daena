"""Gemini CLI adapter (Google).

Wraps the `gemini` CLI for deep search, long context analysis, and
research tasks. Gemini has free deep search and a very large context
window, making it ideal for research-heavy tasks.

CLI reference: gemini "task" or gws (Google Workspace CLI)
"""

from __future__ import annotations

import asyncio
import json as _json
import shutil
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.runtimes.base_adapter import (
    BaseRuntimeAdapter,
    RuntimeCapability,
    RuntimeStatus,
)

logger = get_logger(__name__)


def _run_cmd(
    cmd: list[str],
    *,
    timeout: float = 10.0,
) -> subprocess.CompletedProcess[str]:
    """Run a command synchronously (called from thread pool for Windows compat)."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


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
        """Check Gemini CLI authentication status.

        Strategy (in order):
        1. Try `gemini auth status` or `gemini auth print-access-token`
        2. Check Gemini CLI config files at well-known paths
        3. Fall back to UNKNOWN if CLI is not installed

        Uses asyncio.to_thread for Windows SelectorEventLoop compatibility.
        """
        from app.services.runtimes.subscription_auth import (
            AuthMethod,
            SubscriptionAuth,
            SubscriptionStatus,
        )

        if not await self.check_installed():
            return SubscriptionAuth(
                method=AuthMethod.SUBSCRIPTION,
                status=SubscriptionStatus.NOT_AUTHENTICATED,
                setup_command="npm install -g @anthropic-ai/gemini-cli && gemini auth login",
                login_url="https://github.com/google-gemini/gemini-cli",
                plan_name="Google/Gemini",
                detail="Gemini CLI not installed",
            )

        # Strategy 1: Try `gemini auth print-access-token` (prints token if auth'd)
        try:
            result = await asyncio.to_thread(
                _run_cmd, ["gemini", "auth", "print-access-token"], timeout=10.0,
            )
            if result.returncode == 0 and result.stdout.strip():
                # Has a valid token -- try to get the account email
                user_display = "Google account"
                try:
                    status_result = await asyncio.to_thread(
                        _run_cmd, ["gemini", "auth", "status"], timeout=10.0,
                    )
                    if status_result.returncode == 0:
                        output = status_result.stdout
                        # Try JSON parse first
                        try:
                            data = _json.loads(output.strip())
                            user_display = (
                                data.get("email")
                                or data.get("account")
                                or data.get("user")
                                or user_display
                            )
                        except (_json.JSONDecodeError, ValueError):
                            # Parse plain text for email
                            for line in output.splitlines():
                                if "@" in line:
                                    for word in line.split():
                                        if "@" in word:
                                            user_display = word.strip()
                                            break
                                    break
                except Exception:
                    pass

                return SubscriptionAuth(
                    method=AuthMethod.SUBSCRIPTION,
                    status=SubscriptionStatus.AUTHENTICATED,
                    user_display=user_display,
                    plan_name="Google/Gemini",
                    setup_command="gemini auth login",
                    login_url="https://gemini.google.com",
                )
        except (TimeoutError, FileNotFoundError, OSError):
            pass

        # Strategy 2: Check config files at well-known paths
        try:
            config_paths = [
                Path.home() / ".gemini" / "settings.json",
                Path.home() / ".config" / "gemini-cli" / "settings.json",
                Path.home() / ".gemini" / "auth.json",
                Path.home() / ".config" / "gemini" / "auth.json",
            ]
            for cfg_path in config_paths:
                if cfg_path.exists():
                    try:
                        data = _json.loads(cfg_path.read_text(encoding="utf-8"))
                        # Look for any auth token or credential indicator
                        has_auth = bool(
                            data.get("access_token")
                            or data.get("refresh_token")
                            or data.get("oauth")
                            or data.get("credentials")
                            or data.get("auth")
                        )
                        if has_auth:
                            user_email = (
                                data.get("email")
                                or data.get("user_email")
                                or data.get("account")
                                or "Google account"
                            )
                            return SubscriptionAuth(
                                method=AuthMethod.SUBSCRIPTION,
                                status=SubscriptionStatus.AUTHENTICATED,
                                user_display=user_email,
                                plan_name="Google/Gemini",
                                setup_command="gemini auth login",
                                login_url="https://gemini.google.com",
                            )
                    except (_json.JSONDecodeError, OSError):
                        continue
        except Exception:
            pass

        return SubscriptionAuth(
            method=AuthMethod.SUBSCRIPTION,
            status=SubscriptionStatus.NOT_AUTHENTICATED,
            setup_command="gemini auth login",
            login_url="https://gemini.google.com",
            plan_name="Google/Gemini",
        )
