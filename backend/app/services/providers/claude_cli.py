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
    display_name="Claude Code (Max/Pro)",
    cmd_template=["{bin}", "--model", "opus", "-p", "{prompt}", "--output-format", "json"],
    stdin_template=["{bin}", "--model", "opus", "-p", "-", "--output-format", "json"],
    json_output=True,
    context_window=200_000,
    tags=["reasoning", "coding", "analysis", "large", "planning"],
)

CODEX_SPEC = CliRuntimeSpec(
    runtime_id="codex",
    binary_name="codex",
    model_id=CODEX_CLI_MODEL_ID,
    provider=ModelProvider.OPENAI,
    display_name="Codex (ChatGPT Plus/Pro)",
    cmd_template=["{bin}", "exec", "{prompt}"],
    stdin_template=["{bin}", "exec", "-"],
    json_output=False,
    context_window=128_000,
    tags=["coding", "refactoring", "bulk", "analysis", "reasoning"],
)

GEMINI_SPEC = CliRuntimeSpec(
    runtime_id="gemini_cli",
    binary_name="gemini",
    model_id=GEMINI_CLI_MODEL_ID,
    provider=ModelProvider.GEMINI,
    display_name="Gemini CLI (Google One AI Pro)",
    cmd_template=["{bin}", "-p", "{prompt}"],
    stdin_template=["{bin}", "-p", "-"],
    json_output=False,
    context_window=1_000_000,
    tags=["research", "analysis", "large", "web_search", "reasoning"],
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
    """
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE if stdin_input else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
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
        self._bin = shutil.which(spec.binary_name) or spec.binary_name
        self._installed: bool | None = None
        logger.info(
            "cli_provider.init",
            runtime=spec.runtime_id,
            binary=self._bin,
        )

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
            logger.error(
                "cli_provider.timeout",
                runtime=self._spec.runtime_id,
                prompt_size=len(prompt),
            )
            return LLMResponse(
                content=f"[{self._spec.display_name} is still processing. The task may need to be broken into steps.]",
                model_id=self._spec.model_id,
                provider=self._spec.provider,
                latency_ms=self._elapsed_ms(start),
                finish_reason="timeout",
            )
        except Exception as exc:
            logger.error(
                "cli_provider.error",
                runtime=self._spec.runtime_id,
                error=str(exc),
            )
            return LLMResponse(
                content=f"[{self._spec.display_name} error: {exc}]",
                model_id=self._spec.model_id,
                provider=self._spec.provider,
                latency_ms=self._elapsed_ms(start),
                finish_reason="error",
            )

        # Parse output
        if self._spec.json_output:
            content, cost_usd, duration_ms, num_turns = self._parse_json_result(result.stdout)
        else:
            content = result.stdout.strip()[:8000] or f"[No output from {self._spec.display_name}]"
            cost_usd, duration_ms, num_turns = 0.0, self._elapsed_ms(start), 1

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
        """Parse JSON CLI output (Claude format)."""
        lines = stdout.strip().splitlines()
        for line in reversed(lines):
            try:
                data = json.loads(line)
                if data.get("type") == "result":
                    return (
                        data.get("result", ""),
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
