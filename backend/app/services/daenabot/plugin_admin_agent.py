"""PluginAdminAgent -- lets Daena install, list, diagnose, and fix plugins.

Exposes plugin-management as a first-class DaenaBot tool surface so
the founder can say things like:

  * "Install the Sentry plugin."
  * "Which MCPs are registered?"
  * "Diagnose the Netlify plugin -- why isn't it responding?"
  * "Fix the Google Drive MCP -- re-install it."

Every operation runs through governance (see ``OPERATION_ACTION_MAP``)
so destructive actions still require approval in GOVERNED mode.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.services.daenabot._base_agent import BaseAgent
from app.services.mcp_bootstrap import (
    bootstrap_installed_mcps,
    diagnose_mcp,
    list_installed_mcps,
)
from app.services.mcp_invoker import call_server_tool, list_server_tools
from app.services.plugin_catalog import (
    get_plugin,
    list_plugins,
    list_plugins_by_category,
    plugins_with_mcp,
)

logger = get_logger(__name__)


_DESKTOP_CONFIG = (
    Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"
)


class PluginAdminAgent(BaseAgent):
    """DaenaBot agent for plugin self-service.

    Supports operations:
      * ``list_catalog`` -- return the full plugin catalog (read-only)
      * ``list_installed`` -- return currently installed MCPs
      * ``install_plugin`` -- add an MCP entry to claude_desktop_config
      * ``uninstall_plugin`` -- remove an MCP entry
      * ``diagnose_plugin`` -- check whether an installed MCP is spawnable
      * ``refresh_registry`` -- re-read the config + rebuild adapters
      * ``fix_plugin`` -- best-effort re-install of a specific plugin
    """

    agent_name = "plugin"

    # Install / uninstall / fix touch the desktop config file, so we
    # classify them as EXTERNAL_COMMS-level (file + external package
    # fetch) to let the governance layer decide whether approval is
    # needed under the current slider. Read operations are SAFE.
    OPERATION_ACTION_MAP: dict[str, str] = {
        "list_catalog": "plugin_read",
        "list_installed": "plugin_read",
        "install_plugin": "plugin_install",
        "uninstall_plugin": "plugin_uninstall",
        "diagnose_plugin": "plugin_read",
        "refresh_registry": "plugin_read",
        "fix_plugin": "plugin_install",
        "list_tools": "plugin_read",
        "call_tool": "plugin_invoke",
    }

    # ── Dispatch ──

    async def execute(
        self, operation: str, params: dict[str, Any],
    ) -> dict[str, Any]:
        if operation == "list_catalog":
            return await self._list_catalog(params)
        if operation == "list_installed":
            return await self._list_installed(params)
        if operation == "install_plugin":
            return await self._install_plugin(params)
        if operation == "uninstall_plugin":
            return await self._uninstall_plugin(params)
        if operation == "diagnose_plugin":
            return await self._diagnose_plugin(params)
        if operation == "refresh_registry":
            return await self._refresh_registry(params)
        if operation == "fix_plugin":
            return await self._fix_plugin(params)
        if operation == "list_tools":
            return await self._list_tools(params)
        if operation == "call_tool":
            return await self._call_tool(params)
        return self._error(operation, f"Unknown plugin operation: {operation}")

    # ── Operations ──

    async def _list_catalog(self, params: dict[str, Any]) -> dict[str, Any]:
        grouped = bool(params.get("grouped", False))
        category = params.get("category")
        if grouped:
            return self._result(
                "list_catalog",
                output={"catalog": list_plugins_by_category()},
            )
        plugins = list_plugins()
        if category:
            plugins = [p for p in plugins if p.get("category") == category]
        return self._result(
            "list_catalog",
            output={"plugins": plugins, "count": len(plugins)},
        )

    async def _list_installed(self, _params: dict[str, Any]) -> dict[str, Any]:
        entries = [
            {
                "server_key": m.server_key,
                "display_name": m.display_name,
                "package": m.package,
                "command": m.command,
                "args": m.args,
                "description": m.description,
            }
            for m in list_installed_mcps()
        ]
        return self._result(
            "list_installed",
            output={"installed": entries, "count": len(entries)},
        )

    async def _install_plugin(self, params: dict[str, Any]) -> dict[str, Any]:
        plugin_id = params.get("plugin_id") or ""
        if not plugin_id:
            return self._error("install_plugin", "Missing plugin_id")

        plugin = get_plugin(plugin_id)
        if plugin is None:
            return self._error(
                "install_plugin",
                f"Plugin {plugin_id} not in catalog. "
                "Add it to plugin_catalog.py first.",
            )
        if not plugin.mcp_package:
            return self._error(
                "install_plugin",
                f"Plugin {plugin.name} has no mcp_package; "
                "install path requires a npm package.",
            )

        # Write entry to claude_desktop_config.json. Matches the
        # installer behavior in the /extensions/install endpoint.
        try:
            config = {}
            if _DESKTOP_CONFIG.exists():
                config = json.loads(
                    _DESKTOP_CONFIG.read_text(encoding="utf-8")
                )
            mcp_servers = config.setdefault("mcpServers", {})
            server_key = f"mcp-{plugin.id}"
            mcp_servers[server_key] = {
                "command": "npx",
                "args": ["-y", plugin.mcp_package],
                "metadata": {
                    "name": plugin.name,
                    "description": plugin.subtitle,
                },
            }
            _DESKTOP_CONFIG.parent.mkdir(parents=True, exist_ok=True)
            _DESKTOP_CONFIG.write_text(
                json.dumps(config, indent=2), encoding="utf-8"
            )
            # Re-bootstrap so the new entry is immediately usable
            # without a server restart.
            await bootstrap_installed_mcps()
            return self._result(
                "install_plugin",
                output={
                    "plugin_id": plugin.id,
                    "package": plugin.mcp_package,
                    "server_key": server_key,
                    "status": "installed",
                },
            )
        except Exception as exc:
            return self._error(
                "install_plugin",
                f"Install failed: {exc}",
            )

    async def _uninstall_plugin(self, params: dict[str, Any]) -> dict[str, Any]:
        server_key = params.get("server_key") or params.get("plugin_id")
        if not server_key:
            return self._error(
                "uninstall_plugin", "Missing server_key or plugin_id"
            )
        if not server_key.startswith("mcp-"):
            server_key = f"mcp-{server_key}"

        if not _DESKTOP_CONFIG.exists():
            return self._error(
                "uninstall_plugin",
                "No claude_desktop_config.json present; nothing to uninstall.",
            )
        try:
            config = json.loads(_DESKTOP_CONFIG.read_text(encoding="utf-8"))
            servers = config.get("mcpServers") or {}
            if server_key not in servers:
                return self._error(
                    "uninstall_plugin",
                    f"{server_key} not found in mcpServers.",
                )
            del servers[server_key]
            config["mcpServers"] = servers
            _DESKTOP_CONFIG.write_text(
                json.dumps(config, indent=2), encoding="utf-8"
            )
            await bootstrap_installed_mcps()
            return self._result(
                "uninstall_plugin",
                output={"server_key": server_key, "status": "uninstalled"},
            )
        except Exception as exc:
            return self._error("uninstall_plugin", f"Uninstall failed: {exc}")

    async def _diagnose_plugin(self, params: dict[str, Any]) -> dict[str, Any]:
        server_key = params.get("server_key") or params.get("plugin_id")
        if not server_key:
            return self._error(
                "diagnose_plugin", "Missing server_key or plugin_id"
            )
        if not server_key.startswith("mcp-"):
            server_key = f"mcp-{server_key}"
        report = await diagnose_mcp(server_key)
        return self._result("diagnose_plugin", output=report)

    async def _refresh_registry(self, _params: dict[str, Any]) -> dict[str, Any]:
        registry = await bootstrap_installed_mcps()
        return self._result(
            "refresh_registry",
            output={"count": len(registry), "server_keys": list(registry.keys())},
        )

    async def _fix_plugin(self, params: dict[str, Any]) -> dict[str, Any]:
        """Best-effort re-install: uninstall then install again."""
        plugin_id = params.get("plugin_id") or ""
        if not plugin_id:
            return self._error("fix_plugin", "Missing plugin_id")
        # Uninstall ignoring missing-entry errors; then re-install.
        await self._uninstall_plugin({"plugin_id": plugin_id})
        result = await self._install_plugin({"plugin_id": plugin_id})
        return self._result(
            "fix_plugin",
            output={
                "plugin_id": plugin_id,
                "final_status": result.get("output", {}).get("status"),
                "error": result.get("error"),
            },
        )

    async def _list_tools(self, params: dict[str, Any]) -> dict[str, Any]:
        """Query an installed MCP for its tool descriptors via the
        MCP SDK's stdio transport + ``tools/list``.

        Accepts ``server_key`` directly or ``plugin_id`` (which is
        normalized to ``mcp-<plugin_id>``). Returns whatever the MCP
        reports -- tool name, description, and JSON-schema for
        arguments so callers can generate prompts or UI forms.
        """
        server_key = params.get("server_key") or params.get("plugin_id")
        if not server_key:
            return self._error(
                "list_tools", "Missing server_key or plugin_id"
            )
        if not server_key.startswith("mcp-"):
            server_key = f"mcp-{server_key}"
        result = await list_server_tools(server_key)
        if not result.get("success"):
            return self._error("list_tools", result.get("error", "unknown"))
        return self._result(
            "list_tools",
            output={
                "server_key": server_key,
                "tools": result.get("tools") or [],
            },
        )

    async def _call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        """Invoke a specific tool exposed by an installed MCP.

        Caller supplies ``server_key`` (or ``plugin_id``),
        ``tool_name``, and ``arguments``. The MCP invoker handles
        spawn + handshake + ``tools/call`` end-to-end.
        """
        server_key = params.get("server_key") or params.get("plugin_id")
        tool_name = params.get("tool_name") or ""
        arguments = params.get("arguments") or {}
        if not server_key:
            return self._error(
                "call_tool", "Missing server_key or plugin_id"
            )
        if not tool_name:
            return self._error("call_tool", "Missing tool_name")
        if not server_key.startswith("mcp-"):
            server_key = f"mcp-{server_key}"
        result = await call_server_tool(server_key, tool_name, arguments)
        if not result.get("success"):
            return self._error("call_tool", result.get("error", "unknown"))
        return self._result(
            "call_tool",
            output={
                "server_key": server_key,
                "tool_name": tool_name,
                "content": result.get("content") or [],
                "is_error": bool(result.get("is_error")),
            },
        )


# Public list of plugins we consider "most-used" -- these get a
# native adapter shim (Option C slice) so the orchestrator can
# route to them even without an MCP server running.
NATIVE_ADAPTER_PLUGINS: list[str] = [
    "github",         # Code agent heavily uses this.
    "google-drive",   # Founder file access.
    "slack",          # Sales + Marketing workflows.
    "notion",         # Daena-Mind vault integration.
    "hugging-face",   # Model discovery + inference.
]
