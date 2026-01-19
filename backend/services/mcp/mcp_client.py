"""
MCP Client - Connects to MCP servers via stdio
"""
import asyncio
import json
import logging
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class MCPServerConfig:
    name: str
    command: str
    args: List[str]
    env: Dict[str, str]
    enabled: bool = True

class MCPClient:
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.process: Optional[asyncio.subprocess.Process] = None
        self.tools: List[Dict[str, Any]] = []
        self._request_id = 0
        self._pending_requests: Dict[int, asyncio.Future] = {}
        
    async def start(self):
        """Start the MCP server process"""
        if not self.config.enabled:
            return
            
        try:
            env = os.environ.copy()
            env.update(self.config.env)
            
            self.process = await asyncio.create_subprocess_exec(
                self.config.command,
                *self.config.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            # Start reading stdout in background
            asyncio.create_task(self._read_stdout())
            asyncio.create_task(self._read_stderr())
            
            # Initialize
            await self._initialize()
            
            # List tools
            await self._list_tools()
            
            logger.info(f"✅ MCP Server {self.config.name} started")
            
        except Exception as e:
            logger.error(f"Failed to start MCP server {self.config.name}: {e}")
            self.process = None

    async def stop(self):
        """Stop the MCP server process"""
        if self.process:
            try:
                self.process.terminate()
                await self.process.wait()
            except Exception as e:
                logger.warning(f"Error stopping MCP server {self.config.name}: {e}")
            finally:
                self.process = None

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a tool on this server"""
        if not self.process:
            raise RuntimeError(f"MCP server {self.config.name} not running")
            
        return await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments
        })

    async def _initialize(self):
        """Send initialize request"""
        response = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {}
            },
            "clientInfo": {
                "name": "Daena",
                "version": "1.0.0"
            }
        })
        
        # Send initialized notification
        await self._send_notification("notifications/initialized")
        return response

    async def _list_tools(self):
        """List available tools"""
        response = await self._send_request("tools/list", {})
        self.tools = response.get("tools", [])
        logger.info(f"🛠️  Loaded {len(self.tools)} tools from {self.config.name}")

    async def _send_request(self, method: str, params: Dict[str, Any]) -> Any:
        """Send JSON-RPC request"""
        if not self.process or not self.process.stdin:
            raise RuntimeError("Process not ready")
            
        self._request_id += 1
        req_id = self._request_id
        
        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params
        }
        
        future = asyncio.Future()
        self._pending_requests[req_id] = future
        
        try:
            data = json.dumps(request) + "\n"
            self.process.stdin.write(data.encode())
            await self.process.stdin.drain()
            
            # Wait for response with timeout
            return await asyncio.wait_for(future, timeout=30.0)
        finally:
            self._pending_requests.pop(req_id, None)

    async def _send_notification(self, method: str, params: Dict[str, Any] = None):
        """Send JSON-RPC notification"""
        if not self.process or not self.process.stdin:
            return
            
        request = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params or {}
        }
        
        data = json.dumps(request) + "\n"
        self.process.stdin.write(data.encode())
        await self.process.stdin.drain()

    async def _read_stdout(self):
        """Read stdout and handle JSON-RPC messages"""
        if not self.process or not self.process.stdout:
            return
            
        while True:
            try:
                line = await self.process.stdout.readline()
                if not line:
                    break
                    
                line_str = line.decode().strip()
                if not line_str:
                    continue
                    
                try:
                    message = json.loads(line_str)
                    
                    # Handle response
                    if "id" in message and message["id"] in self._pending_requests:
                        future = self._pending_requests[message["id"]]
                        if "error" in message:
                            future.set_exception(RuntimeError(message["error"]["message"]))
                        else:
                            future.set_result(message.get("result"))
                            
                    # Handle notifications (logging, etc)
                    elif "method" in message:
                        # TODO: Handle server notifications
                        pass
                        
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from {self.config.name}: {line_str}")
                    
            except Exception as e:
                logger.error(f"Error reading stdout from {self.config.name}: {e}")
                break

    async def _read_stderr(self):
        """Read stderr and log it"""
        if not self.process or not self.process.stderr:
            return
            
        while True:
            try:
                line = await self.process.stderr.readline()
                if not line:
                    break
                logger.warning(f"[{self.config.name}] {line.decode().strip()}")
            except Exception as e:
                logger.error(f"Error reading stderr from {self.config.name}: {e}")
                break
