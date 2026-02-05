from fastapi import APIRouter, HTTPException, Depends, Body
from typing import Dict, Any, List, Optional
from backend.services.mcp.mcp_server import get_mcp_server
from backend.routes.auth import get_current_user

router = APIRouter(prefix="/api/v1/mcp", tags=["Model Context Protocol"])

@router.get("/tools")
async def list_tools(current_user: dict = Depends(get_current_user)):
    """List available MCP tools."""
    server = get_mcp_server()
    return {"tools": server.TOOLS}

@router.post("/call/{tool_name}")
async def call_tool(
    tool_name: str, 
    arguments: Dict[str, Any] = Body(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Call an MCP tool via HTTP.
    
    Rate limiting is enforced per user ID.
    User role is checked implicitly by authentication requirement.
    """
    server = get_mcp_server()
    
    # Use authenticated user ID as client_id for rate limiting
    client_id = current_user.get("sub", "unknown_user")
    
    # Optional: Check if user has permission to use MCP
    # if current_user.get("role") not in ["admin", "founder", "agent"]:
    #     raise HTTPException(status_code=403, detail="Permission denied")
    
    result = await server.handle_tool_call(tool_name, arguments, client_id)
    return result

@router.get("/stats")
async def get_stats(current_user: dict = Depends(get_current_user)):
    """Get MCP usage statistics."""
    # Only admin/founder can see global stats
    if current_user.get("role") not in ["admin", "founder"]:
        raise HTTPException(status_code=403, detail="Permission denied")
        
    server = get_mcp_server()
    return server.get_usage_stats()
