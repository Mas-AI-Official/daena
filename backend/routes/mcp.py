"""
MCP API Routes - Manage MCP servers and tools
"""
from fastapi import APIRouter, HTTPException, Body, Header
from typing import Dict, Any, List, Optional
from backend.services.mcp.mcp_registry import get_mcp_registry

router = APIRouter(prefix="/api/v1/connections/mcp", tags=["mcp"])

@router.get("")
async def list_mcp_servers() -> List[Dict[str, Any]]:
    """List all configured MCP servers"""
    registry = get_mcp_registry()
    servers = []
    
    for server_id, cfg in registry.config.items():
        client = registry.clients.get(server_id)
        servers.append({
            "id": server_id,
            "name": cfg.get("name", server_id),
            "enabled": cfg.get("enabled", False),
            "status": "connected" if client else "disconnected",
            "tools": [t["name"] for t in client.tools] if client else []
        })
        
    return servers

@router.post("/{server_id}/enable")
async def enable_server(server_id: str) -> Dict[str, Any]:
    """Enable and start an MCP server"""
    registry = get_mcp_registry()
    if server_id not in registry.config:
        raise HTTPException(status_code=404, detail="Server not found")
        
    try:
        await registry.start_server(server_id, registry.config[server_id])
        registry.config[server_id]["enabled"] = True
        # TODO: Save config to disk
        return {"success": True, "message": f"Server {server_id} enabled"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/{server_id}/disable")
async def disable_server(server_id: str) -> Dict[str, Any]:
    """Disable and stop an MCP server"""
    registry = get_mcp_registry()
    if server_id not in registry.config:
        raise HTTPException(status_code=404, detail="Server not found")
        
    try:
        await registry.stop_server(server_id)
        registry.config[server_id]["enabled"] = False
        # TODO: Save config to disk
        return {"success": True, "message": f"Server {server_id} disabled"}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.post("/execute")
async def execute_tool(
    tool_name: str = Body(...),
    arguments: Dict[str, Any] = Body(...)
) -> Dict[str, Any]:
    """Execute an MCP tool"""
    registry = get_mcp_registry()
    try:
        result = await registry.execute_tool(tool_name, arguments)
        return {"success": True, "result": result}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================
# Daena MCP Server - Expose tools to external agents
# ============================================

@router.get("/server/tools")
async def list_daena_tools() -> Dict[str, Any]:
    """List tools exposed by Daena's MCP server"""
    try:
        from backend.services.mcp.mcp_server import get_mcp_server
        server = get_mcp_server()
        return {
            "tools": server.TOOLS,
            "count": len(server.TOOLS)
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/server/call")
async def call_daena_tool(
    tool_name: str = Body(..., description="Tool to call"),
    arguments: Dict[str, Any] = Body({}, description="Tool arguments"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> Dict[str, Any]:
    """
    Call a Daena tool exposed via MCP.
    
    External agents can use this to leverage Daena's capabilities.
    Requires API key for authentication (if configured).
    """
    try:
        from backend.services.mcp.mcp_server import get_mcp_server
        server = get_mcp_server()
        
        # Validate API key if server has keys configured
        client_id = "anonymous"
        if server.api_keys:
            if not x_api_key:
                return {"error": "API key required", "code": 401}
            client_id = server.validate_api_key(x_api_key)
            if not client_id:
                return {"error": "Invalid API key", "code": 401}
        
        # Execute the tool
        result = await server.handle_tool_call(tool_name, arguments, client_id)
        return result
        
    except Exception as e:
        return {"error": str(e)}


@router.get("/server/stats")
async def daena_server_stats() -> Dict[str, Any]:
    """Get usage statistics for Daena's MCP server"""
    try:
        from backend.services.mcp.mcp_server import get_mcp_server
        server = get_mcp_server()
        return server.get_usage_stats()
    except Exception as e:
        return {"error": str(e)}

