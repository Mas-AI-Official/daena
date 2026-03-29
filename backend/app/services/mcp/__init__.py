"""Daena MCP Server: exposes Daena capabilities via MCP protocol.

External tools (Claude Code, Codex, etc.) can connect TO Daena
for governance evaluation, memory queries, skill retrieval, and
audit logging. This makes Daena the governance layer for external
AI tool execution.
"""

from app.services.mcp.server import DaenaMCPServer

__all__ = ["DaenaMCPServer"]
