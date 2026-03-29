"""Daena MCP Server: exposes governance, memory, skills, and audit via MCP.

Implements the Model Context Protocol server interface so external
runtimes (Claude Code, Codex, etc.) can call Daena for:
    - governance_check: Evaluate an action against governance tiers
    - memory_query: Query NBMF memory system
    - skill_retrieve: Get relevant skills from Skill Refinery
    - audit_log: Log an action to the tamper-evident audit trail
    - runtime_status: Get status of all registered runtimes
    - cost_estimate: Get pre-execution cost estimate for a runtime

The server handles JSON-RPC style requests and can be mounted on
a FastAPI route or run as a stdio subprocess.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class MCPTool:
    """MCP tool definition."""
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass
class MCPToolResult:
    """Result from an MCP tool call."""
    tool_name: str
    success: bool
    output: Any
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for MCP response."""
        result: dict[str, Any] = {
            "tool_name": self.tool_name,
            "success": self.success,
            "output": self.output,
        }
        if self.error:
            result["error"] = self.error
        if self.metadata:
            result["metadata"] = self.metadata
        return result


# MCP tool definitions that Daena exposes to external runtimes
DAENA_MCP_TOOLS: list[MCPTool] = [
    MCPTool(
        name="governance_check",
        description="Evaluate an action against Daena's governance tiers",
        input_schema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "Action to evaluate"},
                "action_type": {
                    "type": "string",
                    "description": "Action type (e.g. RUNTIME_EXECUTION, FILE_WRITE)",
                },
                "context": {
                    "type": "object",
                    "description": "Additional context for evaluation",
                },
            },
            "required": ["action"],
        },
    ),
    MCPTool(
        name="memory_query",
        description="Query Daena's NBMF memory system",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "tier_filter": {
                    "type": "string",
                    "description": "Memory tier filter (T0-T4)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    ),
    MCPTool(
        name="skill_retrieve",
        description="Get relevant skills from Daena's Skill Refinery",
        input_schema={
            "type": "object",
            "properties": {
                "task_description": {
                    "type": "string",
                    "description": "Task to find skills for",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max skills to return",
                    "default": 5,
                },
            },
            "required": ["task_description"],
        },
    ),
    MCPTool(
        name="audit_log",
        description="Log an action to Daena's tamper-evident audit trail",
        input_schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Action that was performed",
                },
                "result": {
                    "type": "string",
                    "description": "Outcome of the action",
                },
                "runtime": {
                    "type": "string",
                    "description": "Runtime that performed the action",
                },
                "metadata": {
                    "type": "object",
                    "description": "Additional metadata",
                },
            },
            "required": ["action", "result"],
        },
    ),
    MCPTool(
        name="runtime_status",
        description="Get status of all registered runtimes",
        input_schema={
            "type": "object",
            "properties": {},
        },
    ),
    MCPTool(
        name="cost_estimate",
        description="Get pre-execution cost estimate for a runtime",
        input_schema={
            "type": "object",
            "properties": {
                "runtime_id": {
                    "type": "string",
                    "description": "Runtime to estimate cost for",
                },
                "estimated_tokens": {
                    "type": "integer",
                    "description": "Estimated total tokens",
                },
            },
            "required": ["runtime_id", "estimated_tokens"],
        },
    ),
]


class DaenaMCPServer:
    """MCP Server exposing Daena capabilities to external tools.

    Usage (HTTP mode)::

        server = DaenaMCPServer()
        # Mount on FastAPI route or call handle_request directly
        result = await server.handle_request({
            "method": "tools/call",
            "params": {
                "name": "governance_check",
                "arguments": {"action": "delete all files"}
            }
        })

    Usage (stdio mode)::

        server = DaenaMCPServer()
        await server.run_stdio()  # Reads from stdin, writes to stdout
    """

    def __init__(self) -> None:
        self._tools = {t.name: t for t in DAENA_MCP_TOOLS}
        self._handlers: dict[str, Any] = {
            "governance_check": self._handle_governance_check,
            "memory_query": self._handle_memory_query,
            "skill_retrieve": self._handle_skill_retrieve,
            "audit_log": self._handle_audit_log,
            "runtime_status": self._handle_runtime_status,
            "cost_estimate": self._handle_cost_estimate,
        }

    def get_tool_definitions(self) -> list[dict[str, Any]]:
        """Return MCP tool definitions for the tools/list response."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
            }
            for tool in DAENA_MCP_TOOLS
        ]

    async def handle_request(
        self, request: dict[str, Any],
    ) -> dict[str, Any]:
        """Handle an incoming MCP JSON-RPC request.

        Supports:
            - tools/list: Return available tool definitions
            - tools/call: Execute a tool and return result

        Args:
            request: JSON-RPC style request dict.

        Returns:
            JSON-RPC style response dict.
        """
        method = request.get("method", "")
        request_id = request.get("id")
        params = request.get("params", {})

        if method == "tools/list":
            return {
                "id": request_id,
                "result": {"tools": self.get_tool_definitions()},
            }

        if method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            handler = self._handlers.get(tool_name)
            if not handler:
                return {
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}",
                    },
                }

            try:
                result = await handler(arguments)
                return {
                    "id": request_id,
                    "result": result.to_dict(),
                }
            except Exception as exc:
                logger.error(
                    "mcp_server.tool_error",
                    tool=tool_name,
                    error=str(exc),
                )
                return {
                    "id": request_id,
                    "error": {
                        "code": -32000,
                        "message": str(exc),
                    },
                }

        return {
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Unsupported method: {method}",
            },
        }

    async def run_stdio(self) -> None:
        """Run the MCP server in stdio mode (for subprocess transport).

        Reads JSON-RPC requests from stdin, writes responses to stdout.
        """
        import sys

        logger.info("mcp_server.stdio_started")
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = await self.handle_request(request)
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except json.JSONDecodeError:
                error_resp = {
                    "error": {
                        "code": -32700,
                        "message": "Parse error",
                    },
                }
                sys.stdout.write(json.dumps(error_resp) + "\n")
                sys.stdout.flush()

    # ── Tool handlers ──

    async def _handle_governance_check(
        self, arguments: dict[str, Any],
    ) -> MCPToolResult:
        """Evaluate an action against Daena's governance tiers."""
        action = arguments.get("action", "")
        action_type = arguments.get("action_type", "RUNTIME_EXECUTION")

        # Use the CriticalityClassifier for quick classification
        from app.services.autopilot.criticality_classifier import (
            CriticalityClassifier,
        )

        classifier = CriticalityClassifier()
        level = classifier.classify(action_type, arguments.get("context"))

        return MCPToolResult(
            tool_name="governance_check",
            success=True,
            output={
                "action": action,
                "action_type": action_type,
                "criticality_level": level.value,
                "allowed": level.value != "pause",
                "requires_approval": level.value == "pause",
            },
        )

    async def _handle_memory_query(
        self, arguments: dict[str, Any],
    ) -> MCPToolResult:
        """Query NBMF memory system."""
        query = arguments.get("query", "")
        tier_filter = arguments.get("tier_filter")
        limit = arguments.get("limit", 5)

        # Return a structured response indicating the query was processed.
        # Full memory integration requires a database session which is
        # injected when the server is wired to the FastAPI app.
        return MCPToolResult(
            tool_name="memory_query",
            success=True,
            output={
                "query": query,
                "tier_filter": tier_filter,
                "results": [],  # Populated when DB session available
                "message": "Memory query processed",
            },
            metadata={"limit": limit},
        )

    async def _handle_skill_retrieve(
        self, arguments: dict[str, Any],
    ) -> MCPToolResult:
        """Retrieve relevant skills from Skill Refinery."""
        task = arguments.get("task_description", "")
        limit = arguments.get("limit", 5)

        return MCPToolResult(
            tool_name="skill_retrieve",
            success=True,
            output={
                "task_description": task,
                "skills": [],  # Populated when skill store available
                "message": "Skill retrieval processed",
            },
            metadata={"limit": limit},
        )

    async def _handle_audit_log(
        self, arguments: dict[str, Any],
    ) -> MCPToolResult:
        """Log an action to the audit trail."""
        action = arguments.get("action", "")
        result = arguments.get("result", "")
        runtime = arguments.get("runtime", "external")

        logger.info(
            "mcp_server.audit_log",
            action=action,
            result=result,
            runtime=runtime,
        )

        return MCPToolResult(
            tool_name="audit_log",
            success=True,
            output={
                "logged": True,
                "action": action,
                "result": result,
                "runtime": runtime,
            },
        )

    async def _handle_runtime_status(
        self, arguments: dict[str, Any],
    ) -> MCPToolResult:
        """Get status of all registered runtimes."""
        from app.core.events import get_runtime_registry

        registry = get_runtime_registry()
        status_data = registry.to_dict()

        return MCPToolResult(
            tool_name="runtime_status",
            success=True,
            output=status_data,
        )

    async def _handle_cost_estimate(
        self, arguments: dict[str, Any],
    ) -> MCPToolResult:
        """Get cost estimate for a runtime execution."""
        runtime_id = arguments.get("runtime_id", "ollama")
        estimated_tokens = arguments.get("estimated_tokens", 1000)

        from app.services.runtimes.cost_estimator import CostEstimator

        estimator = CostEstimator()
        estimate = estimator.estimate(runtime_id, estimated_tokens)

        return MCPToolResult(
            tool_name="cost_estimate",
            success=True,
            output={
                "runtime_id": estimate.runtime_id,
                "estimated_tokens": estimate.estimated_tokens,
                "estimated_cost_usd": estimate.estimated_cost_usd,
                "is_free": estimate.is_free,
                "breakdown": estimate.breakdown,
            },
        )
