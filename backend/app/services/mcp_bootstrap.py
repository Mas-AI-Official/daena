"""MCP bootstrap -- Option A wiring.

On app startup, reads the Claude Desktop MCP config and instantiates
an ``MCPBridgeAdapter`` for every stdio-command entry. The resulting
adapters are held in a process-wide registry that any caller
(chat_orchestrator, Daena's plugin-admin tools, the UI's /extensions
list) can query to see which MCPs are actually installed + spawnable.

This is the missing link between:

  * ``POST /connections/extensions/install`` -- writes
    ``claude_desktop_config.json``
  * Chat tool invocation -- previously unable to reach stdio MCPs

Design rules:

  * **Fail-safe startup**: a broken MCP entry must never take the
    whole server down. Each adapter init is wrapped; failures log
    ``mcp_bootstrap.adapter_failed`` and continue.
  * **No process spawn during bootstrap**: we only INSTANTIATE
    adapters; the actual process spawn happens on first
    ``execute`` call. This keeps startup fast.
  * **Re-entrant**: ``bootstrap_installed_mcps()`` is idempotent --
    subsequent calls refresh the registry, so the Daena
    plugin-admin "refresh" action can trigger it without restart.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.runtimes.adapters.mcp_bridge_runtime_adapter import MCPBridgeAdapter

logger = get_logger(__name__)


_DESKTOP_CONFIG = (
    Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
)


@dataclass
class InstalledMCP:
    """One MCP server discovered from the desktop config."""

    server_key: str           # Key inside mcpServers
    display_name: str         # From metadata.name, falls back to server_key
    description: str          # From metadata.description
    command: str              # e.g. "npx"
    args: list[str]           # Remainder of the exec chain
    adapter: MCPBridgeAdapter
    package: str | None = None  # Inferred from args (-y <pkg>)


# Process-wide registry. Keys are server_key.
_REGISTRY: dict[str, InstalledMCP] = {}
_REGISTRY_LOCK = asyncio.Lock()


async def bootstrap_installed_mcps() -> dict[str, InstalledMCP]:
    """Read ``claude_desktop_config.json`` and populate the registry.

    Returns the updated registry. Safe to call repeatedly -- replaces
    previous entries atomically so a re-scan after a new install
    picks up the change without restart.
    """
    async with _REGISTRY_LOCK:
        _REGISTRY.clear()

        if not _DESKTOP_CONFIG.exists():
            logger.info(
                "mcp_bootstrap.no_config",
                path=str(_DESKTOP_CONFIG),
                impact="No MCPs registered; install one via the Plugins tab.",
            )
            return dict(_REGISTRY)

        try:
            data = json.loads(_DESKTOP_CONFIG.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(
                "mcp_bootstrap.config_unreadable",
                error=str(exc),
                path=str(_DESKTOP_CONFIG),
            )
            return dict(_REGISTRY)

        servers = data.get("mcpServers") or {}
        loaded = 0

        for server_key, cfg in servers.items():
            try:
                cmd = cfg.get("command") or ""
                args = list(cfg.get("args") or [])
                metadata = cfg.get("metadata") or {}

                if not cmd:
                    logger.debug(
                        "mcp_bootstrap.skip_no_command",
                        server_key=server_key,
                    )
                    continue

                # Build the stdio command chain. MCPBridgeAdapter
                # expects the full argv as a list so subprocess.exec
                # can spawn it directly.
                command_chain = [cmd, *args]

                # Guess the npm package (for audit / diagnose output).
                package: str | None = None
                if cmd == "npx":
                    # Strip optional "-y" then take the first
                    # remaining token that looks like a package.
                    for token in args:
                        if token in ("-y", "--yes"):
                            continue
                        if token.startswith("-"):
                            continue
                        package = token
                        break

                adapter = MCPBridgeAdapter(
                    server_name=server_key,
                    command=command_chain,
                )
                installed = InstalledMCP(
                    server_key=server_key,
                    display_name=metadata.get("name") or server_key,
                    description=metadata.get("description") or "",
                    command=cmd,
                    args=args,
                    adapter=adapter,
                    package=package,
                )
                _REGISTRY[server_key] = installed
                loaded += 1
                logger.debug(
                    "mcp_bootstrap.adapter_ready",
                    server_key=server_key,
                    package=package,
                )
            except Exception as exc:
                logger.warning(
                    "mcp_bootstrap.adapter_failed",
                    server_key=server_key,
                    error=str(exc),
                )

        logger.info(
            "mcp_bootstrap.registry_ready",
            count=loaded,
            path=str(_DESKTOP_CONFIG),
        )

    return dict(_REGISTRY)


def list_installed_mcps() -> list[InstalledMCP]:
    """Return the current bootstrap registry (process-wide)."""
    return list(_REGISTRY.values())


def get_installed_mcp(server_key: str) -> InstalledMCP | None:
    """Lookup a specific installed MCP by its claude_desktop key."""
    return _REGISTRY.get(server_key)


async def diagnose_mcp(server_key: str) -> dict[str, Any]:
    """Run a quick health check on an installed MCP.

    Attempts to verify the command is present on PATH (without
    actually starting the MCP server). Used by Daena's plugin-admin
    tools to answer "is Netlify MCP actually installed and
    spawnable on this machine?".
    """
    entry = _REGISTRY.get(server_key)
    if not entry:
        return {
            "server_key": server_key,
            "status": "not_registered",
            "detail": "No such entry in bootstrap registry.",
        }

    try:
        installed = await entry.adapter.check_installed()
        return {
            "server_key": server_key,
            "status": "ok" if installed else "command_missing",
            "command": entry.command,
            "args": entry.args,
            "package": entry.package,
            "detail": (
                "Command resolvable; MCP should spawn on first call."
                if installed
                else f"`{entry.command}` not found on PATH; install it first."
            ),
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "server_key": server_key,
            "status": "error",
            "detail": str(exc),
        }
