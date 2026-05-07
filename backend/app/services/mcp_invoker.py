"""MCP invoker -- speaks the MCP protocol to installed stdio servers.

Bridges the ``mcp_bootstrap`` registry to actual tool execution by
spawning each MCP server on demand, completing the MCP handshake,
and routing ``tools/list`` + ``tools/call`` through the official
Python MCP SDK (``mcp.ClientSession``).

Two shapes of invoker:

  * ``list_server_tools(server_key)`` -- returns the tool
    descriptors the MCP server exposes. Used by the orchestrator
    at turn start (so the LLM knows what's available) and by
    Daena's plugin-admin surface (so the founder can see what
    each plugin can actually do).

  * ``call_server_tool(server_key, tool_name, arguments)`` --
    executes a specific tool with the given arguments.

Each invocation opens a short-lived stdio session (spawn, handshake,
call, close). This keeps the implementation simple -- no long-lived
subprocess management, no request-multiplexing state. The cost is
spawn latency per call, measured in ~100-400 ms for typical MCP
servers. Acceptable for v1; can evolve to persistent sessions if
frequency warrants.

Everything is fail-safe: a timeout / spawn-failure / protocol error
is returned as an error dict, never as an uncaught exception. Upper
layers (chat orchestrator, plugin-admin agent) decide how to
surface the failure.
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.core.logging import get_logger
from app.services.mcp_bootstrap import get_installed_mcp

logger = get_logger(__name__)


# Each stdio session is bounded by this timeout. Covers spawn +
# handshake + tool call end-to-end so a broken MCP cannot hang
# the chat turn indefinitely.
_DEFAULT_TIMEOUT_SECONDS: float = 20.0


def _safe_exception_message(exc: BaseException, server_key: str) -> str:
    """Return an operator-readable MCP failure without raw TaskGroup noise."""
    if isinstance(exc, BaseExceptionGroup):
        parts = [
            _safe_exception_message(child, server_key)
            for child in exc.exceptions
            if child is not None
        ]
        unique: list[str] = []
        for part in parts:
            if part and part not in unique:
                unique.append(part)
        if unique:
            return "; ".join(unique)
        return f"{server_key} MCP process failed during startup."

    text = str(exc).strip()
    if (
        not text
        or "unhandled errors in a TaskGroup" in text
        or text.lower() == "connection closed"
    ):
        return (
            f"{server_key} MCP process exited before the MCP handshake completed. "
            "Check its command, args, required env vars, and package install."
        )
    return text


def _build_params(server_key: str) -> StdioServerParameters | None:
    """Resolve the subprocess argv for an installed MCP."""
    entry = get_installed_mcp(server_key)
    if entry is None:
        return None
    return StdioServerParameters(
        command=entry.command,
        args=list(entry.args),
    )


async def list_server_tools(
    server_key: str,
    *,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Query an installed MCP for its tool catalog.

    Returns ``{"success": True, "tools": [...]}`` on success, or
    ``{"success": False, "error": "..."}`` on any failure.
    """
    params = _build_params(server_key)
    if params is None:
        return {
            "success": False,
            "error": f"{server_key} not in bootstrap registry",
        }

    async def _inner() -> dict[str, Any]:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.list_tools()
                tools = [
                    {
                        "name": t.name,
                        "description": t.description or "",
                        "input_schema": (
                            t.inputSchema
                            if isinstance(t.inputSchema, dict)
                            else {}
                        ),
                    }
                    for t in result.tools
                ]
                return {"success": True, "tools": tools}

    try:
        return await asyncio.wait_for(_inner(), timeout=timeout)
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": f"{server_key} did not respond to tools/list in {timeout}s",
        }
    except Exception as exc:  # pragma: no cover - fail-safe
        message = _safe_exception_message(exc, server_key)
        logger.warning(
            "mcp_invoker.list_tools_failed",
            server_key=server_key,
            error=message,
        )
        return {"success": False, "error": message}


async def call_server_tool(
    server_key: str,
    tool_name: str,
    arguments: dict[str, Any] | None = None,
    *,
    timeout: float = _DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Invoke a specific MCP tool on an installed server."""
    params = _build_params(server_key)
    if params is None:
        return {
            "success": False,
            "error": f"{server_key} not in bootstrap registry",
        }

    args = arguments or {}

    async def _inner() -> dict[str, Any]:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)
                # result.content is a list of content parts
                # (TextContent / ImageContent / ...). We flatten to
                # a JSON-friendly shape.
                content_out: list[dict[str, Any]] = []
                for part in result.content or []:
                    part_dict: dict[str, Any] = {
                        "type": getattr(part, "type", "unknown"),
                    }
                    if hasattr(part, "text"):
                        part_dict["text"] = part.text
                    content_out.append(part_dict)
                return {
                    "success": not bool(getattr(result, "isError", False)),
                    "content": content_out,
                    "is_error": bool(getattr(result, "isError", False)),
                }

    try:
        return await asyncio.wait_for(_inner(), timeout=timeout)
    except asyncio.TimeoutError:
        return {
            "success": False,
            "error": f"{server_key}.{tool_name} timed out after {timeout}s",
        }
    except Exception as exc:
        message = _safe_exception_message(exc, server_key)
        logger.warning(
            "mcp_invoker.call_tool_failed",
            server_key=server_key,
            tool_name=tool_name,
            error=message,
        )
        return {"success": False, "error": message}
