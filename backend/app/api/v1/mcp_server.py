"""MCP Server endpoints: exposes Daena as an MCP server.

External tools connect to these endpoints to use Daena's governance,
memory, skills, and audit capabilities via the MCP protocol.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, get_current_user
from app.core.logging import get_logger
from app.services.mcp.server import DaenaMCPServer

logger = get_logger(__name__)

router = APIRouter()

# Singleton MCP server instance
_mcp_server: DaenaMCPServer | None = None


def _get_mcp_server() -> DaenaMCPServer:
    """Get or create the singleton MCP server."""
    global _mcp_server
    if _mcp_server is None:
        _mcp_server = DaenaMCPServer()
    return _mcp_server


@router.get("/tools")
async def list_tools(
    user: CurrentUser = Depends(get_current_user),
):
    """List all MCP tools Daena exposes."""
    server = _get_mcp_server()
    return {"tools": server.get_tool_definitions()}


@router.post("/call")
async def call_tool(
    request: dict,
    user: CurrentUser = Depends(get_current_user),
):
    """Handle an MCP tool call request.

    Accepts JSON-RPC style requests and routes to the appropriate
    tool handler.
    """
    server = _get_mcp_server()

    # Wrap in MCP request format if not already
    if "method" not in request:
        request = {
            "method": "tools/call",
            "params": request,
            "id": "http-call",
        }

    result = await server.handle_request(request)
    return result


@router.post("/jsonrpc")
async def jsonrpc_endpoint(
    request: dict,
    user: CurrentUser = Depends(get_current_user),
):
    """Full JSON-RPC MCP endpoint for tools/list and tools/call."""
    server = _get_mcp_server()
    return await server.handle_request(request)
