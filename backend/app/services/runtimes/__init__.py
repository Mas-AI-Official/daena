"""Runtime Adapter Layer: multi-runtime orchestration for Daena V2.

This package enables Daena to control CLI runtimes (Claude Code, Codex,
Gemini CLI, Grok CLI, Ollama) as first-class execution engines, not just
LLM API calls. Each adapter wraps a subprocess-based CLI tool and exposes
a uniform interface for health checking, capability scoring, and task
execution with streaming output.

Architecture:
    BaseRuntimeAdapter (ABC)
      +-- ClaudeCodeAdapter   (claude CLI)
      +-- CodexAdapter        (codex CLI)
      +-- GeminiCLIAdapter    (gemini CLI)
      +-- GrokCLIAdapter      (grok CLI)
      +-- OllamaRuntimeAdapter (ollama CLI, bridges to existing provider)
      +-- MCPBridgeAdapter    (generic MCP server via stdio/HTTP)

    RuntimeRegistry: discovers installed runtimes, monitors health, selects
    the best runtime for a given task type via capability scoring.
"""

from app.services.runtimes.base_adapter import (
    BaseRuntimeAdapter,
    ExecutionReceipt,
    RuntimeCapability,
    RuntimeStatus,
)
from app.services.runtimes.registry import RuntimeRegistry

__all__ = [
    "BaseRuntimeAdapter",
    "ExecutionReceipt",
    "RuntimeCapability",
    "RuntimeRegistry",
    "RuntimeStatus",
]
