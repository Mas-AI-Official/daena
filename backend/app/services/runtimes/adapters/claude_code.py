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
    RuntimeExecutionError,
    RuntimeProbeResult,
    RuntimeStatus,
)

logger = get_logger(__name__)

# Phase 4b PR 2 -- truth-rule probe constants. Founder-locked: callable
# requires a real round-trip, never a binary check. 8s caps the version
# check; 25s caps the round-trip "ping" so even a heavy auth flow has
# room without blocking the registry.
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


class ClaudeCodeAdapter(BaseRuntimeAdapter):
    """Adapter for Claude Code CLI (Anthropic)."""

    def __init__(self) -> None:
        super().__init__(
            runtime_id="claude_code",
            display_name="Claude Code",
        )
        # Resolve claude binary path -- handle WSL where Windows binaries need full path
        import json
        import os
        import shutil

        # Phase 1 F1+F5 (2026-04-24). The 401 we debugged tonight came
        # from /usr/bin/claude in WSL kali-linux as root: the OAuth
        # access token in /root/.claude/.credentials.json had expired
        # (Apr 22) and the CLI's auth status reported logged-in even
        # though API calls returned 401 because the refresh wasn't
        # being applied. Meanwhile the Windows-side binary at
        # /mnt/c/Users/masou/.local/bin/claude.exe works cleanly via
        # WSL interop because it auto-refreshes its tokens via the
        # Windows keychain. Resolution order is now:
        #
        #   1. ``DAENA_CLAUDE_BIN`` env override (operator escape hatch)
        #   2. Native Unix /usr/bin/claude IF its creds are unexpired
        #   3. Windows .exe via WSL interop (works when WSL is root and
        #      the Linux subscription token has gone stale)
        #   4. shutil.which fallback + last-resort literal "claude"
        #
        # The expiry pre-check is a couple-of-millis JSON read; we never
        # call the API, just read the file we'd be authenticating with.
        env_override = os.environ.get("DAENA_CLAUDE_BIN", "").strip()
        self._claude_bin = ""

        if env_override and os.path.isfile(env_override):
            self._claude_bin = env_override
            logger.info("claude_code.init.env_override", binary=env_override)

        def _creds_unexpired(creds_path: str) -> bool:
            try:
                with open(creds_path, encoding="utf-8") as fh:
                    data = json.load(fh)
                inner = data.get("claudeAiOauth") or {}
                ts = float(inner.get("expiresAt", 0)) / 1000.0
                if ts <= 0:
                    return False
                from datetime import datetime, timezone
                return datetime.now(timezone.utc).timestamp() < ts
            except Exception:
                return False

        if not self._claude_bin:
            _native_unix_candidates = [
                "/usr/bin/claude",
                "/usr/local/bin/claude",
                os.path.expanduser("~/.local/bin/claude"),
            ]
            for candidate in _native_unix_candidates:
                if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                    # Don't pick Linux native if its OAuth creds are
                    # expired -- we'd just produce 401s on every call.
                    home_creds = os.path.expanduser("~/.claude/.credentials.json")
                    if _creds_unexpired(home_creds):
                        self._claude_bin = candidate
                        logger.info(
                            "claude_code.init.unix_native",
                            binary=candidate, creds=home_creds,
                        )
                        break
                    else:
                        logger.warning(
                            "claude_code.unix_creds_expired",
                            binary=candidate, creds=home_creds,
                            hint="Run `claude login` in WSL or set DAENA_CLAUDE_BIN to the Windows .exe",
                        )

        if not self._claude_bin:
            # WSL interop fallback: Windows .exe is reachable from
            # kali-linux via /mnt/c/. The Windows binary refreshes its
            # OAuth via the Windows keychain so stays valid even when
            # the Linux file copy has gone stale. We only land here
            # when the Linux native creds are missing or expired.
            _wsl_candidates = [
                "/mnt/c/Users/masou/.local/bin/claude.exe",
                "/mnt/c/Users/masou/.local/bin/claude",
            ]
            for candidate in _wsl_candidates:
                if os.path.isfile(candidate):
                    self._claude_bin = candidate
                    logger.info(
                        "claude_code.init.wsl_interop", binary=candidate,
                    )
                    break

        if not self._claude_bin:
            self._claude_bin = shutil.which("claude") or ""

        if not self._claude_bin:
            self._claude_bin = "claude"  # absolute last resort

        logger.info("claude_code.init", binary=self._claude_bin)

        # Persistent session manager for stateful multi-turn execution
        from app.services.runtimes.adapters.claude_session import ClaudeSessionManager

        self._session_manager = ClaudeSessionManager(claude_bin=self._claude_bin)

    async def check_installed(self) -> bool:
        """Check if claude CLI is installed via PATH resolution.

        Demoted from INFO -> DEBUG (Phase 2 efficiency, 2026-04-24): the
        registry polls every 60s, so logging at INFO each tick floods
        the audit log with 1440 redundant lines/day. The path is fixed
        at adapter init -- we only need INFO on first discovery, which
        the registry handles via ``runtime.discovery_complete``.
        """
        import os

        if self._claude_bin != "claude" and os.path.isfile(self._claude_bin):
            logger.debug("claude_code.installed", path=self._claude_bin)
            return True

        # Fallback: try running it
        try:
            result = await asyncio.to_thread(
                _run_cmd, [self._claude_bin, "--version"], timeout=10.0,
            )
            found = result.returncode == 0
            logger.debug("claude_code.version_check", found=found, output=result.stdout[:100])
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

        Tool capability (Phase 1 F5): we now forward MCP config + extra
        writable dirs + allowed-tools ACL + permission mode from the
        chat orchestrator's context. Without these, the CLI subprocess
        runs as a text-only completion endpoint -- it has no way to
        edit files, run bash, or invoke MCP tools. With them, the
        delegated CLI is an actual autonomous executor.
        """
        cwd = context.get("working_directory", ".")
        session_id = context.get("session_id", "unknown")

        # Tool capability surface -- defaults preserve UNLEASHED-style
        # "skip permissions" so existing chats still work even if the
        # orchestrator hasn't been updated yet (graceful rollout).
        mcp_config_path = context.get("mcp_config_path")
        add_dirs = context.get("add_dirs") or []
        allowed_tools = context.get("allowed_tools")
        permission_mode = context.get("permission_mode", "acceptEdits")
        # Adaptive thinking budget from the three-tier router. Defaults
        # to None (medium-effort behaviour matches CLI default).
        effort = context.get("effort")

        logger.info(
            "claude_code.execute",
            session_id=session_id,
            task=task[:200],
            cwd=cwd,
            mcp_config=bool(mcp_config_path),
            add_dirs_count=len(add_dirs),
            allowed_tools_set=bool(allowed_tools),
            permission_mode=permission_mode if allowed_tools else "skip",
        )

        # Dynamic timeout based on task complexity
        # Short tasks: 120s, medium: 300s, complex (>200 words): 600s
        _word_count = len(task.split())
        _timeout = 120.0 if _word_count < 50 else 300.0 if _word_count < 200 else 600.0

        result = await self._session_manager.send(
            daena_session_id=session_id,
            task=task,
            cwd=cwd,
            timeout=_timeout,
            mcp_config_path=mcp_config_path,
            add_dirs=add_dirs,
            allowed_tools=allowed_tools,
            permission_mode=permission_mode,
            effort=effort,
        )

        if result.is_error:
            raise RuntimeExecutionError(
                runtime_id=self.runtime_id,
                message=result.result_text or "Claude Code execution failed",
            )
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

    async def probe(self) -> RuntimeProbeResult:
        """Real round-trip probe (Phase 4b PR 2).

        Truth ladder:
          1. detected = binary present at resolved path
          2. configured = trivially True once detected (no per-request
             config schema for CLI runtimes; subscription handles it)
          3. reachable = ``claude --version`` exits 0
          4. authenticated = ``check_subscription()`` returns AUTHENTICATED
          5. callable = ``claude -p "ping" --output-format json`` succeeds
             AND the parsed JSON has a non-empty ``result`` field

        Failures NEVER mark callable. A timeout, parse error, or 401
        leaves callable=False with the failing dim recorded. No CLI
        stderr is yielded into the result -- we log it server-side
        only (Asset Shield Hard Law 5: data exfiltration).
        """
        import json
        import os
        import time as _time

        from app.services.runtimes.subscription_auth import SubscriptionStatus

        start = _time.perf_counter()
        result = RuntimeProbeResult()

        # Dim 1: detected
        try:
            detected = (
                self._claude_bin != "claude"
                and os.path.isfile(self._claude_bin)
            )
            if not detected:
                # Last-resort try-running-it check for PATH-only resolution.
                version_check = await asyncio.to_thread(
                    _run_cmd,
                    [self._claude_bin, "--version"],
                    timeout=_PROBE_VERSION_TIMEOUT,
                )
                detected = version_check.returncode == 0
            result.detected = detected
        except Exception as exc:  # noqa: BLE001 -- contract: never raise
            result.failure_dim = "detected"
            result.failure_reason = f"detect probe error: {type(exc).__name__}"
            result.duration_ms = int((_time.perf_counter() - start) * 1000)
            return result

        if not result.detected:
            result.failure_dim = "detected"
            result.failure_reason = "claude binary not found on PATH or DAENA_CLAUDE_BIN"
            result.duration_ms = int((_time.perf_counter() - start) * 1000)
            return result

        # Dim 2: configured (trivially true for CLI runtimes once detected)
        result.configured = True

        # Dim 3: reachable (binary actually executes)
        try:
            version_check = await asyncio.to_thread(
                _run_cmd,
                [self._claude_bin, "--version"],
                timeout=_PROBE_VERSION_TIMEOUT,
            )
            result.reachable = version_check.returncode == 0
        except subprocess.TimeoutExpired:
            result.failure_dim = "reachable"
            result.failure_reason = (
                f"claude --version timed out after {_PROBE_VERSION_TIMEOUT}s"
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
            result.failure_reason = "claude --version exited non-zero"
            result.duration_ms = int((_time.perf_counter() - start) * 1000)
            return result

        # Dim 4: authenticated
        try:
            sub = await self.check_subscription()
            if sub.status == SubscriptionStatus.AUTHENTICATED:
                result.authenticated = True
            else:
                result.authenticated = False
                result.failure_dim = "authenticated"
                result.failure_reason = (
                    f"claude subscription status: {sub.status.value}"
                )
                result.duration_ms = int((_time.perf_counter() - start) * 1000)
                return result
        except Exception as exc:  # noqa: BLE001
            result.authenticated = False
            result.failure_dim = "authenticated"
            result.failure_reason = f"auth probe error: {type(exc).__name__}"
            result.duration_ms = int((_time.perf_counter() - start) * 1000)
            return result

        # Dim 5: callable (real round-trip)
        try:
            roundtrip = await asyncio.to_thread(
                _run_cmd,
                [self._claude_bin, "-p", _PROBE_PING_PROMPT, "--output-format", "json"],
                timeout=_PROBE_ROUNDTRIP_TIMEOUT,
            )
            if roundtrip.returncode != 0:
                result.failure_dim = "callable"
                result.failure_reason = (
                    f"round-trip exited {roundtrip.returncode}"
                )
            else:
                # Parse JSON envelope; need a non-empty result string.
                try:
                    payload = json.loads(roundtrip.stdout.strip())
                except json.JSONDecodeError as parse_exc:
                    result.failure_dim = "callable"
                    result.failure_reason = (
                        f"round-trip output not JSON: {parse_exc.msg}"
                    )
                else:
                    is_error = bool(payload.get("is_error", False))
                    text = str(payload.get("result") or payload.get("text") or "").strip()
                    if is_error:
                        result.failure_dim = "callable"
                        result.failure_reason = (
                            f"round-trip is_error=true: {text[:200]}"
                            if text else "round-trip reported is_error"
                        )
                    elif not text:
                        result.failure_dim = "callable"
                        result.failure_reason = "round-trip returned empty result"
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
