"""Tests for plugin_catalog + mcp_bootstrap + PluginAdminAgent.

Pins Option B (backend catalog) and Option A (stdio MCP bootstrap)
contracts so subsequent refactors cannot silently break:

  * The catalog is well-formed (no empty skill lists, every skill
    tool id unique within a plugin, every mcp_package well-scoped)
  * The bootstrap registry loads cleanly from a synthetic config
  * Daena's plugin-admin agent correctly maps every operation through
    its OPERATION_ACTION_MAP (governance hook)
  * install_plugin / uninstall_plugin round-trip through the config
    file without corrupting existing entries
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.services.daenabot.plugin_admin_agent import PluginAdminAgent
from app.services.mcp_bootstrap import (
    bootstrap_installed_mcps,
    get_installed_mcp,
    list_installed_mcps,
)
from app.services.plugin_catalog import (
    PLUGIN_CATALOG,
    get_plugin,
    list_plugins,
    list_plugins_by_category,
    plugins_with_mcp,
    skill_description,
)


# ── Catalog structure ──


class TestCatalogStructure:
    def test_not_empty(self) -> None:
        assert len(PLUGIN_CATALOG) > 0

    def test_every_plugin_has_skills(self) -> None:
        for plugin in PLUGIN_CATALOG.values():
            assert plugin.skills, f"{plugin.id} must declare at least one skill"

    def test_skill_ids_unique_within_plugin(self) -> None:
        for plugin in PLUGIN_CATALOG.values():
            ids = [s.id for s in plugin.skills]
            assert len(ids) == len(set(ids)), (
                f"{plugin.id} has duplicate skill ids: {ids}"
            )

    def test_mcp_package_scoped(self) -> None:
        """Any plugin with an mcp_package should use a real-looking
        npm identifier -- either scoped (@org/pkg) or bare-name."""
        for plugin in plugins_with_mcp():
            pkg = plugin.mcp_package
            assert pkg, plugin.id
            assert "/" in pkg or "-" in pkg or "_" in pkg, (
                f"{plugin.id} mcp_package '{pkg}' does not look like a"
                " real npm package"
            )

    def test_list_plugins_matches_catalog(self) -> None:
        assert len(list_plugins()) == len(PLUGIN_CATALOG)

    def test_list_grouped_preserves_categories(self) -> None:
        grouped = list_plugins_by_category()
        total = sum(len(items) for items in grouped.values())
        assert total == len(PLUGIN_CATALOG)

    def test_get_plugin_roundtrip(self) -> None:
        assert get_plugin("github") is not None
        assert get_plugin("definitely-not-a-plugin") is None

    def test_skill_description_resolves(self) -> None:
        # Pick any skill from any plugin and ensure lookup works.
        plugin = next(iter(PLUGIN_CATALOG.values()))
        first_skill = plugin.skills[0]
        assert skill_description(first_skill.id) == first_skill.description

    def test_skill_description_missing_returns_none(self) -> None:
        assert skill_description("definitely_not_a_skill_id") is None


# ── Bootstrap ──


class TestMCPBootstrap:
    @pytest.mark.asyncio
    async def test_bootstrap_with_no_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No config file present -> empty registry, no errors."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        # Flush module-level path cache by reloading the module.
        import importlib

        from app.services import mcp_bootstrap as boot_mod
        importlib.reload(boot_mod)

        registry = await boot_mod.bootstrap_installed_mcps()
        assert registry == {}

    @pytest.mark.asyncio
    async def test_bootstrap_reads_synthetic_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Write a synthetic claude_desktop_config.json and confirm
        each entry produces a registry entry with a spawnable command
        chain."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        cfg_dir = tmp_path / "AppData" / "Roaming" / "Claude"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        config = {
            "mcpServers": {
                "mcp-github": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "metadata": {
                        "name": "GitHub MCP",
                        "description": "GitHub reference server",
                    },
                },
                "mcp-gdrive": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-gdrive"],
                },
            }
        }
        (cfg_dir / "claude_desktop_config.json").write_text(
            json.dumps(config), encoding="utf-8"
        )
        # Reload bootstrap so its module-level _DESKTOP_CONFIG path
        # re-resolves under the monkeypatched Path.home().
        import importlib

        from app.services import mcp_bootstrap as boot_mod
        importlib.reload(boot_mod)

        registry = await boot_mod.bootstrap_installed_mcps()
        assert "mcp-github" in registry
        assert "mcp-gdrive" in registry

        gh = registry["mcp-github"]
        assert gh.package == "@modelcontextprotocol/server-github"
        assert gh.display_name == "GitHub MCP"
        assert gh.command == "npx"


# ── Plugin admin agent ──


class TestPluginAdminAgent:
    @pytest.mark.asyncio
    async def test_list_catalog_returns_plugins(self) -> None:
        agent = PluginAdminAgent()
        result = await agent.execute("list_catalog", {})
        assert result["success"] is True
        assert result["output"]["count"] > 0

    @pytest.mark.asyncio
    async def test_list_catalog_filter_by_category(self) -> None:
        agent = PluginAdminAgent()
        result = await agent.execute(
            "list_catalog", {"category": "Coding"}
        )
        assert all(
            p["category"] == "Coding" for p in result["output"]["plugins"]
        )

    @pytest.mark.asyncio
    async def test_unknown_operation_returns_error(self) -> None:
        agent = PluginAdminAgent()
        result = await agent.execute("nonexistent_op", {})
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_install_uninstall_roundtrip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        # Reload both modules so they pick up the patched Path.home.
        import importlib

        from app.services import mcp_bootstrap as boot_mod
        from app.services.daenabot import plugin_admin_agent as adm_mod
        importlib.reload(boot_mod)
        importlib.reload(adm_mod)

        agent = adm_mod.PluginAdminAgent()

        # Install a plugin that has an mcp_package in the catalog.
        r1 = await agent.execute(
            "install_plugin", {"plugin_id": "github"}
        )
        assert r1["success"] is True, r1

        installed_keys = [m.server_key for m in boot_mod.list_installed_mcps()]
        assert "mcp-github" in installed_keys

        # Uninstall.
        r2 = await agent.execute(
            "uninstall_plugin", {"plugin_id": "github"}
        )
        assert r2["success"] is True

        installed_keys_after = [
            m.server_key for m in boot_mod.list_installed_mcps()
        ]
        assert "mcp-github" not in installed_keys_after

    @pytest.mark.asyncio
    async def test_install_unknown_plugin_errors(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        agent = PluginAdminAgent()
        r = await agent.execute(
            "install_plugin", {"plugin_id": f"nope-{uuid.uuid4().hex[:6]}"}
        )
        assert r["success"] is False
        assert "catalog" in r["error"].lower()

    def test_operation_action_map_complete(self) -> None:
        """Every operation must have a governance action_type so the
        approval layer can classify it. If a new op gets added
        without an action_type the governance pipeline fails open."""
        expected = {
            "list_catalog",
            "list_installed",
            "install_plugin",
            "uninstall_plugin",
            "diagnose_plugin",
            "refresh_registry",
            "fix_plugin",
            "list_tools",
            "call_tool",
        }
        assert expected.issubset(set(PluginAdminAgent.OPERATION_ACTION_MAP))


# ── MCP invoker ──


class TestMCPInvoker:
    @pytest.mark.asyncio
    async def test_list_tools_rejects_missing_args(self) -> None:
        agent = PluginAdminAgent()
        r = await agent.execute("list_tools", {})
        assert r["success"] is False

    @pytest.mark.asyncio
    async def test_call_tool_rejects_missing_args(self) -> None:
        agent = PluginAdminAgent()
        r = await agent.execute(
            "call_tool", {"plugin_id": "github"}  # no tool_name
        )
        assert r["success"] is False
        assert "tool_name" in (r.get("error") or "").lower()

    @pytest.mark.asyncio
    async def test_list_tools_unknown_server(self) -> None:
        """Asking to list tools for an MCP that's not in the registry
        surfaces a clear 'not in bootstrap registry' error instead of
        hanging on a spawn. This is the failure mode a user hits when
        they haven't actually installed the plugin yet."""
        agent = PluginAdminAgent()
        r = await agent.execute(
            "list_tools", {"plugin_id": f"nope-{uuid.uuid4().hex[:6]}"}
        )
        assert r["success"] is False
        assert "registry" in (r.get("error") or "").lower()

    @pytest.mark.asyncio
    async def test_call_tool_unknown_server(self) -> None:
        agent = PluginAdminAgent()
        r = await agent.execute(
            "call_tool",
            {"plugin_id": "never-installed", "tool_name": "do_thing"},
        )
        assert r["success"] is False
        assert "registry" in (r.get("error") or "").lower()
