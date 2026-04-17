"""MCP auto-sync from installed CLI configs.

If the operator already configured an MCP server in Claude Code, Codex
CLI, or Gemini CLI, Daena should detect it and offer one-click import
rather than forcing the operator to install the same MCP ten times.
"""

from app.services.mcp_sync.detector import CLIMCPDetector, DetectedMCP

__all__ = ["CLIMCPDetector", "DetectedMCP"]
