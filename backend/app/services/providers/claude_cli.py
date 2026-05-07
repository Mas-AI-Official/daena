"""CLI-based LLM providers — wraps CLI runtimes as pipeline providers.

Each CLI runtime (Claude Code, Codex, Gemini CLI) can serve as a proper
LLM provider that participates in the full Daena pipeline: model routing,
Council synthesis, Quintessence DCP experts, memory recall, governance.

Uses subscription-based auth (Max/Pro plans). No API key needed.
If an API key IS configured, the API-based provider takes priority.
The CLI provider only registers when no API key exists for that slot.

Provider slot mapping:
    claude  CLI -> ANTHROPIC  (Claude Max/Pro subscription)
    codex   CLI -> OPENAI     (ChatGPT Plus/Pro subscription)
    gemini  CLI -> GEMINI     (Google AI subscription, free tier available)

The runtime adapters in services/runtimes/ handle EXE-mode tool execution.
These providers handle CMD-mode LLM reasoning through the pipeline.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from collections.abc import AsyncIterator
from dataclasses import dataclass

from app.core.constants import HealthStatus, ModelProvider
from app.core.logging import get_logger
from app.services.providers.base import (
    BaseProvider,
    GenerateRequest,
    LLMChunk,
    LLMResponse,
    ModelInfo,
)

logger = get_logger(__name__)


# ── CLI auth-error sentinels ───────────────────────────────────────────
# Strings that mean the CLI was reachable but rejected the request due
# to missing/invalid credentials. When the CLI emits any of these as
# content (instead of as a non-zero exit + stderr), we MUST raise rather
# than treat the message as a successful response — otherwise the
# orchestrator's fallback chain stops at the first auth failure and
# never tries Codex / Gemini / Grok / Ollama.
_CLI_AUTH_ERROR_MARKERS = (
    "not logged in",
    "please run /login",
    "please run `claude login`",
    "please run claude login",
    "api error: 401",
    "api error: 403",
    "authentication_error",
    "invalid authentication credentials",
    "credentials are invalid",
    "session expired",
    "unauthorized",
    "[claude code error",
    "[claude cli error",
    "[codex error",
    "[gemini error",
)


def _looks_like_cli_auth_error(text: str) -> bool:
    """True if the CLI's response content is an auth/credential error."""
    if not text:
        return False
    lower = text.lower()
    return any(marker in lower for marker in _CLI_AUTH_ERROR_MARKERS)

# Model IDs that the registry and router use
CLAUDE_CLI_MODEL_ID = "claude-code-cli"
CODEX_CLI_MODEL_ID = "codex-cli"
GEMINI_CLI_MODEL_ID = "gemini-cli"

# Map runtime IDs to their CLI provider model IDs
CLI_RUNTIME_TO_MODEL = {
    "claude_code": CLAUDE_CLI_MODEL_ID,
    "codex": CODEX_CLI_MODEL_ID,
    "gemini_cli": GEMINI_CLI_MODEL_ID,
}


@dataclass(frozen=True, slots=True)
class CliRuntimeSpec:
    """Specification for a CLI runtime."""

    runtime_id: str
    binary_name: str
    model_id: str
    provider: ModelProvider
    display_name: str
    cmd_template: list[str]  # e.g. ["{bin}", "-p", "{prompt}", "--output-format", "json"]
    stdin_template: list[str]  # for large prompts via stdin
    json_output: bool  # whether output is JSON (Claude) or plain text (Codex, Gemini)
    context_window: int
    tags: list[str]


# ── CLI runtime specifications ─────────────────────────────────

CLAUDE_SPEC = CliRuntimeSpec(
    runtime_id="claude_code",
    binary_name="claude",
    model_id=CLAUDE_CLI_MODEL_ID,
    provider=ModelProvider.ANTHROPIC,
    display_name="Claude Sonnet (CLI)",
    # 2026-04-22: rolled back from explicit ``claude-sonnet-4-7-max`` to
    # the ``sonnet`` alias. The explicit ID was rejected by the CLI on
    # at least one authenticated account with:
    #   "There's an issue with the selected model (claude-sonnet-4-7-
    #   max). It may not exist or you may not have access to it."
    # The ``sonnet`` alias is permanent on the Anthropic CLI and always
    # resolves to the latest Sonnet available to the subscription. If
    # the explicit 4.7-max ID needs to be re-pinned later (e.g. for
    # benchmarking a specific version), do it via founder_policy
    # preferred-model override, not here -- the default should be the
    # alias so the registered CLI continues to work for every tier of
    # subscription Daena ships to.
    cmd_template=["{bin}", "--model", "sonnet", "-p", "{prompt}", "--output-format", "json"],
    stdin_template=["{bin}", "--model", "sonnet", "-p", "-", "--output-format", "json"],
    json_output=True,
    context_window=1_000_000,
    tags=["reasoning", "coding", "analysis", "large", "planning", "frontier", "priority"],
)

CODEX_SPEC = CliRuntimeSpec(
    runtime_id="codex",
    binary_name="codex",
    model_id=CODEX_CLI_MODEL_ID,
    provider=ModelProvider.OPENAI,
    display_name="Codex 5.4 (CLI subscription)",
    # Codex CLI picks its model server-side based on the ChatGPT Pro
    # subscription tier. When 5.4 rolls out in the CLI we get it
    # automatically; no flag to pin explicitly yet.
    cmd_template=["{bin}", "exec", "{prompt}"],
    stdin_template=["{bin}", "exec", "-"],
    json_output=False,
    context_window=400_000,
    tags=["coding", "code", "refactoring", "bulk", "analysis", "reasoning", "large", "frontier", "priority"],
)

GEMINI_SPEC = CliRuntimeSpec(
    runtime_id="gemini_cli",
    binary_name="gemini",
    model_id=GEMINI_CLI_MODEL_ID,
    provider=ModelProvider.GEMINI,
    display_name="Gemini 3.1 Pro (CLI subscription)",
    # Gemini CLI already targets 3.1 Pro in the founder's config;
    # the ``-m`` flag would pin a specific variant if ever needed.
    cmd_template=["{bin}", "-p", "{prompt}"],
    stdin_template=["{bin}", "-p", "-"],
    json_output=False,
    context_window=1_000_000,
    tags=["reasoning", "analysis", "large", "vision", "long-context", "web_search", "frontier", "priority"],
)

ALL_CLI_SPECS = [CLAUDE_SPEC, CODEX_SPEC, GEMINI_SPEC]


def _run_cli(
    cmd: list[str],
    *,
    stdin_input: str | None = None,
    timeout: float = 600.0,
) -> subprocess.CompletedProcess[str]:
    """Run CLI command synchronously (called from thread pool).

    Uses Popen + communicate so the process is properly killed on timeout.

    WSL -> Windows interop env fix (Phase 1 F1.b, 2026-04-24): when the
    binary is a Windows .exe under /mnt/c/, force USERPROFILE so the
    Windows CLI can find its OAuth credentials in C:\\Users\\<user>\\.claude\\.
    Without this the binary defaults to HOME=/root and 401s.
    """
    import os

    env = os.environ.copy()
    bin_path = cmd[0] if cmd else ""
    if bin_path.startswith("/mnt/"):
        try:
            parts = bin_path.lstrip("/").split("/")
            if len(parts) >= 4 and parts[0] == "mnt" and parts[2].lower() == "users":
                drive = parts[1].upper() + ":"
                user_home = f"{drive}\\Users\\{parts[3]}"
                env.setdefault("USERPROFILE", user_home)
                env.setdefault("HOMEDRIVE", drive)
                env.setdefault("HOMEPATH", f"\\Users\\{parts[3]}")
                env.setdefault("APPDATA", f"{user_home}\\AppData\\Roaming")
                env.setdefault("LOCALAPPDATA", f"{user_home}\\AppData\\Local")
        except Exception:
            pass

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE if stdin_input else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    try:
        stdout, stderr = proc.communicate(
            input=stdin_input,
            timeout=timeout,
        )
        return subprocess.CompletedProcess(
            args=cmd, returncode=proc.returncode,
            stdout=stdout, stderr=stderr,
        )
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)
        raise


class CliProvider(BaseProvider):
    """Generic LLM provider for CLI runtimes.

    Wraps any CLI runtime (Claude, Codex, Gemini) as a proper LLM
    provider that can participate in Council/QE synthesis.
    """

    def __init__(self, spec: CliRuntimeSpec) -> None:
        super().__init__(spec.provider)
        self._spec = spec
        # Phase 1 F1 (2026-04-24). For Claude specifically, mirror the
        # adapter's binary-resolution: env override -> /usr/bin/claude
        # if its OAuth token is still fresh -> Windows .exe via WSL
        # interop. The Council/Quintessence path was hitting 401s with
        # the Linux native binary because the token expired Apr 22 even
        # though `claude auth status` reported logged-in. Other CLIs
        # (codex, gemini) still use plain shutil.which.
        if spec.binary_name == "claude":
            self._bin = self._resolve_claude_bin()
        else:
            self._bin = shutil.which(spec.binary_name) or spec.binary_name
        self._installed: bool | None = None
        logger.info(
            "cli_provider.init",
            runtime=spec.runtime_id,
            binary=self._bin,
        )

    @staticmethod
    def _resolve_claude_bin() -> str:
        """Phase 1 F1 (2026-04-24) -- mirrors claude_code adapter logic.

        See backend/app/services/runtimes/adapters/claude_code.py for the
        full rationale. Short version: pick whichever binary actually has
        valid OAuth credentials right now.
        """
        import json
        import os

        env_override = os.environ.get("DAENA_CLAUDE_BIN", "").strip()
        if env_override and os.path.isfile(env_override):
            return env_override

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

        for candidate in ("/usr/bin/claude", "/usr/local/bin/claude"):
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                if _creds_unexpired(os.path.expanduser("~/.claude/.credentials.json")):
                    return candidate
                # else: fall through to WSL interop

        for candidate in (
            "/mnt/c/Users/masou/.local/bin/claude.exe",
            "/mnt/c/Users/masou/.local/bin/claude",
        ):
            if os.path.isfile(candidate):
                return candidate

        return shutil.which("claude") or "claude"

    async def generate(self, request: GenerateRequest) -> LLMResponse:
        """Send prompt to CLI and return full response."""
        start = self._start_timer()
        prompt = self._build_prompt(request)

        logger.info(
            "cli_provider.generate",
            runtime=self._spec.runtime_id,
            prompt_size=len(prompt),
        )

        # Build command — use stdin for large prompts (>8KB)
        use_stdin = len(prompt) > 8000
        if use_stdin:
            cmd = [
                s.format(bin=self._bin, prompt=prompt)
                for s in self._spec.stdin_template
            ]
        else:
            cmd = [
                s.format(bin=self._bin, prompt=prompt)
                for s in self._spec.cmd_template
            ]

        try:
            result = await asyncio.to_thread(
                _run_cli, cmd,
                stdin_input=prompt if use_stdin else None,
                timeout=600.0,
            )
        except subprocess.TimeoutExpired:
            # RAISE so the failover chain catches it and tries next provider
            from app.core.exceptions import ProviderError

            logger.error(
                "cli_provider.timeout",
                runtime=self._spec.runtime_id,
                prompt_size=len(prompt),
            )
            raise ProviderError(
                f"{self._spec.display_name} timed out after 600s"
            )
        except Exception as exc:
            from app.core.exceptions import ProviderError

            # Classify the error to help the health tracker
            error_msg = str(exc)
            logger.error(
                "cli_provider.error",
                runtime=self._spec.runtime_id,
                error=error_msg,
            )
            raise ProviderError(
                f"{self._spec.display_name} error: {error_msg}"
            )

        # Check for CLI-level errors in the output (non-zero exit, error stderr)
        if result.returncode != 0:
            from app.core.exceptions import ProviderError

            stderr = (result.stderr or "").strip()[:500]
            _err_msg = f"{self._spec.display_name} CLI exit code {result.returncode}: {stderr}"
            logger.warning(
                "cli_provider.cli_error",
                runtime=self._spec.runtime_id,
                returncode=result.returncode,
                stderr=stderr[:200],
            )
            # If there IS stdout content despite error exit code, use it
            # (some CLIs return useful output with non-zero exit)
            if not result.stdout.strip():
                raise ProviderError(_err_msg)

        # Parse output. _parse_json_result may raise ProviderError on
        # is_error=True (auth failure, etc.) — that bubbles up so the
        # orchestrator's fallback chain can try the next runtime.
        if self._spec.json_output:
            content, cost_usd, duration_ms, num_turns = self._parse_json_result(result.stdout)
        else:
            content = result.stdout.strip()[:8000] or f"[No output from {self._spec.display_name}]"
            cost_usd, duration_ms, num_turns = 0.0, self._elapsed_ms(start), 1

        # Final guard: detect known error sentinels in the content even
        # when the CLI returned exit 0 + non-JSON output. Claude CLI
        # sometimes emits "Not logged in" via stdout with rc=0 in older
        # builds. Without this guard the cascade would treat the error
        # message as a valid response.
        if _looks_like_cli_auth_error(content):
            from app.core.exceptions import ProviderError
            logger.warning(
                "cli_provider.auth_error_in_content",
                runtime=self._spec.runtime_id,
                excerpt=content[:120],
            )
            raise ProviderError(f"{self._spec.display_name}: {content[:200]}")

        return LLMResponse(
            content=content,
            model_id=self._spec.model_id,
            provider=self._spec.provider,
            token_count_input=len(prompt) // 4,
            token_count_output=len(content) // 4,
            cost_usd=cost_usd,
            latency_ms=self._elapsed_ms(start),
            finish_reason="stop",
            raw={"duration_ms": duration_ms, "num_turns": num_turns},
        )

    async def stream(self, request: GenerateRequest) -> AsyncIterator[LLMChunk]:
        """Simulate streaming by chunking the full CLI response."""
        response = await self.generate(request)
        chunk_size = 30
        content = response.content
        for i in range(0, len(content), chunk_size):
            chunk = content[i:i + chunk_size]
            yield LLMChunk(
                content=chunk,
                model_id=self._spec.model_id,
                provider=self._spec.provider,
                finish_reason="stop" if i + chunk_size >= len(content) else None,
                token_index=i // chunk_size,
            )

    async def close(self) -> None:
        """No persistent connections to close for CLI providers."""

    async def health_check(self) -> HealthStatus:
        """Check if the CLI binary is installed."""
        if self._installed is None:
            import os
            self._installed = (
                self._bin != self._spec.binary_name
                and os.path.isfile(self._bin)
            ) or shutil.which(self._spec.binary_name) is not None

        self._healthy = HealthStatus.HEALTHY if self._installed else HealthStatus.UNAVAILABLE
        return self._healthy

    async def list_models(self) -> list[ModelInfo]:
        """Report this CLI runtime as an available model."""
        if self._installed is None:
            await self.health_check()
        if not self._installed:
            return []
        return [
            ModelInfo(
                model_id=self._spec.model_id,
                provider=self._spec.provider,
                display_name=self._spec.display_name,
                context_window=self._spec.context_window,
                supports_streaming=True,
                supports_vision=False,
                supports_tools=True,
                cost_per_1m_input=0.0,
                cost_per_1m_output=0.0,
                tags=self._spec.tags,
            ),
        ]

    @staticmethod
    def _build_prompt(request: GenerateRequest) -> str:
        """Convert GenerateRequest messages into a single prompt string."""
        parts: list[str] = []
        if request.system_prompt:
            parts.append(request.system_prompt)
        for msg in request.messages:
            if msg.role == "system":
                parts.append(msg.content)
            elif msg.role == "user":
                parts.append(msg.content)
            elif msg.role == "assistant":
                parts.append(f"[Previous response]: {msg.content}")
        return "\n\n".join(parts)

    @staticmethod
    def _parse_json_result(stdout: str) -> tuple[str, float, int, int]:
        """Parse JSON CLI output (Claude format).

        Claude CLI emits one JSON event per line. The terminal "result"
        event carries either a successful response (subtype="success",
        is_error=False) OR a wrapped error (is_error=True, e.g. "Not
        logged in"). Previously the parser blindly returned data.result
        in both cases, so an auth failure was treated as a successful
        empty-ish answer and the orchestrator's fallback chain never
        advanced. Now we raise on is_error=True so the caller in
        generate() catches it and the chain moves on.
        """
        from app.core.exceptions import ProviderError

        lines = stdout.strip().splitlines()
        for line in reversed(lines):
            try:
                data = json.loads(line)
                if data.get("type") == "result":
                    if data.get("is_error") is True:
                        # Surface the wrapped error so the orchestrator
                        # treats this provider as failed and walks the chain.
                        msg = data.get("result") or data.get("subtype") or "Claude CLI error"
                        raise ProviderError(f"Claude CLI: {msg}")
                    result_text = data.get("result", "")
                    # Even when is_error is missing/false, some CLI builds
                    # stuff "Not logged in" into the result text. Detect
                    # and raise so the chain advances.
                    if _looks_like_cli_auth_error(result_text):
                        raise ProviderError(f"Claude CLI: {result_text[:200]}")
                    return (
                        result_text,
                        data.get("total_cost_usd", 0.0),
                        data.get("duration_ms", 0),
                        data.get("num_turns", 0),
                    )
            except json.JSONDecodeError:
                continue
        raw = stdout.strip()[:4000] if stdout.strip() else "[No response]"
        return raw, 0.0, 0, 0


# ── Factory: backward-compatible singleton name ─────────────────

ClaudeCliProvider = lambda: CliProvider(CLAUDE_SPEC)  # noqa: E731
