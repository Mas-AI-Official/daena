"""Runtime adapters for CLI tools.

Each adapter wraps a specific CLI tool and implements BaseRuntimeAdapter.
"""

from app.services.runtimes.adapters.claude_code import ClaudeCodeAdapter
from app.services.runtimes.adapters.codex import CodexAdapter
from app.services.runtimes.adapters.gemini_cli import GeminiCLIAdapter
from app.services.runtimes.adapters.grok_cli import GrokCLIAdapter
from app.services.runtimes.adapters.mcp_bridge import MCPBridgeAdapter
from app.services.runtimes.adapters.ollama_adapter import OllamaRuntimeAdapter

__all__ = [
    "ClaudeCodeAdapter",
    "CodexAdapter",
    "GeminiCLIAdapter",
    "GrokCLIAdapter",
    "MCPBridgeAdapter",
    "OllamaRuntimeAdapter",
]
