"""
MCP Client for Daena AI VP

Enables Daena to connect to external AI assistants via the Model Context Protocol.
Supports connecting to Antigravity (Gemini) and other MCP-compatible servers.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging
import httpx

logger = logging.getLogger(__name__)


@dataclass 
class MCPConnection:
    """Represents a connection to an MCP server."""
    name: str
    url: str
    connected: bool = False
    capabilities: List[str] = field(default_factory=list)
    last_ping: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


# Active MCP connections
_mcp_connections: Dict[str, MCPConnection] = {}


# Pre-configured MCP servers
MCP_SERVERS = {
    "antigravity": {
        "name": "Antigravity (Gemini)",
        "url": "http://localhost:3000/mcp",  # Default MCP port
        "description": "Gemini-powered AI assistant via Cursor IDE",
        "capabilities": ["code_edit", "file_read", "search", "browser"]
    },
    "ollama": {
        "name": "Local Ollama",
        "url": "http://localhost:11434",
        "description": "Local LLM via Ollama",
        "capabilities": ["chat", "generate"]
    }
}


async def discover_mcp_servers() -> Dict[str, Any]:
    """
    Discover available MCP servers on the network.
    """
    discovered = []
    
    # Check pre-configured servers
    for server_id, config in MCP_SERVERS.items():
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                # Different endpoints for different servers
                if server_id == "ollama":
                    response = await client.get(f"{config['url']}/api/tags")
                else:
                    response = await client.get(f"{config['url']}/health")
                
                if response.status_code < 400:
                    discovered.append({
                        "id": server_id,
                        "name": config["name"],
                        "url": config["url"],
                        "available": True,
                        "capabilities": config["capabilities"]
                    })
        except Exception as e:
            logger.debug(f"Server {server_id} not available: {e}")
            discovered.append({
                "id": server_id,
                "name": config["name"],
                "url": config["url"],
                "available": False,
                "error": str(e)
            })
    
    return {
        "success": True,
        "servers": discovered,
        "discovered_at": datetime.now().isoformat()
    }


async def connect_to_mcp(server_id: str, custom_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Connect to an MCP server.
    
    Args:
        server_id: Pre-configured server ID or custom name
        custom_url: Optional custom URL for non-configured servers
    """
    global _mcp_connections
    
    # Get server config
    if server_id in MCP_SERVERS:
        config = MCP_SERVERS[server_id]
        url = custom_url or config["url"]
        name = config["name"]
        capabilities = config["capabilities"]
    else:
        if not custom_url:
            return {"success": False, "error": f"Unknown server: {server_id}. Provide custom_url."}
        url = custom_url
        name = server_id
        capabilities = []
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Try to handshake with the server
            if server_id == "ollama":
                response = await client.get(f"{url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    capabilities = ["chat", "generate"]
                    # Add model names as metadata
                    models = [m.get("name") for m in data.get("models", [])]
                    metadata = {"models": models}
            else:
                # Standard MCP handshake
                response = await client.post(
                    f"{url}/initialize",
                    json={"client": "daena", "version": "1.0"}
                )
                metadata = response.json() if response.status_code == 200 else {}
        
        # Create connection
        connection = MCPConnection(
            name=name,
            url=url,
            connected=True,
            capabilities=capabilities,
            last_ping=datetime.now(),
            metadata=metadata if 'metadata' in dir() else {}
        )
        
        _mcp_connections[server_id] = connection
        
        return {
            "success": True,
            "server_id": server_id,
            "name": name,
            "url": url,
            "capabilities": capabilities,
            "connected": True
        }
        
    except Exception as e:
        logger.error(f"Failed to connect to {server_id}: {e}")
        return {"success": False, "error": str(e), "server_id": server_id}


async def disconnect_mcp(server_id: str) -> Dict[str, Any]:
    """Disconnect from an MCP server."""
    global _mcp_connections
    
    if server_id not in _mcp_connections:
        return {"success": False, "error": f"Not connected to {server_id}"}
    
    del _mcp_connections[server_id]
    return {"success": True, "server_id": server_id, "disconnected": True}


def list_connections() -> Dict[str, Any]:
    """List all active MCP connections."""
    connections = []
    for server_id, conn in _mcp_connections.items():
        connections.append({
            "id": server_id,
            "name": conn.name,
            "url": conn.url,
            "connected": conn.connected,
            "capabilities": conn.capabilities,
            "last_ping": conn.last_ping.isoformat() if conn.last_ping else None
        })
    
    return {
        "success": True,
        "connections": connections,
        "count": len(connections)
    }


async def send_to_mcp(
    server_id: str, 
    action: str, 
    payload: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Send a request to an MCP server.
    
    Args:
        server_id: Target server ID
        action: Action to execute (chat, generate, execute_tool, etc.)
        payload: Action-specific payload
    """
    if server_id not in _mcp_connections:
        # Try to auto-connect
        connect_result = await connect_to_mcp(server_id)
        if not connect_result.get("success"):
            return connect_result
    
    connection = _mcp_connections[server_id]
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            if server_id == "ollama":
                # Ollama-specific endpoints
                if action == "chat":
                    response = await client.post(
                        f"{connection.url}/api/chat",
                        json={
                            "model": payload.get("model", "qwen2.5:14b-instruct"),
                            "messages": payload.get("messages", []),
                            "stream": False
                        }
                    )
                elif action == "generate":
                    response = await client.post(
                        f"{connection.url}/api/generate",
                        json={
                            "model": payload.get("model", "qwen2.5:14b-instruct"),
                            "prompt": payload.get("prompt", ""),
                            "stream": False
                        }
                    )
                else:
                    return {"success": False, "error": f"Unknown action for Ollama: {action}"}
            else:
                # Standard MCP protocol
                response = await client.post(
                    f"{connection.url}/execute",
                    json={"action": action, **payload}
                )
            
            connection.last_ping = datetime.now()
            
            if response.status_code == 200:
                return {"success": True, "result": response.json()}
            else:
                return {"success": False, "error": f"Server returned {response.status_code}"}
                
    except Exception as e:
        logger.error(f"MCP request failed: {e}")
        return {"success": False, "error": str(e)}


async def ask_antigravity(question: str, context: Optional[str] = None) -> Dict[str, Any]:
    """
    Send a question to Antigravity (Gemini via MCP).
    
    This is a convenience function for quick queries.
    Falls back to local Ollama if Antigravity is unavailable.
    """
    # Try Antigravity first
    try:
        result = await send_to_mcp("antigravity", "chat", {
            "messages": [
                {"role": "system", "content": context or "You are a helpful AI assistant."},
                {"role": "user", "content": question}
            ]
        })
        if result.get("success"):
            return result
    except:
        pass
    
    # Fallback to Ollama
    try:
        result = await send_to_mcp("ollama", "chat", {
            "messages": [
                {"role": "system", "content": context or "You are a helpful AI assistant."},
                {"role": "user", "content": question}
            ]
        })
        return result
    except Exception as e:
        return {"success": False, "error": f"No AI assistants available: {e}"}


# Convenience function for Daena
async def daena_mcp(command: str) -> Dict[str, Any]:
    """
    Parse MCP-related commands.
    
    Examples:
        "discover servers"
        "connect to ollama"
        "list connections"
        "ask ollama what is python?"
    """
    command = command.lower().strip()
    
    if "discover" in command or "find servers" in command:
        return await discover_mcp_servers()
    
    elif command.startswith("connect"):
        parts = command.split()
        server_id = parts[-1] if len(parts) > 1 else "ollama"
        return await connect_to_mcp(server_id)
    
    elif "disconnect" in command:
        parts = command.split()
        server_id = parts[-1] if len(parts) > 1 else "ollama"
        return await disconnect_mcp(server_id)
    
    elif command in ["list", "connections", "list connections", "status"]:
        return list_connections()
    
    elif command.startswith("ask"):
        parts = command.split(" ", 2)
        if len(parts) >= 3:
            server_id = parts[1]
            question = parts[2]
            return await send_to_mcp(server_id, "chat", {
                "messages": [{"role": "user", "content": question}]
            })
        else:
            return {"success": False, "error": "Usage: ask <server> <question>"}
    
    else:
        return {
            "success": False,
            "error": "Unknown command. Try: discover, connect <server>, list, ask <server> <question>"
        }
