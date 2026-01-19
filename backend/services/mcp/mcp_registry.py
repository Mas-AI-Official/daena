"""
MCP Registry - Manages MCP server connections and tools
"""
import json
import logging
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from backend.services.mcp.mcp_client import MCPClient, MCPServerConfig

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config" / "mcp_servers.json"

class MCPRegistry:
    _instance = None
    
    def __init__(self):
        self.clients: Dict[str, MCPClient] = {}
        self.tools: Dict[str, str] = {}  # tool_name -> server_name
        self.config: Dict[str, Any] = {}
        
    @classmethod
    def get_instance(cls) -> "MCPRegistry":
        if cls._instance is None:
            cls._instance = MCPRegistry()
        return cls._instance
        
    async def initialize(self):
        """Load config and start enabled servers"""
        if not CONFIG_PATH.exists():
            logger.warning(f"MCP config not found at {CONFIG_PATH}")
            return
            
        try:
            with open(CONFIG_PATH, "r") as f:
                self.config = json.load(f)
                
            for server_id, cfg in self.config.items():
                if cfg.get("enabled", False):
                    await self.start_server(server_id, cfg)
                    
        except Exception as e:
            logger.error(f"Failed to initialize MCP registry: {e}")

    async def start_server(self, server_id: str, cfg: Dict[str, Any]):
        """Start a specific MCP server"""
        if server_id in self.clients:
            return
            
        config = MCPServerConfig(
            name=server_id,
            command=cfg.get("command", "npx"),
            args=cfg.get("args", []),
            env=cfg.get("env", {}),
            enabled=True
        )
        
        client = MCPClient(config)
        await client.start()
        
        if client.process:
            self.clients[server_id] = client
            
            # Register tools
            for tool in client.tools:
                self.tools[tool["name"]] = server_id
                
            logger.info(f"✅ Registered {len(client.tools)} tools from {server_id}")

    async def stop_server(self, server_id: str):
        """Stop an MCP server"""
        if server_id in self.clients:
            await self.clients[server_id].stop()
            del self.clients[server_id]
            
            # Remove tools
            self.tools = {t: s for t, s in self.tools.items() if s != server_id}
            logger.info(f"Stopped MCP server {server_id}")

    async def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get all available tools from all servers"""
        all_tools = []
        for client in self.clients.values():
            all_tools.extend(client.tools)
        return all_tools

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool on the appropriate server"""
        server_id = self.tools.get(tool_name)
        if not server_id:
            raise ValueError(f"Tool {tool_name} not found")
            
        client = self.clients.get(server_id)
        if not client:
            raise RuntimeError(f"Server {server_id} not connected")
            
        return await client.execute_tool(tool_name, arguments)

    async def shutdown(self):
        """Stop all servers"""
        for server_id in list(self.clients.keys()):
            await self.stop_server(server_id)

def get_mcp_registry() -> MCPRegistry:
    return MCPRegistry.get_instance()
