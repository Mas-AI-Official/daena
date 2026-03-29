"""Tests for Daena MCP Server (Sprint 3, Phase 3).

Covers tool definitions, JSON-RPC routing, all 6 tool handlers,
error handling, and MCPToolResult serialization.
"""

from __future__ import annotations

import pytest

from app.services.mcp.server import (
    DAENA_MCP_TOOLS,
    DaenaMCPServer,
    MCPTool,
    MCPToolResult,
)

# ── MCPToolResult tests ──


class TestMCPToolResult:
    def test_to_dict_success(self):
        result = MCPToolResult(
            tool_name="test",
            success=True,
            output={"key": "value"},
        )
        d = result.to_dict()
        assert d["tool_name"] == "test"
        assert d["success"] is True
        assert d["output"] == {"key": "value"}
        assert "error" not in d

    def test_to_dict_with_error(self):
        result = MCPToolResult(
            tool_name="test",
            success=False,
            output=None,
            error="Something went wrong",
        )
        d = result.to_dict()
        assert d["success"] is False
        assert d["error"] == "Something went wrong"

    def test_to_dict_with_metadata(self):
        result = MCPToolResult(
            tool_name="test",
            success=True,
            output="ok",
            metadata={"count": 5},
        )
        d = result.to_dict()
        assert d["metadata"] == {"count": 5}


# ── Tool definitions tests ──


class TestToolDefinitions:
    def test_all_tools_defined(self):
        assert len(DAENA_MCP_TOOLS) == 6

    def test_tool_names(self):
        names = {t.name for t in DAENA_MCP_TOOLS}
        expected = {
            "governance_check",
            "memory_query",
            "skill_retrieve",
            "audit_log",
            "runtime_status",
            "cost_estimate",
        }
        assert names == expected

    def test_each_tool_has_schema(self):
        for tool in DAENA_MCP_TOOLS:
            assert isinstance(tool, MCPTool)
            assert tool.description
            assert tool.input_schema
            assert tool.input_schema.get("type") == "object"


# ── DaenaMCPServer tests ──


class TestDaenaMCPServer:
    @pytest.fixture
    def server(self):
        return DaenaMCPServer()

    def test_get_tool_definitions(self, server):
        defs = server.get_tool_definitions()
        assert len(defs) == 6
        assert all("name" in d for d in defs)
        assert all("inputSchema" in d for d in defs)

    @pytest.mark.asyncio
    async def test_tools_list_method(self, server):
        response = await server.handle_request({
            "method": "tools/list",
            "id": "req-1",
        })
        assert response["id"] == "req-1"
        assert "result" in response
        assert "tools" in response["result"]
        assert len(response["result"]["tools"]) == 6

    @pytest.mark.asyncio
    async def test_unknown_method(self, server):
        response = await server.handle_request({
            "method": "unknown/method",
            "id": "req-2",
        })
        assert "error" in response
        assert response["error"]["code"] == -32601

    @pytest.mark.asyncio
    async def test_unknown_tool(self, server):
        response = await server.handle_request({
            "method": "tools/call",
            "params": {"name": "nonexistent_tool", "arguments": {}},
            "id": "req-3",
        })
        assert "error" in response
        assert "Unknown tool" in response["error"]["message"]

    @pytest.mark.asyncio
    async def test_governance_check(self, server):
        response = await server.handle_request({
            "method": "tools/call",
            "params": {
                "name": "governance_check",
                "arguments": {
                    "action": "delete all files",
                    "action_type": "delete_file",
                },
            },
            "id": "req-4",
        })
        assert "result" in response
        result = response["result"]
        assert result["tool_name"] == "governance_check"
        assert result["success"] is True
        # delete_file should require approval
        assert result["output"]["requires_approval"] is True

    @pytest.mark.asyncio
    async def test_governance_check_safe_action(self, server):
        response = await server.handle_request({
            "method": "tools/call",
            "params": {
                "name": "governance_check",
                "arguments": {
                    "action": "read a file",
                    "action_type": "read_file",
                },
            },
            "id": "req-5",
        })
        result = response["result"]
        assert result["output"]["allowed"] is True
        assert result["output"]["requires_approval"] is False

    @pytest.mark.asyncio
    async def test_memory_query(self, server):
        response = await server.handle_request({
            "method": "tools/call",
            "params": {
                "name": "memory_query",
                "arguments": {
                    "query": "project architecture",
                    "tier_filter": "T2",
                },
            },
            "id": "req-6",
        })
        result = response["result"]
        assert result["success"] is True
        assert result["output"]["query"] == "project architecture"

    @pytest.mark.asyncio
    async def test_skill_retrieve(self, server):
        response = await server.handle_request({
            "method": "tools/call",
            "params": {
                "name": "skill_retrieve",
                "arguments": {
                    "task_description": "build a REST API",
                },
            },
            "id": "req-7",
        })
        result = response["result"]
        assert result["success"] is True
        assert "skills" in result["output"]

    @pytest.mark.asyncio
    async def test_audit_log(self, server):
        response = await server.handle_request({
            "method": "tools/call",
            "params": {
                "name": "audit_log",
                "arguments": {
                    "action": "modified config file",
                    "result": "success",
                    "runtime": "claude_code",
                },
            },
            "id": "req-8",
        })
        result = response["result"]
        assert result["success"] is True
        assert result["output"]["logged"] is True

    @pytest.mark.asyncio
    async def test_runtime_status(self, server):
        response = await server.handle_request({
            "method": "tools/call",
            "params": {
                "name": "runtime_status",
                "arguments": {},
            },
            "id": "req-9",
        })
        result = response["result"]
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_cost_estimate(self, server):
        response = await server.handle_request({
            "method": "tools/call",
            "params": {
                "name": "cost_estimate",
                "arguments": {
                    "runtime_id": "claude_code",
                    "estimated_tokens": 2000,
                },
            },
            "id": "req-10",
        })
        result = response["result"]
        assert result["success"] is True
        assert result["output"]["runtime_id"] == "claude_code"
        assert result["output"]["estimated_cost_usd"] > 0

    @pytest.mark.asyncio
    async def test_cost_estimate_free_runtime(self, server):
        response = await server.handle_request({
            "method": "tools/call",
            "params": {
                "name": "cost_estimate",
                "arguments": {
                    "runtime_id": "ollama",
                    "estimated_tokens": 5000,
                },
            },
            "id": "req-11",
        })
        result = response["result"]
        assert result["output"]["is_free"] is True
        assert result["output"]["estimated_cost_usd"] == 0
