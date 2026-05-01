"""Compatibility shim (Phase 4b PR 2, ADR-002 D-012).

The MCP runtime adapter was renamed to ``mcp_bridge_runtime_adapter`` so
the file's role is unambiguous: it is a Runtime Adapter for an MCP
server, not the (separate) "mcp_bridge" service used for Claude Code
orchestration of the local LLM.

Old imports of ``app.services.runtimes.adapters.mcp_bridge`` continue
to work via this re-export. Remove this shim after the soak window
when no in-tree references exist.
"""

from __future__ import annotations

from app.services.runtimes.adapters.mcp_bridge_runtime_adapter import (
    MCPBridgeAdapter,
)

__all__ = ["MCPBridgeAdapter"]
