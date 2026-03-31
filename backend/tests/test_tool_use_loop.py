"""Tests for the agentic tool-use loop infrastructure.

Covers:
- ToolSchemaBuilder: schema generation, tool prompt building, MCP auto-discovery
- parse_tool_calls: parsing tool calls from LLM responses
- resolve_tool_call: mapping schema names to dispatch paths
- ToolUseLoop: tool execution dispatch for ALL tool categories
"""

from __future__ import annotations

import pytest

from app.services.tool_schema_builder import (
    build_tool_schema,
    build_tool_prompt,
    parse_tool_calls,
    resolve_tool_call,
    TOOL_DISPATCH_MAP,
)


class TestBuildToolSchema:
    """Tests for build_tool_schema."""

    def test_returns_list(self):
        schema = build_tool_schema()
        assert isinstance(schema, list)

    def test_includes_system_tools(self):
        schema = build_tool_schema(include_system=True, include_integrations=False, include_workflows=False, include_daenabot=False, include_desktop=False)
        names = {t["name"] for t in schema}
        assert "read_file" in names
        assert "write_file" in names
        assert "run_command" in names
        assert "list_directory" in names

    def test_includes_new_system_tools(self):
        """Verify expanded system tools are present."""
        schema = build_tool_schema(include_system=True, include_integrations=False, include_workflows=False, include_daenabot=False, include_desktop=False)
        names = {t["name"] for t in schema}
        assert "run_python" in names
        assert "delete_file" in names
        assert "move_file" in names
        assert "copy_file" in names
        assert "http_get" in names
        assert "http_post" in names
        assert "install_package" in names

    def test_includes_integration_tools(self):
        schema = build_tool_schema(include_system=False, include_integrations=True, include_workflows=False, include_daenabot=False, include_desktop=False)
        names = {t["name"] for t in schema}
        assert "gmail_search" in names
        assert "calendar_list_events" in names
        assert "notion_search" in names

    def test_filters_by_connected_providers(self):
        schema = build_tool_schema(
            include_system=False, include_integrations=True,
            include_workflows=False, include_daenabot=False, include_desktop=False,
            connected_providers=["gmail"],
        )
        names = {t["name"] for t in schema}
        assert "gmail_search" in names
        assert "calendar_list_events" not in names
        assert "notion_search" not in names

    def test_includes_workflow_tools(self):
        schema = build_tool_schema(include_system=False, include_integrations=False, include_workflows=True, include_daenabot=False, include_desktop=False)
        names = {t["name"] for t in schema}
        assert "run_workflow" in names

    def test_includes_browser_tools(self):
        """Verify expanded browser tools."""
        schema = build_tool_schema(include_system=False, include_integrations=False, include_workflows=False, include_daenabot=True, include_desktop=False)
        names = {t["name"] for t in schema}
        assert "browser_navigate" in names
        assert "browser_screenshot" in names
        assert "browser_extract_text" in names
        assert "browser_fill_form" in names
        assert "browser_click" in names
        assert "mcp_call" in names

    def test_includes_desktop_tools(self):
        """Verify desktop control tools."""
        schema = build_tool_schema(include_system=False, include_integrations=False, include_workflows=False, include_daenabot=False, include_desktop=True)
        names = {t["name"] for t in schema}
        assert "desktop_screenshot" in names
        assert "desktop_click" in names
        assert "desktop_type" in names
        assert "desktop_hotkey" in names
        assert "desktop_scroll" in names
        assert "desktop_move_mouse" in names

    def test_desktop_tools_can_be_excluded(self):
        """Verify desktop tools respect include_desktop flag."""
        schema = build_tool_schema(include_desktop=False)
        names = {t["name"] for t in schema}
        assert "desktop_screenshot" not in names

    def test_mcp_auto_discovery(self):
        """Verify MCP tools from registry are included."""

        class FakeRegistry:
            def list_tools(self):
                return [
                    {"name": "custom_tool", "description": "Does something", "input_schema": {"type": "object", "properties": {"x": {"type": "string"}}}},
                    {"name": "other_tool", "description": "Does other thing", "input_schema": {}},
                ]

        schema = build_tool_schema(
            include_system=False, include_integrations=False,
            include_workflows=False, include_daenabot=False, include_desktop=False,
            include_mcp=True, mcp_registry=FakeRegistry(),
        )
        names = {t["name"] for t in schema}
        assert "mcp_custom_tool" in names
        assert "mcp_other_tool" in names
        assert len(schema) == 2

    def test_mcp_no_registry_no_crash(self):
        """Verify no crash when mcp_registry is None."""
        schema = build_tool_schema(include_mcp=True, mcp_registry=None)
        # Should still return other tools without error
        assert isinstance(schema, list)

    def test_all_tools_have_required_fields(self):
        schema = build_tool_schema()
        for tool in schema:
            assert "name" in tool, f"Tool missing 'name': {tool}"
            assert "description" in tool, f"Tool {tool.get('name')} missing 'description'"
            assert isinstance(tool["name"], str)
            assert isinstance(tool["description"], str)

    def test_full_schema_has_expanded_count(self):
        """Full schema should have 30+ tools now."""
        schema = build_tool_schema()
        assert len(schema) >= 30, f"Expected 30+ tools, got {len(schema)}"

    def test_no_duplicate_tool_names(self):
        """Ensure no duplicate names in full schema."""
        schema = build_tool_schema()
        names = [t["name"] for t in schema]
        assert len(names) == len(set(names)), f"Duplicate tool names: {[n for n in names if names.count(n) > 1]}"


class TestBuildToolPrompt:
    """Tests for build_tool_prompt."""

    def test_empty_tools_returns_empty(self):
        assert build_tool_prompt([]) == ""

    def test_includes_tool_call_format(self):
        tools = [{"name": "test", "description": "A test tool", "parameters": {"type": "object", "properties": {}}}]
        prompt = build_tool_prompt(tools)
        assert "tool_call" in prompt
        assert "test" in prompt
        assert "A test tool" in prompt

    def test_includes_parameter_info(self):
        tools = [{
            "name": "search",
            "description": "Search something",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        }]
        prompt = build_tool_prompt(tools)
        assert "query" in prompt
        assert "required" in prompt.lower()


class TestParseToolCalls:
    """Tests for parse_tool_calls."""

    def test_parse_tool_call_block(self):
        response = '''Here's what I found:
```tool_call
{"tool": "gmail_search", "params": {"query": "is:unread"}}
```
Let me check that for you.'''
        calls = parse_tool_calls(response)
        assert len(calls) == 1
        assert calls[0]["tool"] == "gmail_search"
        assert calls[0]["params"]["query"] == "is:unread"

    def test_parse_multiple_tool_calls(self):
        response = '''I'll check both:
```tool_call
{"tool": "gmail_search", "params": {"query": "is:unread"}}
```
And also:
```tool_call
{"tool": "calendar_list_events", "params": {}}
```'''
        calls = parse_tool_calls(response)
        assert len(calls) == 2
        assert calls[0]["tool"] == "gmail_search"
        assert calls[1]["tool"] == "calendar_list_events"

    def test_no_tool_calls_returns_empty(self):
        response = "Here is a regular response with no tool calls."
        calls = parse_tool_calls(response)
        assert len(calls) == 0

    def test_parse_bare_json(self):
        response = '{"tool": "read_file", "params": {"path": "/tmp/test.txt"}}'
        calls = parse_tool_calls(response)
        assert len(calls) == 1
        assert calls[0]["tool"] == "read_file"

    def test_handles_malformed_json(self):
        response = '```tool_call\n{not valid json}\n```'
        calls = parse_tool_calls(response)
        assert len(calls) == 0

    def test_handles_arguments_key(self):
        response = '```tool_call\n{"tool": "test", "arguments": {"key": "val"}}\n```'
        calls = parse_tool_calls(response)
        assert len(calls) == 1
        assert calls[0]["params"] == {"key": "val"}


class TestResolveToolCall:
    """Tests for resolve_tool_call."""

    def test_resolve_system_tool(self):
        qualified, params = resolve_tool_call("read_file", {"path": "/tmp/x"})
        assert qualified == "file.read_file"

    def test_resolve_gmail_tool(self):
        qualified, params = resolve_tool_call("gmail_search", {"query": "test"})
        assert qualified == "gmail.search_emails"

    def test_resolve_calendar_tool(self):
        qualified, params = resolve_tool_call("calendar_list_events", {})
        assert qualified == "calendar.list_events"

    def test_resolve_notion_tool(self):
        qualified, params = resolve_tool_call("notion_search", {"query": "test"})
        assert qualified == "notion.search_pages"

    def test_resolve_workflow_tool(self):
        qualified, params = resolve_tool_call("run_workflow", {"workflow_id": "ops.daily_briefing"})
        assert qualified == "workflow.run"

    def test_resolve_terminal_tool(self):
        qualified, params = resolve_tool_call("run_command", {"command": "ls"})
        assert qualified == "terminal.execute_command"

    def test_resolve_new_system_tools(self):
        """Test dispatch for newly added system tools."""
        cases = {
            "run_python": "terminal.run_python",
            "delete_file": "file.delete_file",
            "move_file": "file.move_file",
            "copy_file": "file.copy_file",
            "http_get": "network.http_get",
            "http_post": "network.http_post",
            "install_package": "terminal.install_package",
        }
        for schema_name, expected_qualified in cases.items():
            qualified, _ = resolve_tool_call(schema_name, {})
            assert qualified == expected_qualified, f"{schema_name} -> {qualified} (expected {expected_qualified})"

    def test_resolve_browser_tools(self):
        """Test dispatch for expanded browser tools."""
        cases = {
            "browser_extract_text": "browser.extract_text",
            "browser_fill_form": "browser.fill_form",
            "browser_click": "browser.click_element",
        }
        for schema_name, expected_qualified in cases.items():
            qualified, _ = resolve_tool_call(schema_name, {})
            assert qualified == expected_qualified, f"{schema_name} -> {qualified}"

    def test_resolve_desktop_tools(self):
        """Test dispatch for desktop control tools."""
        cases = {
            "desktop_screenshot": "desktop.screenshot",
            "desktop_click": "desktop.click",
            "desktop_type": "desktop.type_text",
            "desktop_hotkey": "desktop.hotkey",
            "desktop_scroll": "desktop.scroll",
            "desktop_move_mouse": "desktop.move_mouse",
        }
        for schema_name, expected_qualified in cases.items():
            qualified, _ = resolve_tool_call(schema_name, {})
            assert qualified == expected_qualified, f"{schema_name} -> {qualified}"

    def test_resolve_mcp_call(self):
        """Test MCP bridge tool resolution."""
        qualified, params = resolve_tool_call("mcp_call", {"tool_name": "custom", "arguments": {}})
        assert qualified == "mcp.call_tool"

    def test_resolve_auto_discovered_mcp_tool(self):
        """Auto-discovered MCP tools (mcp_ prefix) should resolve to mcp.call_tool."""
        qualified, params = resolve_tool_call("mcp_custom_tool", {"x": 1})
        assert qualified == "mcp.call_tool"
        assert params["tool_name"] == "custom_tool"
        assert params["arguments"] == {"x": 1}

    def test_unknown_tool_passes_through(self):
        qualified, params = resolve_tool_call("custom.tool", {"x": 1})
        assert qualified == "custom.tool"

    def test_all_dispatch_entries_have_two_parts(self):
        for schema_name, (prefix, operation) in TOOL_DISPATCH_MAP.items():
            assert isinstance(prefix, str) and prefix, f"Bad prefix for {schema_name}"
            assert isinstance(operation, str) and operation, f"Bad operation for {schema_name}"

    def test_dispatch_map_coverage(self):
        """Every tool in the schema should have a dispatch mapping."""
        schema = build_tool_schema(include_mcp=False)
        for tool in schema:
            name = tool["name"]
            assert name in TOOL_DISPATCH_MAP, f"Tool '{name}' in schema but not in TOOL_DISPATCH_MAP"


class TestToolUseLoop:
    """Tests for ToolUseLoop execution."""

    @pytest.mark.asyncio
    async def test_execute_file_read(self):
        """Test that the loop can execute a file read tool."""
        import tempfile
        import os
        from unittest.mock import AsyncMock
        import uuid

        # Create a temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            temp_path = f.name

        try:
            from app.services.tool_use_loop import ToolUseLoop
            loop = ToolUseLoop(
                db=AsyncMock(),
                user_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                agi_mode=True,
            )
            result = await loop._execute_tool("read_file", {"path": temp_path})
            assert result["success"] is True
            assert "hello world" in result["content"]
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_execute_file_write(self):
        """Test file write tool."""
        import tempfile
        import os
        from unittest.mock import AsyncMock
        import uuid

        temp_path = tempfile.mktemp(suffix=".txt")
        try:
            from app.services.tool_use_loop import ToolUseLoop
            loop = ToolUseLoop(
                db=AsyncMock(),
                user_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                agi_mode=True,
            )
            result = await loop._execute_tool("write_file", {"path": temp_path, "content": "test content"})
            assert result["success"] is True

            # Verify it was written
            read_result = await loop._execute_tool("read_file", {"path": temp_path})
            assert "test content" in read_result["content"]
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_execute_file_delete_archives(self):
        """Test that delete archives instead of permanent delete (Hard Law #6)."""
        import tempfile
        import os
        from pathlib import Path
        from unittest.mock import AsyncMock
        import uuid

        # Use a unique temp directory to avoid collisions with existing .archive
        tmpdir = tempfile.mkdtemp()
        temp_path = os.path.join(tmpdir, "archive_me.txt")
        with open(temp_path, "w") as f:
            f.write("archive me")

        try:
            from app.services.tool_use_loop import ToolUseLoop
            loop = ToolUseLoop(
                db=AsyncMock(),
                user_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                agi_mode=True,
            )
            result = await loop._execute_tool("delete_file", {"path": temp_path})
            assert result["success"] is True
            assert "Archived" in result["message"]
            # Original should be gone
            assert not os.path.exists(temp_path)
            # Archive dir should exist within the temp dir
            archive_dir = Path(tmpdir) / ".archive"
            assert archive_dir.exists()
        finally:
            # Clean up entire temp directory
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_execute_file_move(self):
        """Test file move tool."""
        import tempfile
        import os
        from unittest.mock import AsyncMock
        import uuid

        src = tempfile.mktemp(suffix=".txt")
        dst = tempfile.mktemp(suffix=".txt")
        with open(src, "w") as f:
            f.write("move me")

        try:
            from app.services.tool_use_loop import ToolUseLoop
            loop = ToolUseLoop(
                db=AsyncMock(),
                user_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                agi_mode=True,
            )
            result = await loop._execute_tool("move_file", {"source": src, "destination": dst})
            assert result["success"] is True
            assert not os.path.exists(src)
            assert os.path.exists(dst)
        finally:
            for p in (src, dst):
                if os.path.exists(p):
                    os.unlink(p)

    @pytest.mark.asyncio
    async def test_execute_file_copy(self):
        """Test file copy tool."""
        import tempfile
        import os
        from unittest.mock import AsyncMock
        import uuid

        src = tempfile.mktemp(suffix=".txt")
        dst = tempfile.mktemp(suffix=".txt")
        with open(src, "w") as f:
            f.write("copy me")

        try:
            from app.services.tool_use_loop import ToolUseLoop
            loop = ToolUseLoop(
                db=AsyncMock(),
                user_id=uuid.uuid4(),
                tenant_id=uuid.uuid4(),
                agi_mode=True,
            )
            result = await loop._execute_tool("copy_file", {"source": src, "destination": dst})
            assert result["success"] is True
            assert os.path.exists(src)  # Original still there
            assert os.path.exists(dst)  # Copy exists
        finally:
            for p in (src, dst):
                if os.path.exists(p):
                    os.unlink(p)

    @pytest.mark.asyncio
    async def test_execute_run_python(self):
        """Test Python execution tool."""
        from unittest.mock import AsyncMock
        import uuid

        from app.services.tool_use_loop import ToolUseLoop
        loop = ToolUseLoop(
            db=AsyncMock(),
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            agi_mode=True,
        )
        result = await loop._execute_tool("run_python", {"code": "print(2 + 2)"})
        assert result["success"] is True
        assert "4" in result["stdout"]

    @pytest.mark.asyncio
    async def test_execute_http_get(self):
        """Test HTTP GET (mocked)."""
        from unittest.mock import AsyncMock, patch, MagicMock
        import uuid

        from app.services.tool_use_loop import ToolUseLoop
        loop = ToolUseLoop(
            db=AsyncMock(),
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            agi_mode=True,
        )

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>test</html>"
        mock_response.headers = {}

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await loop._execute_tool("http_get", {"url": "https://example.com"})
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_list_directory(self):
        """Test that the loop can list a directory."""
        import uuid
        from unittest.mock import AsyncMock

        from app.services.tool_use_loop import ToolUseLoop
        loop = ToolUseLoop(
            db=AsyncMock(),
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
        )
        result = await loop._execute_tool("list_directory", {"path": "."})
        assert result["success"] is True
        assert isinstance(result["entries"], list)

    @pytest.mark.asyncio
    async def test_execute_search_files(self):
        """Test file search tool."""
        import uuid
        from unittest.mock import AsyncMock

        from app.services.tool_use_loop import ToolUseLoop
        loop = ToolUseLoop(
            db=AsyncMock(),
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
        )
        result = await loop._execute_tool("search_files", {"pattern": "*.py", "root": "."})
        assert result["success"] is True
        assert isinstance(result["files"], list)

    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        """Test that unknown tools return error."""
        import uuid
        from unittest.mock import AsyncMock

        from app.services.tool_use_loop import ToolUseLoop
        loop = ToolUseLoop(
            db=AsyncMock(),
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
        )
        result = await loop._execute_tool("nonexistent_tool", {})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_workflow_unknown(self):
        """Test workflow execution with unknown ID."""
        import uuid
        from unittest.mock import AsyncMock

        from app.services.tool_use_loop import ToolUseLoop
        loop = ToolUseLoop(
            db=AsyncMock(),
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
        )
        result = await loop._execute_tool("run_workflow", {"workflow_id": "nonexistent"})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_desktop_fallback_no_pyautogui(self):
        """Desktop tools should try MCP fallback if pyautogui unavailable."""
        import uuid
        from unittest.mock import AsyncMock, patch

        from app.services.tool_use_loop import ToolUseLoop
        loop = ToolUseLoop(
            db=AsyncMock(),
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            agi_mode=True,
        )

        # Mock pyautogui as not available + MCP fallback
        with patch.dict("sys.modules", {"pyautogui": None}):
            with patch.object(loop, "_exec_desktop_via_mcp", new_callable=AsyncMock) as mock_mcp:
                mock_mcp.return_value = {"success": True, "message": "Screenshot via MCP"}
                result = await loop._exec_desktop("screenshot", {})
                # Should have tried MCP fallback
                mock_mcp.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_mcp_call(self):
        """Test MCP bridge execution."""
        import uuid
        from unittest.mock import AsyncMock, patch, MagicMock

        from app.services.tool_use_loop import ToolUseLoop
        loop = ToolUseLoop(
            db=AsyncMock(),
            user_id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            agi_mode=True,
        )

        with patch("app.services.daenabot.mcp_agent.MCPAgent") as MockMCP:
            mock_agent = MagicMock()
            mock_agent.execute = AsyncMock(return_value={
                "status": "success",
                "output": {"tool": "test", "result": "ok"},
            })
            MockMCP.return_value = mock_agent

            result = await loop._exec_mcp("call_tool", {"tool_name": "test", "arguments": {}})
            assert result["success"] is True

    def test_strip_tool_calls(self):
        from app.services.tool_use_loop import ToolUseLoop
        text = 'Before ```tool_call\n{"tool": "x"}\n``` After'
        result = ToolUseLoop._strip_tool_calls(text)
        assert "Before" in result
        assert "After" in result
        assert "tool_call" not in result

    def test_format_tool_results(self):
        """Test tool result formatting."""
        from app.services.tool_use_loop import ToolUseLoop
        calls = [{"tool": "read_file", "params": {"path": "/tmp/x"}}]
        results = [{"tool": "read_file", "result": {"success": True, "content": "hello"}}]
        formatted = ToolUseLoop._format_tool_results(calls, results)
        assert "read_file" in formatted
        assert "hello" in formatted
