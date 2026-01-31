"""
MCP (Model Context Protocol) Adapter for Daena
==============================================

Translates MCP tool calls to Daena's internal format and vice versa.
This allows Daena to plug into the growing MCP-compatible ecosystem.

MCP Spec Reference: https://modelcontextprotocol.io/
"""

import json
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class MCPToolType(Enum):
    """Types of MCP tools."""
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    QUERY = "query"


@dataclass
class MCPTool:
    """Represents an MCP-compatible tool definition."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    tool_type: MCPToolType = MCPToolType.READ
    requires_approval: bool = False
    daena_handler: Optional[str] = None  # Maps to Daena's internal handler
    
    def to_mcp_format(self) -> Dict[str, Any]:
        """Convert to MCP tool definition format."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema
        }


@dataclass
class MCPToolCall:
    """Represents an incoming MCP tool call."""
    id: str
    name: str
    arguments: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MCPToolResult:
    """Represents the result of an MCP tool call."""
    call_id: str
    content: List[Dict[str, Any]]
    is_error: bool = False
    
    def to_mcp_format(self) -> Dict[str, Any]:
        """Convert to MCP result format."""
        return {
            "type": "tool_result",
            "tool_use_id": self.call_id,
            "content": self.content,
            "is_error": self.is_error
        }


class MCPAdapter:
    """
    Translates between MCP protocol and Daena's internal tool system.
    
    This adapter allows:
    1. Daena to receive MCP-formatted tool calls and execute them
    2. Daena to expose its tools AS an MCP server
    """
    
    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}
        self.handlers: Dict[str, Callable] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register Daena's core tools as MCP-compatible."""
        
        # File system tools
        self.register_tool(MCPTool(
            name="filesystem_read",
            description="Read a file from the workspace. Returns file contents.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file to read (relative to workspace)"
                    }
                },
                "required": ["path"]
            },
            tool_type=MCPToolType.READ,
            daena_handler="backend.tools.filesystem.read_file"
        ))
        
        self.register_tool(MCPTool(
            name="filesystem_write",
            description="Write content to a file in the workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to write to"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write"
                    }
                },
                "required": ["path", "content"]
            },
            tool_type=MCPToolType.WRITE,
            requires_approval=True,
            daena_handler="backend.tools.filesystem.write_file"
        ))
        
        # Search tools
        self.register_tool(MCPTool(
            name="workspace_search",
            description="Search for files or content in the workspace.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "type": {
                        "type": "string",
                        "enum": ["filename", "content", "semantic"],
                        "default": "content"
                    }
                },
                "required": ["query"]
            },
            tool_type=MCPToolType.QUERY,
            daena_handler="backend.tools.search.workspace_search"
        ))
        
        # Shell execution
        self.register_tool(MCPTool(
            name="shell_exec",
            description="Execute a shell command on the local system.",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Command to execute"
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory (optional)"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds",
                        "default": 60
                    }
                },
                "required": ["command"]
            },
            tool_type=MCPToolType.EXECUTE,
            requires_approval=True,
            daena_handler="backend.tools.shell.execute"
        ))
        
        # Web search
        self.register_tool(MCPTool(
            name="web_search",
            description="Search the web for information.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query"
                    },
                    "num_results": {
                        "type": "integer",
                        "default": 5
                    }
                },
                "required": ["query"]
            },
            tool_type=MCPToolType.QUERY,
            daena_handler="backend.tools.search.web_search"
        ))
        
        # DeFi scanning
        self.register_tool(MCPTool(
            name="defi_scan",
            description="Scan a smart contract for security vulnerabilities.",
            input_schema={
                "type": "object",
                "properties": {
                    "contract_path": {
                        "type": "string",
                        "description": "Path to Solidity contract file"
                    },
                    "tools": {
                        "type": "array",
                        "items": {"type": "string"},
                        "default": ["slither", "mythril"]
                    }
                },
                "required": ["contract_path"]
            },
            tool_type=MCPToolType.EXECUTE,
            daena_handler="backend.services.defi_scanner.scan"
        ))
        
        # Council consultation
        self.register_tool(MCPTool(
            name="council_consult",
            description="Consult Daena's council of experts on a question.",
            input_schema={
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Question to ask the council"
                    },
                    "domains": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Council domains to consult (finance, tech, legal, etc.)"
                    },
                    "urgency": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "default": "medium"
                    }
                },
                "required": ["question"]
            },
            tool_type=MCPToolType.QUERY,
            daena_handler="backend.council.consult"
        ))
    
    def register_tool(self, tool: MCPTool, handler: Optional[Callable] = None):
        """Register a tool with the adapter."""
        self.tools[tool.name] = tool
        if handler:
            self.handlers[tool.name] = handler
        logger.info(f"Registered MCP tool: {tool.name}")
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools in MCP format."""
        return [tool.to_mcp_format() for tool in self.tools.values()]
    
    def parse_tool_call(self, mcp_request: Dict[str, Any]) -> MCPToolCall:
        """Parse an incoming MCP tool call request."""
        return MCPToolCall(
            id=mcp_request.get("id", str(datetime.now().timestamp())),
            name=mcp_request.get("name", ""),
            arguments=mcp_request.get("input", {})
        )
    
    async def execute_tool(self, call: MCPToolCall) -> MCPToolResult:
        """Execute an MCP tool call using Daena's internal handlers."""
        
        if call.name not in self.tools:
            return MCPToolResult(
                call_id=call.id,
                content=[{"type": "text", "text": f"Unknown tool: {call.name}"}],
                is_error=True
            )
        
        tool = self.tools[call.name]
        
        # Check if tool requires approval
        if tool.requires_approval:
            # In a real implementation, this would trigger approval flow
            logger.warning(f"Tool {call.name} requires approval (auto-approved for demo)")
        
        try:
            # Try to find and execute the handler
            if call.name in self.handlers:
                handler = self.handlers[call.name]
                result = await handler(**call.arguments) if asyncio.iscoroutinefunction(handler) else handler(**call.arguments)
            elif tool.daena_handler:
                # Dynamic import of Daena handler
                result = await self._call_daena_handler(tool.daena_handler, call.arguments)
            else:
                result = f"Tool {call.name} has no handler (stub response)"
            
            return MCPToolResult(
                call_id=call.id,
                content=[{"type": "text", "text": str(result)}]
            )
            
        except Exception as e:
            logger.error(f"Tool execution failed: {e}")
            return MCPToolResult(
                call_id=call.id,
                content=[{"type": "text", "text": f"Execution error: {str(e)}"}],
                is_error=True
            )
    
    async def _call_daena_handler(self, handler_path: str, arguments: Dict[str, Any]) -> Any:
        """Dynamically call a Daena handler by its module path."""
        try:
            parts = handler_path.rsplit(".", 1)
            if len(parts) != 2:
                return f"Invalid handler path: {handler_path}"
            
            module_path, func_name = parts
            module = __import__(module_path, fromlist=[func_name])
            handler = getattr(module, func_name)
            
            if asyncio.iscoroutinefunction(handler):
                return await handler(**arguments)
            return handler(**arguments)
            
        except ImportError as e:
            return f"Handler not found: {handler_path} ({e})"
        except AttributeError as e:
            return f"Function not found in handler: {e}"
    
    def translate_to_mcp(self, daena_response: Dict[str, Any]) -> Dict[str, Any]:
        """Translate a Daena response to MCP format."""
        return {
            "jsonrpc": "2.0",
            "result": daena_response,
            "id": daena_response.get("request_id", 1)
        }
    
    def translate_from_mcp(self, mcp_request: Dict[str, Any]) -> Dict[str, Any]:
        """Translate an MCP request to Daena's internal format."""
        method = mcp_request.get("method", "")
        params = mcp_request.get("params", {})
        
        if method == "tools/list":
            return {"action": "list_tools"}
        elif method == "tools/call":
            return {
                "action": "execute_tool",
                "tool_name": params.get("name"),
                "arguments": params.get("arguments", {})
            }
        elif method == "resources/list":
            return {"action": "list_resources"}
        elif method == "resources/read":
            return {
                "action": "read_resource",
                "uri": params.get("uri")
            }
        else:
            return {"action": "unknown", "method": method}


# Async context manager import
import asyncio

# Singleton instance
mcp_adapter = MCPAdapter()


def get_mcp_adapter() -> MCPAdapter:
    """Get the MCP adapter singleton."""
    return mcp_adapter
