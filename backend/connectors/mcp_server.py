"""
MCP Server for Daena
====================

Exposes Daena's tools as an MCP server, allowing external agents
to use Daena's capabilities via the Model Context Protocol.

Usage:
    python -m backend.connectors.mcp_server

Or integrate with FastAPI:
    from backend.connectors.mcp_server import mcp_router
    app.include_router(mcp_router, prefix="/mcp")
"""

import json
import logging
from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from .mcp_adapter import get_mcp_adapter, MCPToolCall

logger = logging.getLogger(__name__)

# FastAPI router for MCP endpoints
mcp_router = APIRouter(tags=["MCP"])


@mcp_router.get("/tools")
async def list_mcp_tools():
    """List all available MCP tools."""
    adapter = get_mcp_adapter()
    return {
        "tools": adapter.list_tools()
    }


@mcp_router.post("/tools/call")
async def call_mcp_tool(request: Request):
    """Execute an MCP tool call."""
    try:
        body = await request.json()
        
        adapter = get_mcp_adapter()
        tool_call = adapter.parse_tool_call(body)
        
        result = await adapter.execute_tool(tool_call)
        
        return result.to_mcp_format()
        
    except Exception as e:
        logger.error(f"MCP tool call failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@mcp_router.post("/rpc")
async def mcp_rpc(request: Request):
    """
    JSON-RPC 2.0 endpoint for full MCP compatibility.
    
    Supports:
    - tools/list: List available tools
    - tools/call: Execute a tool
    - resources/list: List available resources
    - resources/read: Read a resource
    """
    try:
        body = await request.json()
        
        # Validate JSON-RPC format
        if body.get("jsonrpc") != "2.0":
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32600, "message": "Invalid Request"},
                "id": body.get("id")
            }, status_code=400)
        
        method = body.get("method", "")
        params = body.get("params", {})
        request_id = body.get("id", 1)
        
        adapter = get_mcp_adapter()
        
        if method == "tools/list":
            return JSONResponse({
                "jsonrpc": "2.0",
                "result": {"tools": adapter.list_tools()},
                "id": request_id
            })
        
        elif method == "tools/call":
            tool_call = MCPToolCall(
                id=str(request_id),
                name=params.get("name", ""),
                arguments=params.get("arguments", {})
            )
            result = await adapter.execute_tool(tool_call)
            
            return JSONResponse({
                "jsonrpc": "2.0",
                "result": {"content": result.content, "isError": result.is_error},
                "id": request_id
            })
        
        elif method == "resources/list":
            # Return available resources (workspace files, etc.)
            resources = [
                {
                    "uri": "file:///workspace",
                    "name": "Workspace",
                    "description": "Current Daena workspace"
                },
                {
                    "uri": "daena://council/finance",
                    "name": "Finance Council",
                    "description": "Consult the finance council"
                },
                {
                    "uri": "daena://council/tech",
                    "name": "Tech Council",
                    "description": "Consult the tech council"
                }
            ]
            return JSONResponse({
                "jsonrpc": "2.0",
                "result": {"resources": resources},
                "id": request_id
            })
        
        elif method == "resources/read":
            uri = params.get("uri", "")
            # TODO: Implement resource reading
            return JSONResponse({
                "jsonrpc": "2.0",
                "result": {"contents": [{"type": "text", "text": f"Resource at {uri}"}]},
                "id": request_id
            })
        
        else:
            return JSONResponse({
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method not found: {method}"},
                "id": request_id
            }, status_code=404)
            
    except json.JSONDecodeError:
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {"code": -32700, "message": "Parse error"},
            "id": None
        }, status_code=400)
    except Exception as e:
        logger.error(f"MCP RPC error: {e}")
        return JSONResponse({
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": str(e)},
            "id": body.get("id") if 'body' in dir() else None
        }, status_code=500)


@mcp_router.get("/health")
async def mcp_health():
    """Health check for MCP server."""
    adapter = get_mcp_adapter()
    return {
        "status": "healthy",
        "tools_registered": len(adapter.tools),
        "protocol": "MCP 1.0"
    }


# Standalone server mode
if __name__ == "__main__":
    import uvicorn
    from fastapi import FastAPI
    
    app = FastAPI(title="Daena MCP Server")
    app.include_router(mcp_router)
    
    print("🔌 Starting Daena MCP Server on http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001)
