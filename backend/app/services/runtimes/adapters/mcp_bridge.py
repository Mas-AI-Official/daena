"""MCP Bridge adapter.

Generic adapter for Model Context Protocol servers. Bridges external
MCP tools into Daena's runtime layer, enabling tool discovery,
capability assessment, and governed execution.

MCP servers can expose tools via stdio or HTTP transports. This adapter
wraps both patterns and presents them as a runtime.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from app.core.logging import get_logger
from app.services.runtimes.base_adapter import (
    BaseRuntimeAdapter,
    RuntimeCapability,
    RuntimeStatus,
)

logger = get_logger(__name__)


class MCPBridgeAdapter(BaseRuntimeAdapter):
    """Generic MCP server adapter.

    Can wrap any MCP-compliant tool server. Configuration specifies
    how to connect (stdio command or HTTP URL) and what tools it
    exposes.
    """

    def __init__(
        self,
        server_name: str,
        command: list[str] | None = None,
        url: str | None = None,
        capabilities: RuntimeCapability | None = None,
    ) -> None:
        """Initialize MCP bridge.

        Args:
            server_name: Unique name for this MCP server.
            command: Subprocess command for stdio transport (e.g. ["node", "server.js"]).
            url: HTTP URL for HTTP transport.
            capabilities: Override default capability scores.
        """
        super().__init__(
            runtime_id=f"mcp_{server_name}",
            display_name=f"MCP: {server_name}",
        )
        self._command = command
        self._url = url
        self._custom_capabilities = capabilities
        self._process: asyncio.subprocess.Process | None = None
        self._tools: list[dict[str, Any]] = []

    async def check_installed(self) -> bool:
        """Check if the MCP server can be started."""
        if self._url:
            # HTTP transport: check if URL is reachable
            import httpx
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(self._url, timeout=5.0)
                    return resp.status_code < 500
            except (httpx.ConnectError, httpx.TimeoutException, OSError):
                return False

        if self._command:
            # stdio transport: check if command exists
            try:
                proc = await asyncio.create_subprocess_exec(
                    self._command[0], "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await asyncio.wait_for(proc.wait(), timeout=5.0)
                return True  # command exists, even if --version is not supported
            except (TimeoutError, FileNotFoundError, OSError):
                return False

        return False

    async def check_health(self) -> RuntimeStatus:
        """Check if MCP server is responsive."""
        installed = await self.check_installed()
        if not installed:
            return RuntimeStatus.NOT_INSTALLED
        return RuntimeStatus.ONLINE

    async def get_capabilities(self) -> RuntimeCapability:
        """MCP servers have domain-specific capabilities."""
        if self._custom_capabilities:
            return self._custom_capabilities
        # Default: moderate scores, no cost (depends on underlying tool)
        return RuntimeCapability(
            complex_reasoning=3.0,
            code_generation=3.0,
            code_editing=3.0,
            file_operations=5.0,
            web_research=3.0,
            data_analysis=3.0,
            browser_automation=3.0,
            simple_chat=2.0,
            bulk_operations=5.0,
            cost_per_1k_tokens=0.0,
        )

    async def execute(
        self, task: str, context: dict[str, Any],
    ) -> AsyncIterator[str]:
        """Execute an MCP tool call.

        For stdio transport, spawns the MCP server and communicates
        via JSON-RPC over stdin/stdout. For HTTP transport, makes
        tool call requests to the server URL.
        """
        tool_name = context.get("tool_name", "")
        tool_args = context.get("tool_args", {})

        if self._url:
            # HTTP transport
            async for chunk in self._execute_http(tool_name, tool_args):
                yield chunk
        elif self._command:
            # stdio transport
            async for chunk in self._execute_stdio(tool_name, tool_args):
                yield chunk
        else:
            yield "[ERROR] MCP server has no transport configured"

    async def _execute_http(
        self, tool_name: str, tool_args: dict,
    ) -> AsyncIterator[str]:
        """Execute tool via HTTP transport."""
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._url}/tools/{tool_name}",
                    json=tool_args,
                    timeout=60.0,
                )
                resp.raise_for_status()
                yield resp.text
        except httpx.HTTPError as e:
            yield f"[ERROR] MCP HTTP call failed: {e}"

    async def _execute_stdio(
        self, tool_name: str, tool_args: dict,
    ) -> AsyncIterator[str]:
        """Execute tool via stdio transport (JSON-RPC)."""
        assert self._command is not None
        try:
            proc = await asyncio.create_subprocess_exec(
                *self._command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._process = proc

            # Send JSON-RPC tool call
            request = json.dumps({
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": tool_args,
                },
                "id": 1,
            }) + "\n"

            assert proc.stdin is not None
            proc.stdin.write(request.encode())
            await proc.stdin.drain()
            proc.stdin.close()

            # Read response
            assert proc.stdout is not None
            async for line in proc.stdout:
                decoded = line.decode("utf-8", errors="replace").strip()
                if decoded:
                    yield decoded

            await proc.wait()
        except OSError as e:
            yield f"[ERROR] MCP stdio execution failed: {e}"
        finally:
            self._process = None

    async def cancel(self, session_id: str) -> bool:
        """Cancel a running MCP execution."""
        if self._process and self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=3.0)
            except TimeoutError:
                self._process.kill()
            return True
        return False

    def get_auth_requirements(self) -> dict[str, Any]:
        return {
            "type": "varies",
            "description": f"MCP server '{self.display_name}' may require configuration",
            "transport": "http" if self._url else "stdio",
            "command": self._command,
            "url": self._url,
        }
