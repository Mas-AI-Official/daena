"""MCPAgent: executes MCP tool calls through governance.

Bridges DaenaBot's execution framework with external MCP servers,
applying governance checks before every tool invocation.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.logging import get_logger
from app.services.daenabot._base_agent import BaseAgent

logger = get_logger(__name__)


class MCPAgent(BaseAgent):
    """Executes MCP tool calls through governance."""

    agent_name = "mcp"

    OPERATION_ACTION_MAP: dict[str, str] = {
        "call_tool": "MCP_TOOL_CALL",
    }

    def __init__(self, server_url: str = "") -> None:
        self._server_url = server_url

    async def execute(
        self, operation: str, params: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute an MCP tool call.

        Args:
            operation: Always "call_tool" for MCP.
            params: Must include "tool_name" and "arguments".
                    May include "server_url" override.

        Returns:
            Standardised result dict.
        """
        if operation != "call_tool":
            return self._error(operation, f"Unknown MCP operation: {operation}")

        tool_name = params.get("tool_name", "")
        arguments = params.get("arguments", {})
        server_url = params.get("server_url", self._server_url)

        if not tool_name:
            return self._error(operation, "Missing tool_name parameter")
        if not server_url:
            return self._error(operation, "No MCP server URL configured")

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{server_url}/tools/call",
                    json={
                        "name": tool_name,
                        "arguments": arguments,
                    },
                )
                resp.raise_for_status()
                result_data = resp.json()

                return self._result(
                    operation,
                    output={
                        "tool": tool_name,
                        "result": result_data.get("content", result_data),
                    },
                )
        except httpx.TimeoutException:
            return self._error(operation, f"MCP tool '{tool_name}' timed out")
        except Exception as exc:
            return self._error(operation, f"MCP tool '{tool_name}' failed: {exc}")
