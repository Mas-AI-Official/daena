"""Tests for MCP tool registry."""

from __future__ import annotations

import asyncio

import pytest

from app.services.mcp_registry import MCPRegistry, MCPTool


@pytest.fixture()
def registry() -> MCPRegistry:
    """Fresh MCPRegistry instance for each test."""
    return MCPRegistry()


def _run(coro):  # noqa: ANN001, ANN202
    """Run an async coroutine synchronously."""
    return asyncio.get_event_loop().run_until_complete(coro)


class TestMCPRegistry:
    def test_register_tools(self, registry: MCPRegistry) -> None:
        tools = [
            MCPTool(name="read_doc", description="Read a document", connection_id="conn-1"),
            MCPTool(name="search", description="Search content", connection_id="conn-1"),
        ]
        count = _run(registry.register_tools(tools))
        assert count == 2
        assert registry.tool_count == 2

    def test_list_tools(self, registry: MCPRegistry) -> None:
        tools = [
            MCPTool(name="read_doc", description="Read a document", connection_id="conn-1"),
        ]
        _run(registry.register_tools(tools))
        listed = registry.list_tools()
        assert len(listed) == 1
        assert listed[0]["name"] == "read_doc"

    def test_get_tool(self, registry: MCPRegistry) -> None:
        tool = MCPTool(name="search", description="Search", connection_id="conn-1")
        _run(registry.register_tools([tool]))
        found = registry.get_tool("search")
        assert found is not None
        assert found.name == "search"

    def test_get_nonexistent_tool(self, registry: MCPRegistry) -> None:
        assert registry.get_tool("nonexistent") is None

    def test_unregister_connection(self, registry: MCPRegistry) -> None:
        tools = [
            MCPTool(name="tool1", description="T1", connection_id="conn-1"),
            MCPTool(name="tool2", description="T2", connection_id="conn-1"),
            MCPTool(name="tool3", description="T3", connection_id="conn-2"),
        ]
        _run(registry.register_tools(tools))
        removed = registry.unregister_connection("conn-1")
        assert removed == 2
        assert registry.tool_count == 1

    def test_classify_governance_tier_destructive(self) -> None:
        tier = MCPRegistry._classify_governance_tier(
            {"name": "delete_record", "description": "Delete a database record"}
        )
        assert tier == 3

    def test_classify_governance_tier_read(self) -> None:
        tier = MCPRegistry._classify_governance_tier(
            {"name": "get_info", "description": "Get user information"}
        )
        assert tier == 2

    def test_classify_governance_tier_minimal(self) -> None:
        tier = MCPRegistry._classify_governance_tier(
            {"name": "ping", "description": "Health check"}
        )
        assert tier == 1

    def test_empty_tool_name_skipped(self, registry: MCPRegistry) -> None:
        tools = [MCPTool(name="", description="empty")]
        count = _run(registry.register_tools(tools))
        assert count == 0
