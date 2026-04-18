"""Extension scanner -- reads installed plugins/MCP servers from Claude config.

Scans:
  1. ~/.claude/plugins/installed_plugins.json (Claude Code plugins)
  2. ~/AppData/Roaming/Claude/claude_desktop_config.json (MCP servers)

Returns a unified list of extensions with name, source, enabled status.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)

_PLUGINS_PATH = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
_DESKTOP_CONFIG = Path.home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json"


@dataclass
class ExtensionInfo:
    """Metadata about a detected extension/plugin."""

    id: str
    name: str
    source: str  # "claude-plugins-official", "superpowers-marketplace", "mcp-server"
    category: str  # "lsp", "tool", "connector", "skill", "other"
    enabled: bool
    description: str
    # Session 10: Claude Desktop parity -- surface the tool list and
    # version so the per-tool permissions UI and the header "v0.2.1 --"
    # can render without a second round-trip. Empty list is fine;
    # frontend shows an informative placeholder when tools are unknown.
    tools: list[str] = field(default_factory=list)
    version: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "source": self.source,
            "category": self.category,
            "enabled": self.enabled,
            "description": self.description,
            "tools": list(self.tools),
            "version": self.version,
        }


def _categorize_plugin(name: str) -> str:
    """Auto-categorize a plugin by its name."""
    lower = name.lower()
    if lower.endswith("-lsp"):
        return "lsp"
    if any(k in lower for k in ["figma", "playwright", "chrome", "slack", "notion", "firebase", "supabase", "stripe", "linear", "atlassian", "github", "gitlab", "postman", "sentry", "posthog"]):
        return "connector"
    if any(k in lower for k in ["skill", "firecrawl", "context7", "sourcegraph", "greptile", "pinecone"]):
        return "tool"
    if any(k in lower for k in ["output-style", "frontend-design", "playground", "code-review", "commit", "hookify", "pr-review", "superpowers"]):
        return "skill"
    return "other"


def _human_name(plugin_id: str) -> str:
    """Convert plugin ID to human-readable name."""
    # "figma@claude-plugins-official" -> "Figma"
    name_part = plugin_id.split("@")[0]
    # "chrome-devtools-mcp" -> "Chrome Devtools MCP"
    return name_part.replace("-", " ").replace("_", " ").title()


def scan_extensions() -> list[ExtensionInfo]:
    """Scan all extension sources and return a unified list."""
    extensions: list[ExtensionInfo] = []

    # 1. Claude Code plugins
    if _PLUGINS_PATH.exists():
        try:
            data = json.loads(_PLUGINS_PATH.read_text(encoding="utf-8"))
            plugins = data.get("plugins", {})
            for plugin_id, info in plugins.items():
                name_part, _, marketplace = plugin_id.partition("@")
                enabled = True
                if isinstance(info, list):
                    # Format: list of version entries
                    enabled = True
                elif isinstance(info, dict):
                    enabled = info.get("enabled", True)

                extensions.append(ExtensionInfo(
                    id=plugin_id,
                    name=_human_name(plugin_id),
                    source=marketplace or "unknown",
                    category=_categorize_plugin(name_part),
                    enabled=enabled,
                    description=f"Claude Code plugin ({marketplace})",
                ))
        except Exception as exc:
            logger.warning("extension_scanner.plugins_read_failed", error=str(exc))

    # 2. Claude Desktop MCP servers (legacy mcpServers in config)
    if _DESKTOP_CONFIG.exists():
        try:
            data = json.loads(_DESKTOP_CONFIG.read_text(encoding="utf-8"))
            servers = data.get("mcpServers", {})
            for name, cfg in servers.items():
                cmd = cfg.get("command", "")
                args = cfg.get("args", [])
                desc = f"{cmd} {' '.join(str(a) for a in args[:2])}" if cmd else "MCP server"
                extensions.append(ExtensionInfo(
                    id=f"mcp-{name}",
                    name=name.replace("-", " ").replace("_", " ").title(),
                    source="mcp-server",
                    category="connector",
                    enabled=True,
                    description=desc,
                ))
        except Exception as exc:
            logger.warning("extension_scanner.desktop_config_failed", error=str(exc))

    # 3. Claude Desktop Extensions (new format: Claude Extensions/ directory with manifests)
    _extensions_dir = Path.home() / "AppData" / "Roaming" / "Claude" / "Claude Extensions"
    if _extensions_dir.exists():
        try:
            for ext_dir in _extensions_dir.iterdir():
                if not ext_dir.is_dir():
                    continue
                manifest_path = ext_dir / "manifest.json"
                if not manifest_path.exists():
                    continue
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    ext_name = manifest.get("display_name") or manifest.get("name", ext_dir.name)
                    ext_desc = manifest.get("description", "Claude Desktop extension")
                    ext_version = manifest.get("version", "")
                    if ext_version:
                        ext_desc = f"v{ext_version} -- {ext_desc[:80]}"

                    # Session 10: extract tool list where the manifest
                    # declares it. Claude Desktop Extensions (DXT) put
                    # tools under either `tools` (top-level) or
                    # `mcp.tools`. Missing = empty; frontend shows a
                    # placeholder so the user knows why.
                    raw_tools = (
                        manifest.get("tools")
                        or manifest.get("mcp", {}).get("tools", [])
                        or []
                    )
                    tool_names: list[str] = []
                    if isinstance(raw_tools, list):
                        for t in raw_tools:
                            if isinstance(t, str):
                                tool_names.append(t)
                            elif isinstance(t, dict) and t.get("name"):
                                tool_names.append(str(t["name"]))

                    extensions.append(ExtensionInfo(
                        id=f"dxt-{manifest.get('name', ext_dir.name)}",
                        name=ext_name,
                        source="mcp-server",
                        category="connector",
                        enabled=True,
                        description=ext_desc[:120],
                        tools=tool_names,
                        version=ext_version,
                    ))
                except Exception:
                    pass  # Skip malformed manifests
        except Exception as exc:
            logger.warning("extension_scanner.extensions_dir_failed", error=str(exc))

    logger.info("extension_scanner.complete", total=len(extensions))
    return extensions
