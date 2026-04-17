r"""CLI MCP detector -- scans installed Claude Code / Codex / Gemini CLI configs.

Operator pain it solves
------------------------
Today the operator installs Gmail MCP in Claude Code, then has to install
it again in Codex CLI, then again in Gemini CLI, then again in Daena's
MCP registry. Four installs for one capability.

This service reads each CLI's config file, extracts the MCP servers they
already have, and surfaces a merged list that Daena can one-click import.
Governance runs through ``install_scanner.scan_mcp_server`` before
anything goes live, so a misbehaving third-party MCP is still gated.

Config paths (Windows)
----------------------
- Claude Code:     ``~\.claude\mcp.json``  (or embedded in ``~\.claude.json``)
- Codex CLI:       ``~\.codex\config.json`` (newer) or ``~\.openai\config.json``
- Gemini CLI:      ``~\.config\google-gemini\mcp.json`` (common) or
                   ``~\.gemini\mcp_servers.json``

Exact path names vary by CLI version. The detector tries a prioritized
list of candidates for each CLI and returns the first one that parses
cleanly.

What it does NOT do (yet)
-------------------------
- Write to the CLIs' configs. Sync is one-way (CLI -> Daena).
- Auto-install detected MCPs. That stays behind an explicit operator
  action + the existing ``install_scanner`` safety gate.
- Handle credential sync. Detected MCPs must be re-authorized in Daena
  by design -- we do not copy OAuth tokens between tools.

Public API
----------
>>> detector = CLIMCPDetector()
>>> mcps = await detector.discover_all()
>>> for mcp in mcps:
...     print(mcp.source_cli, mcp.name, mcp.command)
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Data class ───────────────────────────────────────────────────────

@dataclass(slots=True)
class DetectedMCP:
    """One MCP server found in some CLI's config."""

    source_cli: str          # "claude_code", "codex", "gemini_cli"
    config_path: str         # absolute path to the config file
    name: str                # key under mcpServers / mcp_servers
    command: str             # exec command ("npx", "uvx", "docker", ...)
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    url: str = ""            # for http-based MCP servers
    notes: str = ""          # free-form status / warning


# ── CLI config candidates (ordered by likelihood) ────────────────────

def _home() -> Path:
    return Path.home()


_CANDIDATES: dict[str, list[Path]] = {
    "claude_code": [
        _home() / ".claude" / "mcp.json",
        _home() / ".claude.json",                     # legacy embedded
        _home() / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json",
    ],
    "codex": [
        _home() / ".codex" / "config.json",
        _home() / ".openai" / "codex.json",
        _home() / ".config" / "codex" / "mcp.json",
    ],
    "gemini_cli": [
        _home() / ".config" / "google-gemini" / "mcp.json",
        _home() / ".gemini" / "mcp_servers.json",
        _home() / ".gemini" / "settings.json",
    ],
}


# ── Detector ────────────────────────────────────────────────────────

class CLIMCPDetector:
    """Discovery service. Read-only; never mutates CLI configs."""

    async def discover_all(self) -> list[DetectedMCP]:
        """Scan every known CLI and return a merged flat list of MCPs."""
        tasks = [self._discover_one(cli) for cli in _CANDIDATES]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        merged: list[DetectedMCP] = []
        for chunk in results:
            merged.extend(chunk)
        logger.info(
            "mcp_sync.discovered",
            total=len(merged),
            by_cli={c: sum(1 for m in merged if m.source_cli == c) for c in _CANDIDATES},
        )
        return merged

    async def _discover_one(self, cli: str) -> list[DetectedMCP]:
        """Try each candidate path for a CLI and return the first hit."""
        for path in _CANDIDATES[cli]:
            if not path.exists():
                continue
            try:
                raw = await asyncio.to_thread(path.read_text, "utf-8")
                data = json.loads(raw)
            except (OSError, json.JSONDecodeError) as exc:
                logger.debug(
                    "mcp_sync.config_unreadable", cli=cli, path=str(path), error=str(exc),
                )
                continue
            mcps = self._extract(cli, str(path), data)
            if mcps:
                return mcps
        return []

    def _extract(
        self, cli: str, path: str, data: dict[str, Any],
    ) -> list[DetectedMCP]:
        """Extract MCP entries from a parsed config.

        Handles both ``mcpServers`` (Claude Code, Codex recent) and
        ``mcp_servers`` (Gemini CLI older), and both command-based
        (``{"command": "npx", "args": [...]}``) and URL-based
        (``{"url": "https://..."}``) MCP shapes.
        """
        servers_block = (
            data.get("mcpServers")
            or data.get("mcp_servers")
            or data.get("mcp", {}).get("servers")
            or {}
        )
        out: list[DetectedMCP] = []
        if not isinstance(servers_block, dict):
            return out
        for name, cfg in servers_block.items():
            if not isinstance(cfg, dict):
                continue
            out.append(
                DetectedMCP(
                    source_cli=cli,
                    config_path=path,
                    name=name,
                    command=str(cfg.get("command", "")),
                    args=[str(a) for a in cfg.get("args", [])] if isinstance(cfg.get("args"), list) else [],
                    env={k: str(v) for k, v in (cfg.get("env", {}) or {}).items()},
                    url=str(cfg.get("url", "")),
                    notes=str(cfg.get("notes", "")),
                )
            )
        return out

    # ── Dedup helper (public) ──────────────────────────────────

    @staticmethod
    def deduplicate(mcps: list[DetectedMCP]) -> list[DetectedMCP]:
        """Collapse MCPs with the same (name, command, args) across CLIs.

        Returns the first occurrence and annotates ``notes`` with the
        list of CLIs that had it. UI surfaces 'Gemini MCP detected in
        Claude Code + Codex' instead of three separate rows.
        """
        seen: dict[tuple[str, str, tuple[str, ...]], DetectedMCP] = {}
        cli_map: dict[tuple[str, str, tuple[str, ...]], list[str]] = {}
        for m in mcps:
            key = (m.name, m.command, tuple(m.args))
            if key not in seen:
                seen[key] = m
                cli_map[key] = []
            cli_map[key].append(m.source_cli)
        out: list[DetectedMCP] = []
        for key, m in seen.items():
            clis = sorted(set(cli_map[key]))
            m.notes = (m.notes + " | " if m.notes else "") + f"detected_in={','.join(clis)}"
            out.append(m)
        return out
