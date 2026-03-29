"""Claude Code CLI adapter.

Wraps the `claude` CLI for autonomous task execution. Claude Code is
the primary "Main Mind" runtime: best at complex reasoning, code
generation, and multi-step tasks. Requires Anthropic Pro or Max
subscription.

CLI reference: claude -p "task" --output-format json

Note: All subprocess calls use asyncio.to_thread(subprocess.run)
instead of asyncio.create_subprocess_exec because uvicorn on Windows
uses SelectorEventLoop which does not support subprocess pipes.
"""

from __future__ import annotations

import asyncio
import subprocess
from collections.abc import AsyncIterator
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
    cwd: str | None = None,
    timeout: float = 60.0,
) -> subprocess.CompletedProcess[str]:
    """Run a command synchronously (called from thread pool)."""
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
    )


class ClaudeCodeAdapter(BaseRuntimeAdapter):
    """Adapter for Claude Code CLI (Anthropic)."""

    def __init__(self) -> None:
        super().__init__(
            runtime_id="claude_code",
            display_name="Claude Code",
        )
        # Resolve claude binary path once at init time
        import shutil

        self._claude_bin = shutil.which("claude") or "claude"
        logger.info("claude_code.init", binary=self._claude_bin)

        # Persistent session manager for stateful multi-turn execution
        from app.services.runtimes.adapters.claude_session import ClaudeSessionManager

        self._session_manager = ClaudeSessionManager(claude_bin=self._claude_bin)

    async def check_installed(self) -> bool:
        """Check if claude CLI is installed via PATH resolution."""
        import os

        if self._claude_bin != "claude" and os.path.isfile(self._claude_bin):
            logger.info("claude_code.installed", path=self._claude_bin)
            return True

        # Fallback: try running it
        try:
            result = await asyncio.to_thread(
                _run_cmd, [self._claude_bin, "--version"], timeout=10.0,
            )
            found = result.returncode == 0
            logger.info("claude_code.version_check", found=found, output=result.stdout[:100])
            return found
        except Exception as exc:
            logger.warning("claude_code.not_found", error=str(exc))
            return False

    async def check_health(self) -> RuntimeStatus:
        """Check if claude CLI is installed and responsive."""
        if not await self.check_installed():
            return RuntimeStatus.NOT_INSTALLED
        return RuntimeStatus.ONLINE

    async def get_capabilities(self) -> RuntimeCapability:
        """Claude Code excels at reasoning, code gen, and multi-step tasks."""
        return RuntimeCapability(
            complex_reasoning=9.5,
            code_generation=9.5,
            code_editing=9.0,
            file_operations=9.0,
            web_research=7.0,
            data_analysis=8.0,
            browser_automation=6.0,
            simple_chat=8.0,
            bulk_operations=7.0,
            cost_per_1k_tokens=0.015,
        )

    async def execute(
        self, task: str, context: dict[str, Any],
    ) -> AsyncIterator[str]:
        """Execute task via persistent Claude Code session.

        Uses ClaudeSessionManager to maintain stateful sessions.
        First command creates a new CLI session; follow-up commands
        in the same Daena chat session resume it with full context.
        """
        cwd = context.get("working_directory", ".")
        session_id = context.get("session_id", "unknown")

        logger.info(
            "claude_code.execute",
            session_id=session_id,
            task=task[:200],
            cwd=cwd,
        )

        result = await self._session_manager.send(
            daena_session_id=session_id,
            task=task,
            cwd=cwd,
            timeout=300.0,
        )

        if result.is_error:
            yield f"[Claude Code error: {result.result_text}]"
        else:
            if result.result_text:
                yield result.result_text
            if result.cost_usd > 0 or result.duration_ms > 0:
                session = self._session_manager.get(session_id)
                turn_info = f"Turn {session.command_count}" if session else ""
                yield f"\n---\n_Runtime: Claude Code | {turn_info} | Cost: ${result.cost_usd:.4f} | Duration: {result.duration_ms}ms_"

    async def cancel(self, session_id: str) -> bool:
        """Cancel is not supported in thread-pool subprocess mode."""
        # With to_thread, we can't easily cancel. Return False.
        return False

    def get_auth_requirements(self) -> dict[str, Any]:
        return {
            "type": "subscription",
            "description": "Claude Code uses your Anthropic subscription (Pro or Max)",
            "setup_command": "claude login",
            "login_url": "https://claude.ai/login",
            "subscription_plans": ["Claude Pro ($20/mo)", "Claude Max ($100/mo)"],
            "cost_to_user": "$0 (included in subscription)",
            "api_key_fallback": {
                "env_var": "ANTHROPIC_API_KEY",
                "description": "Optional: API key for pay-per-token usage",
            },
        }

    async def check_subscription(self):
        """Check if user has active Claude Code session via `claude auth status`.

        Uses subprocess.run in thread pool (not asyncio subprocess)
        because uvicorn on Windows uses SelectorEventLoop.
        """
        from app.services.runtimes.subscription_auth import (
            AuthMethod,
            SubscriptionAuth,
            SubscriptionStatus,
        )

        try:
            logger.info("claude_code.checking_subscription", binary=self._claude_bin)
            result = await asyncio.to_thread(
                _run_cmd, [self._claude_bin, "auth", "status"], timeout=10.0,
            )
            logger.info(
                "claude_code.auth_result",
                returncode=result.returncode,
                stdout_len=len(result.stdout),
            )

            if result.returncode == 0:
                import json

                try:
                    data = json.loads(result.stdout.strip())
                    logged_in = data.get("loggedIn", False)
                    api_provider = data.get("apiProvider", "")

                    if logged_in:
                        plan = "Claude Max" if api_provider == "firstParty" else "Claude Pro"
                        return SubscriptionAuth(
                            method=AuthMethod.SUBSCRIPTION,
                            status=SubscriptionStatus.AUTHENTICATED,
                            user_display=f"{plan} subscriber",
                            plan_name=plan,
                            setup_command="claude login",
                            login_url="https://claude.ai/login",
                        )
                    else:
                        # Token exists but expired or invalid
                        return SubscriptionAuth(
                            method=AuthMethod.SUBSCRIPTION,
                            status=SubscriptionStatus.EXPIRED,
                            setup_command="claude login",
                            login_url="https://claude.ai/login",
                            plan_name="Claude Pro/Max",
                            detail="Session expired. Run 'claude login' to refresh.",
                        )
                except (json.JSONDecodeError, KeyError):
                    pass

            return SubscriptionAuth(
                method=AuthMethod.SUBSCRIPTION,
                status=SubscriptionStatus.NOT_AUTHENTICATED,
                setup_command="claude login",
                login_url="https://claude.ai/login",
                plan_name="Claude Pro/Max",
            )
        except Exception as exc:
            logger.warning("claude_code.subscription_error", error=str(exc))
            return SubscriptionAuth(
                method=AuthMethod.SUBSCRIPTION,
                status=SubscriptionStatus.UNKNOWN,
                setup_command="claude login",
                detail=f"Could not check Claude CLI status: {exc}",
            )
