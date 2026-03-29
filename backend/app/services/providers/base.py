"""Abstract base class for all LLM provider adapters.

Every provider (Ollama, Anthropic, OpenAI, etc.) implements this
interface.  The model router and LLM service interact ONLY through
this contract — no provider-specific logic leaks upstream.

Design:
    - generate() → LLMResponse   (single-shot, full response)
    - stream()   → AsyncIterator[LLMChunk]  (token-by-token)
    - health_check() → HealthStatus  (for registry monitoring)
    - list_models() → list[ModelInfo]  (self-reported catalog)

All methods are async.  Providers that wrap synchronous SDKs must
use ``asyncio.to_thread()`` internally.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from app.core.constants import HealthStatus, ModelProvider

# ── Data structures ────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class LLMMessage:
    """Single message in a conversation turn."""

    role: str  # "system" | "user" | "assistant" | "tool"
    content: str
    name: str | None = None  # optional speaker name
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ModelInfo:
    """Metadata about a model offered by a provider."""

    model_id: str  # e.g. "llama3.1:8b", "claude-sonnet-4-20250514"
    provider: ModelProvider
    display_name: str = ""
    context_window: int = 4096
    supports_streaming: bool = True
    supports_vision: bool = False
    supports_tools: bool = False
    cost_per_1m_input: float = 0.0  # USD
    cost_per_1m_output: float = 0.0  # USD
    tags: list[str] = field(default_factory=list)  # e.g. ["fast", "coding"]


@dataclass(slots=True)
class LLMResponse:
    """Structured response from a provider generate() call.

    Carries the content plus all metadata needed for governance
    audit, cost tracking, and quality scoring.
    """

    content: str
    model_id: str
    provider: ModelProvider
    token_count_input: int = 0
    token_count_output: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    finish_reason: str = "stop"  # stop | length | tool_calls | error
    raw: dict[str, Any] = field(default_factory=dict)  # provider-specific payload


@dataclass(frozen=True, slots=True)
class LLMChunk:
    """Single token/chunk from a streaming response."""

    content: str
    model_id: str
    provider: ModelProvider
    finish_reason: str | None = None  # set on final chunk
    token_index: int = 0


@dataclass(frozen=True, slots=True)
class GenerateRequest:
    """Input parameters for a generate/stream call.

    Centralises all tunables so providers don't need
    scattered **kwargs.
    """

    messages: list[LLMMessage]
    model_id: str | None = None  # None = let provider pick default
    temperature: float = 0.7
    max_tokens: int = 2048
    top_p: float = 1.0
    stop_sequences: list[str] = field(default_factory=list)
    system_prompt: str | None = None
    stream: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


# ── Abstract base ──────────────────────────────────────────────


class BaseProvider(ABC):
    """Contract that every LLM provider adapter must implement.

    Subclasses set ``provider`` in __init__ and implement the
    four abstract methods.  The base class provides timing helpers
    and a standard error-wrapping pattern.
    """

    provider: ModelProvider

    def __init__(self, provider: ModelProvider) -> None:
        self.provider = provider
        self._healthy: HealthStatus = HealthStatus.HEALTHY

    # ── Abstract interface ────────────────────────────────────

    @abstractmethod
    async def generate(self, request: GenerateRequest) -> LLMResponse:
        """Send a prompt and return the full response.

        Implementations must:
        - Populate token counts and cost on the response
        - Set latency_ms (or use _timed_generate helper)
        - Raise ProviderError on transient failures
        """

    @abstractmethod
    async def stream(
        self, request: GenerateRequest
    ) -> AsyncIterator[LLMChunk]:
        """Yield response tokens one at a time.

        Final chunk must have ``finish_reason`` set.
        Providers that don't support streaming should fall back to
        generate() and yield the full content as a single chunk.
        """
        # pragma: no cover — abstract
        yield  # type: ignore[misc]

    @abstractmethod
    async def health_check(self) -> HealthStatus:
        """Probe provider availability.

        Called periodically by the model registry.
        Should be fast (<2s timeout) and not count toward billing.
        """

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        """Return models currently available from this provider.

        For cloud providers this may be a hardcoded catalog.
        For Ollama this queries the local API.
        """

    # ── Helpers ────────────────────────────────────────────────

    def _start_timer(self) -> float:
        """Return a monotonic start time for latency tracking."""
        return time.monotonic()

    def _elapsed_ms(self, start: float) -> int:
        """Milliseconds elapsed since ``start``."""
        return int((time.monotonic() - start) * 1000)

    def _compute_cost(
        self,
        model_info: ModelInfo,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Calculate USD cost from token counts and model pricing."""
        input_cost = (input_tokens / 1_000_000) * model_info.cost_per_1m_input
        output_cost = (output_tokens / 1_000_000) * model_info.cost_per_1m_output
        return round(input_cost + output_cost, 8)

    @property
    def status(self) -> HealthStatus:
        """Last known health status."""
        return self._healthy

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} provider={self.provider.value}>"
