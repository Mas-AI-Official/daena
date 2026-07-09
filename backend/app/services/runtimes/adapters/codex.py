"""Codex CLI adapter (OpenAI).

Wraps the `codex` CLI for autonomous code generation and bulk file
operations. Codex excels at large-scale refactoring and consistent
pattern application across many files. Best for async/batch work.

CLI reference: codex exec "task" (non-interactive mode)

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
    RuntimeExecutionError,
    RuntimeProbeResult,
    RuntimeStatus,
)

logger = get_logger(__name__)

_PROBE_VERSION_TIMEOUT = 8.0
_PROBE_ROUNDTRIP_TIMEOUT = 25.0
_PROBE_PING_PROMPT = "ping"


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


class CodexAdapter(BaseRuntimeAdapter):
    """Adapter for OpenAI Codex CLI."""

    def __init__(self) -> None:
        super().__init__(
            runtime_id="codex",
            display_name="Codex (OpenAI)",
        )
        import os
        import shutil

        # Prefer native Linux/macOS codex over the Windows-mounted
        # npm binary. The Windows .exe ships the Windows-only optional
        # dependency @openai/codex-win32-x64; when Linux spawns it the
        # ESM loader throws "Missing optional dependency
        # @openai/codex-linux-x64" (the exact error the operator hit).
        # /usr/bin/codex installed via npm -g on the WSL Linux side
        # uses the platform-correct variant.
        _native_unix_candidates = [
            "/usr/bin/codex",
            "/usr/local/bin/codex",
            os.path.expanduser("~/.local/bin/codex"),
        ]
        self._codex_bin = ""
        for candidate in _native_unix_candidates:
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                self._codex_bin = candidate
                break
        if not self._codex_bin:
            self._codex_bin = shutil.which("codex") or "codex"
        logger.info("codex.init", binary=self._codex_bin)

    async def check_installed(self) -> bool:
        """Check if codex CLI is installed via PATH resolution."""
        import os

        if self._codex_bin != "codex" and os.path.isfile(self._codex_bin):
            return True
        try:
            result = await asyncio.to_thread(
                _run_cmd, [self._codex_bin, "--version"], timeout=10.0,
            )
            return result.returncode == 0
        except Exception:
            return False

    async def check_health(self) -> RuntimeStatus:
        """Check if codex CLI is installed and responsive."""
        if not await self.check_installed():
            return RuntimeStatus.NOT_INSTALLED
        return RuntimeStatus.ONLINE

    async def get_capabilities(self) -> RuntimeCapability:
        """Codex excels at bulk code operations and consistent refactoring."""
        return RuntimeCapability(
            complex_reasoning=7.5,
            code_generation=9.0,
            code_editing=9.0,
            file_operations=8.5,
            web_research=5.0,
            data_analysis=7.0,
            browser_automation=3.0,
            simple_chat=6.0,
            bulk_operations=9.5,
            cost_per_1k_tokens=0.012,
        )

    async def execute(
        self, task: str, context: dict[str, Any],
    ) -> AsyncIterator[str]:
        """Spawn codex CLI and return result."""
        cwd = context.get("working_directory", ".")

        cmd = [self._codex_bin, "exec", task]

        logger.info("codex.execute", task=task[:200], cwd=cwd)

        try:
            result = await asyncio.to_thread(
                _run_cmd, cmd, cwd=cwd, timeout=300.0,
            )
            output = result.stdout.strip()
            if output:
                yield output
            if result.stderr.strip():
                # Stderr is for backend logs only -- never yield to the SSE
                # stream. The Codex CLI banner contains workdir/model/provider/
                # session-id strings that violate Asset Shield's egress promise
                # (Hard Law 5: data exfiltration). See QA finding F-0011.
                logger.warning(
                    "codex.stderr",
                    stderr=result.stderr.strip()[:500],
                    task=task[:100],
                )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeExecutionError(
                runtime_id=self.runtime_id,
                message="Codex timed out after 5 minutes",
            ) from exc
        except Exception as exc:
            raise RuntimeExecutionError(
                runtime_id=self.runtime_id,
                message=str(exc) or exc.__class__.__name__,
            ) from exc

    async def cancel(self, session_id: str) -> bool:
        """Cancel is not supported in thread-pool subprocess mode."""
        return False

    def get_auth_requirements(self) -> dict[str, Any]:
        return {
            "type": "subscription",
            "description": "Codex uses your OpenAI subscription (ChatGPT Pro/Plus)",
            "setup_command": "codex --login",
            "login_url": "https://chat.openai.com",
            "subscription_plans": ["ChatGPT Plus ($20/mo)", "ChatGPT Pro ($200/mo)"],
            "cost_to_user": "$0 (included in subscription)",
            "api_key_fallback": {
                "env_var": "OPENAI_API_KEY",
                "description": "Optional: API key for pay-per-token usage",
            },
        }

    async def check_subscription(self):
        """Check if user has active Codex session.

        Reads ~/.codex/auth.json directly instead of running
        `codex auth status` (which doesn't exist in codex-cli).
        """
        import json as _json
        from pathlib import Path

        from app.services.runtimes.subscription_auth import (
            AuthMethod,
            SubscriptionAuth,
            SubscriptionStatus,
        )

        try:
            auth_file = Path.home() / ".codex" / "auth.json"
            if not auth_file.exists():
                return SubscriptionAuth(
                    method=AuthMethod.SUBSCRIPTION,
                    status=SubscriptionStatus.NOT_AUTHENTICATED,
                    setup_command="codex login",
                    login_url="https://chat.openai.com",
                    plan_name="ChatGPT Plus/Pro",
                )

            data = _json.loads(auth_file.read_text(encoding="utf-8"))
            auth_mode = data.get("auth_mode", "")
            tokens = data.get("tokens", {})
            id_token = tokens.get("id_token", "")

            # Parse JWT payload (base64-decoded middle section)
            if id_token:
                import base64

                payload_b64 = id_token.split(".")[1]
                # Pad base64
                payload_b64 += "=" * (4 - len(payload_b64) % 4)
                payload = _json.loads(base64.urlsafe_b64decode(payload_b64))

                email = payload.get("email", "")
                auth_info = payload.get("https://api.openai.com/auth", {})
                plan_type = auth_info.get("chatgpt_plan_type", "plus")
                orgs = auth_info.get("organizations", [])
                org_name = orgs[0].get("title", "") if orgs else ""

                plan_name = f"ChatGPT {plan_type.capitalize()}"

                logger.info(
                    "codex.auth_parsed",
                    email=email,
                    plan=plan_name,
                    org=org_name,
                )

                return SubscriptionAuth(
                    method=AuthMethod.SUBSCRIPTION,
                    status=SubscriptionStatus.AUTHENTICATED,
                    user_display=email or f"{plan_name} subscriber",
                    plan_name=plan_name,
                    setup_command="codex login",
                    login_url="https://chat.openai.com",
                )

            # auth.json exists but no token
            if auth_mode:
                return SubscriptionAuth(
                    method=AuthMethod.SUBSCRIPTION,
                    status=SubscriptionStatus.AUTHENTICATED,
                    user_display=f"{auth_mode} user",
                    plan_name=f"ChatGPT ({auth_mode})",
                    setup_command="codex login",
                    login_url="https://chat.openai.com",
                )

            return SubscriptionAuth(
                method=AuthMethod.SUBSCRIPTION,
                status=SubscriptionStatus.NOT_AUTHENTICATED,
                setup_command="codex login",
                login_url="https://chat.openai.com",
                plan_name="ChatGPT Plus/Pro",
            )
        except Exception as exc:
            logger.warning("codex.subscription_error", error=str(exc))
            return SubscriptionAuth(
                method=AuthMethod.SUBSCRIPTION,
                status=SubscriptionStatus.UNKNOWN,
                setup_command="codex login",
                detail=f"Could not check Codex CLI status: {exc}",
            )

    async def probe(self) -> RuntimeProbeResult:
        """Real round-trip probe (Phase 4b PR 2).

        Truth ladder mirrors claude_code:
          1. detected = codex binary present
          2. configured = trivially True once detected
          3. reachable = ``codex --version`` exits 0
          4. authenticated = ~/.codex/auth.json has a parseable token
          5. callable = ``codex exec "ping"`` succeeds with non-empty
             stdout

        Stderr is logged server-side only (Asset Shield Hard Law 5).
        """
        import os
        import time as _time

        from app.services.runtimes.subscription_auth import SubscriptionStatus

        start = _time.perf_counter()
        result = RuntimeProbeResult()

        # Dim 1: detected
        try:
            detected = (
                self._codex_bin != "codex"
                and os.path.isfile(self._codex_bin)
            )
            if not detected:
                version_check = await asyncio.to_thread(
                    _run_cmd,
                    [self._codex_bin, "--version"],
                    timeout=_PROBE_VERSION_TIMEOUT,
                )
                detected = version_check.returncode == 0
            result.detected = detected
        except Exception as exc:  # noqa: BLE001
            result.failure_dim = "detected"
            result.failure_reason = f"detect probe error: {type(exc).__name__}"
            result.duration_ms = int((_time.perf_counter() - start) * 1000)
            return result

        if not result.detected:
            result.failure_dim = "detected"
            result.failure_reason = "codex binary not found"
            result.duration_ms = int((_time.perf_counter() - start) * 1000)
            return result

        result.configured = True

        # Dim 3: reachable
        try:
            version_check = await asyncio.to_thread(
                _run_cmd,
                [self._codex_bin, "--version"],
                timeout=_PROBE_VERSION_TIMEOUT,
            )
            result.reachable = version_check.returncode == 0
        except subprocess.TimeoutExpired:
            result.failure_dim = "reachable"
            result.failure_reason = (
                f"codex --version timed out after {_PROBE_VERSION_TIMEOUT}s"
            )
            result.duration_ms = int((_time.perf_counter() - start) * 1000)
            return result
        except Exception as exc:  # noqa: BLE001
            result.failure_dim = "reachable"
            result.failure_reason = f"reachable probe error: {type(exc).__name__}"
            result.duration_ms = int((_time.perf_counter() - start) * 1000)
            return result

        if not result.reachable:
            result.failure_dim = "reachable"
            result.failure_reason = "codex --version exited non-zero"
            result.duration_ms = int((_time.perf_counter() - start) * 1000)
            return result

        # Dim 4: authenticated (read ~/.codex/auth.json via check_subscription)
        try:
            sub = await self.check_subscription()
            if sub.status == SubscriptionStatus.AUTHENTICATED:
                result.authenticated = True
            else:
                result.authenticated = False
                result.failure_dim = "authenticated"
                result.failure_reason = (
                    f"codex subscription status: {sub.status.value}"
                )
                result.duration_ms = int((_time.perf_counter() - start) * 1000)
                return result
        except Exception as exc:  # noqa: BLE001
            result.authenticated = False
            result.failure_dim = "authenticated"
            result.failure_reason = f"auth probe error: {type(exc).__name__}"
            result.duration_ms = int((_time.perf_counter() - start) * 1000)
            return result

        # Dim 5: callable -- real ``codex exec "ping"``
        try:
            roundtrip = await asyncio.to_thread(
                _run_cmd,
                [self._codex_bin, "exec", _PROBE_PING_PROMPT],
                timeout=_PROBE_ROUNDTRIP_TIMEOUT,
            )
            output = (roundtrip.stdout or "").strip()
            if roundtrip.returncode != 0:
                result.failure_dim = "callable"
                result.failure_reason = (
                    f"round-trip exited {roundtrip.returncode}"
                )
            elif not output:
                result.failure_dim = "callable"
                result.failure_reason = "round-trip returned empty stdout"
            else:
                result.callable = True
        except subprocess.TimeoutExpired:
            result.failure_dim = "callable"
            result.failure_reason = (
                f"round-trip timed out after {_PROBE_ROUNDTRIP_TIMEOUT}s"
            )
        except Exception as exc:  # noqa: BLE001
            result.failure_dim = "callable"
            result.failure_reason = f"round-trip probe error: {type(exc).__name__}"

        result.duration_ms = int((_time.perf_counter() - start) * 1000)
        if result.callable:
            result.failure_dim = None
            result.failure_reason = None
        return result
