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
    RuntimeProbeResult,
    RuntimeStatus,
)

logger = get_logger(__name__)

_PROBE_VERSION_TIMEOUT = 8.0
_PROBE_ROUNDTRIP_TIMEOUT = 25.0
_PROBE_PING_PROMPT = "ping"


def _gemini_config_search_paths() -> list[Path]:
    """Return every plausible location for a `~/.gemini/` style folder.

    On WSL Linux we run from /root, but the user's real Gemini auth lives
    in their Windows home (mounted at /mnt/c/Users/<user>/). Returning
    BOTH lets Strategy 2 find auth wherever it actually was written.
    """
    candidates: list[Path] = [Path.home() / ".gemini"]
    # WSL -> Windows home enumeration (only matters when we're inside WSL)
    try:
        users_root = Path("/mnt/c/Users")
        if users_root.is_dir():
            for child in users_root.iterdir():
                cfg = child / ".gemini"
                if cfg.is_dir():
                    candidates.append(cfg)
    except (OSError, PermissionError):
        pass
    return candidates


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
        except (subprocess.TimeoutExpired, TimeoutError, FileNotFoundError, OSError) as exc:
            # subprocess.run raises TimeoutExpired (NOT TimeoutError) on
            # timeout; without catching it explicitly the exception
            # propagated up the gather chain, killed Strategy 2, and the
            # UI lost the gemini subscription card. 2026-05-09 fix.
            logger.info(
                "gemini_cli.strategy1_skipped",
                reason=type(exc).__name__,
                detail=str(exc)[:120],
            )

        # Strategy 2: Check every ~/.gemini/ config file we can find
        # (own home AND every Windows home visible via WSL /mnt/c).
        try:
            for gemini_dir in _gemini_config_search_paths():
                if not gemini_dir.is_dir():
                    continue
                oauth_file = gemini_dir / "oauth_creds.json"
                if not oauth_file.exists():
                    # Some installs keep only google_accounts.json + tokens
                    # in google_accounts.json itself; walk that as fallback.
                    accounts_file = gemini_dir / "google_accounts.json"
                    if accounts_file.exists():
                        try:
                            accts = _json.loads(accounts_file.read_text(encoding="utf-8"))
                            if accts.get("active") or accts.get("accounts"):
                                user_email = (
                                    accts.get("active")
                                    or next(iter(accts.get("accounts", {}).keys()), "Google account")
                                )
                                logger.info(
                                    "gemini_cli.auth_detected_via_accounts",
                                    email=user_email,
                                    config_dir=str(gemini_dir),
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
                            pass
                    continue

                # oauth_creds.json present:
                try:
                    creds = _json.loads(oauth_file.read_text(encoding="utf-8"))
                    has_token = bool(
                        creds.get("access_token") or creds.get("refresh_token")
                    )
                    if has_token:
                        # Get email from google_accounts.json
                        user_email = "Google account"
                        accounts_file = gemini_dir / "google_accounts.json"
                        if accounts_file.exists():
                            try:
                                accts = _json.loads(
                                    accounts_file.read_text(encoding="utf-8")
                                )
                                user_email = accts.get("active", user_email)
                            except (_json.JSONDecodeError, OSError):
                                pass

                        # Check plan from settings.json
                        plan_name = "Google/Gemini"
                        settings_file = gemini_dir / "settings.json"
                        if settings_file.exists():
                            try:
                                settings = _json.loads(
                                    settings_file.read_text(encoding="utf-8")
                                )
                                auth_type = (
                                    settings.get("security", {})
                                    .get("auth", {})
                                    .get("selectedType", "")
                                )
                                if "personal" in auth_type:
                                    plan_name = "Google One AI Pro"
                            except (_json.JSONDecodeError, OSError):
                                pass

                        logger.info(
                            "gemini_cli.auth_detected",
                            email=user_email,
                            plan=plan_name,
                        )
                        return SubscriptionAuth(
                            method=AuthMethod.SUBSCRIPTION,
                            status=SubscriptionStatus.AUTHENTICATED,
                            user_display=user_email,
                            plan_name=plan_name,
                            setup_command="gemini auth login",
                            login_url="https://gemini.google.com",
                        )
                except (_json.JSONDecodeError, OSError):
                    pass

            # Fallback: check other possible config locations (own home
            # AND every Windows home visible via WSL /mnt/c).
            fallback_paths: list[Path] = [
                Path.home() / ".config" / "gemini-cli" / "settings.json",
                Path.home() / ".config" / "gemini" / "auth.json",
            ]
            try:
                users_root = Path("/mnt/c/Users")
                if users_root.is_dir():
                    for child in users_root.iterdir():
                        for tail in ("gemini-cli/settings.json", "gemini/auth.json"):
                            cand = child / "AppData" / "Roaming" / tail
                            if cand.exists():
                                fallback_paths.append(cand)
            except (OSError, PermissionError):
                pass
            for cfg_path in fallback_paths:
                if cfg_path.exists():
                    try:
                        data = _json.loads(cfg_path.read_text(encoding="utf-8"))
                        has_auth = bool(
                            data.get("access_token")
                            or data.get("refresh_token")
                        )
                        if has_auth:
                            return SubscriptionAuth(
                                method=AuthMethod.SUBSCRIPTION,
                                status=SubscriptionStatus.AUTHENTICATED,
                                user_display=data.get("email", "Google account"),
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

    async def probe(self) -> RuntimeProbeResult:
        """Real round-trip probe (Phase 4b PR 2).

        gemini CLI hangs on --version when not authenticated, so we
        gate dim 3 (reachable) on a short timeout and treat hang-then-
        timeout as "reachable=false, failure_reason=hang".

        Truth ladder:
          1. detected = `gemini` resolves on PATH
          2. configured = trivially True once detected
          3. reachable = ``gemini --version`` returns within 8s with rc=0
             (a hang is treated as not-reachable)
          4. authenticated = check_subscription returns AUTHENTICATED
          5. callable = ``gemini -p "ping"`` returns non-empty stdout
        """
        import time as _time

        from app.services.runtimes.subscription_auth import SubscriptionStatus

        start = _time.perf_counter()
        result = RuntimeProbeResult()

        # Dim 1: detected
        if shutil.which("gemini") is None:
            result.failure_dim = "detected"
            result.failure_reason = "gemini binary not on PATH"
            result.duration_ms = int((_time.perf_counter() - start) * 1000)
            return result
        result.detected = True
        result.configured = True

        # Dim 3: reachable (gemini --version may hang -- timeout-gated)
        try:
            version_check = await asyncio.to_thread(
                _run_cmd, ["gemini", "--version"], timeout=_PROBE_VERSION_TIMEOUT,
            )
            result.reachable = version_check.returncode == 0
            if not result.reachable:
                result.failure_dim = "reachable"
                result.failure_reason = "gemini --version exited non-zero"
                result.duration_ms = int((_time.perf_counter() - start) * 1000)
                return result
        except subprocess.TimeoutExpired:
            result.failure_dim = "reachable"
            result.failure_reason = (
                f"gemini --version hung past {_PROBE_VERSION_TIMEOUT}s "
                "(typical of unauthenticated CLI)"
            )
            result.duration_ms = int((_time.perf_counter() - start) * 1000)
            return result
        except Exception as exc:  # noqa: BLE001
            result.failure_dim = "reachable"
            result.failure_reason = f"reachable probe error: {type(exc).__name__}"
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
                    f"gemini subscription status: {sub.status.value}"
                )
                result.duration_ms = int((_time.perf_counter() - start) * 1000)
                return result
        except Exception as exc:  # noqa: BLE001
            result.authenticated = False
            result.failure_dim = "authenticated"
            result.failure_reason = f"auth probe error: {type(exc).__name__}"
            result.duration_ms = int((_time.perf_counter() - start) * 1000)
            return result

        # Dim 5: callable -- real `gemini -p "ping"` round-trip
        try:
            roundtrip = await asyncio.to_thread(
                _run_cmd,
                ["gemini", "-p", _PROBE_PING_PROMPT],
                timeout=_PROBE_ROUNDTRIP_TIMEOUT,
            )
            output = (roundtrip.stdout or "").strip()
            if roundtrip.returncode != 0:
                result.failure_dim = "callable"
                result.failure_reason = f"round-trip exited {roundtrip.returncode}"
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
