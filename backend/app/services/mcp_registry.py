"""MCP (Model Context Protocol) tool registry.

Discovers and registers tools from MCP-compatible connections,
making them available to DaenaBot for execution through governance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class MCPTool:
    """A tool discovered from an MCP server."""
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    connection_id: str = ""
    governance_tier: int = 2  # Default: NOTIFIED tier for external tools


class MCPRegistry:
    """Discovers and registers tools from MCP connections."""

    def __init__(self) -> None:
        self._tools: dict[str, MCPTool] = {}
        self._connection_urls: dict[str, str] = {}

    @property
    def tool_count(self) -> int:
        """Number of registered MCP tools."""
        return len(self._tools)

    def list_tools(self) -> list[dict[str, Any]]:
        """List all registered MCP tools."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
                "connection_id": t.connection_id,
                "governance_tier": t.governance_tier,
            }
            for t in self._tools.values()
        ]

    def get_tool(self, name: str) -> MCPTool | None:
        """Get a registered MCP tool by name."""
        return self._tools.get(name)

    async def discover_tools(self, connection_id: str, server_url: str) -> list[MCPTool]:
        """Query an MCP server for available tools.

        Args:
            connection_id: The Daena connection ID for this MCP server.
            server_url: The URL of the MCP server.

        Returns:
            List of discovered MCP tools.
        """
        discovered: list[MCPTool] = []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{server_url}/tools/list",
                    json={},
                )
                resp.raise_for_status()
                data = resp.json()

                tools_data = data.get("tools", [])
                for tool_data in tools_data:
                    tool = MCPTool(
                        name=tool_data.get("name", ""),
                        description=tool_data.get("description", ""),
                        input_schema=tool_data.get("inputSchema", {}),
                        connection_id=connection_id,
                        governance_tier=self._classify_governance_tier(tool_data),
                    )
                    discovered.append(tool)

                logger.info(
                    "mcp_registry.tools_discovered",
                    connection_id=connection_id,
                    count=len(discovered),
                )
        except Exception as exc:
            logger.warning(
                "mcp_registry.discovery_failed",
                connection_id=connection_id,
                error=str(exc),
            )

        return discovered

    async def register_tools(self, tools: list[MCPTool]) -> int:
        """Make discovered tools available to DaenaBot.

        Args:
            tools: List of MCP tools to register.

        Returns:
            Number of tools registered.
        """
        registered = 0
        for tool in tools:
            if not tool.name:
                continue
            self._tools[tool.name] = tool
            registered += 1
            logger.info(
                "mcp_registry.tool_registered",
                name=tool.name,
                governance_tier=tool.governance_tier,
            )
        return registered

    def unregister_connection(self, connection_id: str) -> int:
        """Remove all tools from a specific connection.

        Args:
            connection_id: The connection whose tools to remove.

        Returns:
            Number of tools removed.
        """
        to_remove = [
            name for name, tool in self._tools.items()
            if tool.connection_id == connection_id
        ]
        for name in to_remove:
            del self._tools[name]
        return len(to_remove)

    @staticmethod
    def _classify_governance_tier(tool_data: dict) -> int:
        """Classify governance tier based on tool capabilities.

        Destructive or high-risk operations get higher tiers.
        """
        name = tool_data.get("name", "").lower()
        desc = tool_data.get("description", "").lower()
        combined = f"{name} {desc}"

        # Tier 3: requires approval (destructive actions)
        if any(w in combined for w in ("delete", "remove", "drop", "destroy",
                                        "write", "modify", "update", "create",
                                        "send", "post", "execute", "run")):
            return 3

        # Tier 2: notified (read + potentially sensitive)
        if any(w in combined for w in ("read", "get", "list", "search",
                                        "query", "fetch", "download")):
            return 2

        # Tier 1: logged (minimal risk)
        return 1
