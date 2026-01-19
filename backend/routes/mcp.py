"""
MCP API Routes - Manage MCP servers and tools
"""
from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any, List
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
