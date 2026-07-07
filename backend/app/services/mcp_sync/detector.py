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
import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Data classes ─────────────────────────────────────────────────────

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


@dataclass(slots=True)
class CandidatePathProbe:
    """Result of probing one candidate config path.

    Used by the discovery debug payload so the operator can see EXACTLY
    which paths Daena searched and why each one did or didn't yield
    MCP servers. NEVER carries env values, secrets, or full server
    config -- just the existence + parse status + count.
    """

    cli: str            # "claude_code" / "codex" / "gemini_cli"
    path: str           # absolute path Daena tried
    exists: bool        # was the file present on disk?
    parse_ok: bool      # did it parse as JSON?
    has_mcp_block: bool # did it contain a mcpServers / mcp_servers block?
    mcp_count: int      # how many entries in that block
    server_names: list[str] = field(default_factory=list)
    skip_reason: str = ""  # why this path was skipped (if exists=False or parse_ok=False)


# ── CLI config candidates (ordered by likelihood) ────────────────────

def _home() -> Path:
    return Path.home()


def _is_wsl() -> bool:
    """True when running inside WSL (Linux kernel with Microsoft signature).

    Detection uses /proc/version on Linux only -- a single read; no shell.
    Returns False on macOS / native Windows / errors.
    """
    if platform.system() != "Linux":
        return False
    try:
        return "microsoft" in Path("/proc/version").read_text("utf-8").lower()
    except OSError:
        return False


def _wsl_windows_user_home() -> Path | None:
    """Best-effort guess at the Windows user's profile directory from WSL.

    Strategy: enumerate /mnt/c/Users entries, skip well-known
    non-user folders, return the first one that has both AppData and
    .claude (matches a real Windows user profile). Returns None if the
    /mnt/c bridge is not mounted or no candidate matches.

    NEVER reads any file under the candidate -- only checks existence
    of well-known folder markers.
    """
    bridge = Path("/mnt/c/Users")
    if not bridge.is_dir():
        return None
    skip = {"All Users", "Default", "Default User", "Public",
            "desktop.ini", "WDAGUtilityAccount"}
    try:
        entries = [p for p in bridge.iterdir() if p.is_dir() and p.name not in skip]
    except OSError:
        return None
    for entry in entries:
        try:
            if (entry / "AppData" / "Roaming").is_dir():
                return entry
        except OSError:
            # A locked / sandbox profile (e.g. CodexSandboxOffline) can
            # make stat() raise PermissionError instead of returning
            # False. Skip that entry and keep scanning -- a later one may
            # be the real Windows user -- rather than letting the error
            # propagate up through the module-level _CANDIDATES build and
            # abort `import app.main` (the backend's WSL launch path).
            continue
    return None


def _build_candidates() -> dict[str, list[Path]]:
    """Build the ordered candidate list. Includes WSL bridge paths when
    appropriate so a Linux-side backend can still find MCP configs the
    operator wrote on the Windows side via Claude / Codex / Gemini."""
    cands: dict[str, list[Path]] = {
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

    # WSL bridge: when Daena's backend boots in WSL but the operator
    # installed MCP servers using Windows-side Claude / Codex / Gemini,
    # /home/<user>/.claude/* will be empty even though the configs do
    # exist on the Windows host. Bridge in /mnt/c/Users/<win-user>/ ...
    # paths so the detector covers both sides without forcing the
    # operator to symlink directories.
    if _is_wsl():
        win_home = _wsl_windows_user_home()
        if win_home is not None:
            cands["claude_code"].extend([
                win_home / "AppData" / "Roaming" / "Claude" / "claude_desktop_config.json",
                win_home / ".claude" / "mcp.json",
                win_home / ".claude.json",
            ])
            cands["codex"].extend([
                win_home / ".codex" / "config.json",
                win_home / ".openai" / "codex.json",
            ])
            cands["gemini_cli"].extend([
                win_home / ".gemini" / "mcp_servers.json",
                win_home / ".gemini" / "settings.json",
                win_home / ".config" / "google-gemini" / "mcp.json",
            ])

    # Allow per-CLI overrides via env (operators occasionally relocate
    # configs to non-standard paths; the override is opt-in and named
    # only -- we never auto-write to it).
    for cli, env_var in (
        ("claude_code", "DAENA_CLAUDE_CONFIG"),
        ("codex", "DAENA_CODEX_CONFIG"),
        ("gemini_cli", "DAENA_GEMINI_CONFIG"),
    ):
        override = os.environ.get(env_var, "").strip()
        if override:
            cands[cli].insert(0, Path(override))

    # De-duplicate while preserving order (resolve() collapses ../ and
    # case differences on Windows; falls back to the literal Path on
    # OSError so a non-existent path is still tried as written).
    deduped: dict[str, list[Path]] = {}
    for cli, paths in cands.items():
        seen: set[str] = set()
        out: list[Path] = []
        for p in paths:
            try:
                key = str(p.resolve())
            except OSError:
                key = str(p)
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
        deduped[cli] = out
    return deduped


# Lazy singleton -- _build_candidates() is cheap (~10 fs stat calls) but
# we cache the dict so successive discovery runs in the same process
# don't redo the WSL detection.
_CANDIDATES_CACHE: dict[str, list[Path]] | None = None


def _candidates() -> dict[str, list[Path]]:
    global _CANDIDATES_CACHE
    if _CANDIDATES_CACHE is None:
        _CANDIDATES_CACHE = _build_candidates()
    return _CANDIDATES_CACHE


def reset_candidates_cache() -> None:
    """Test hook: drop the candidates cache so a fresh build runs."""
    global _CANDIDATES_CACHE
    _CANDIDATES_CACHE = None


# Module-level _CANDIDATES kept for backward compatibility with any
# external import; reads call _candidates() so WSL bridge + env
# overrides work.
_CANDIDATES = _candidates()


# ── Detector ────────────────────────────────────────────────────────

class CLIMCPDetector:
    """Discovery service. Read-only; never mutates CLI configs."""

    async def discover_all(self) -> list[DetectedMCP]:
        """Scan every known CLI and return a merged flat list of MCPs."""
        candidates = _candidates()
        tasks = [self._discover_one(cli) for cli in candidates]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        merged: list[DetectedMCP] = []
        for chunk in results:
            merged.extend(chunk)
        logger.info(
            "mcp_sync.discovered",
            total=len(merged),
            by_cli={c: sum(1 for m in merged if m.source_cli == c) for c in candidates},
        )
        return merged

    async def discover_with_debug(
        self,
    ) -> tuple[list[DetectedMCP], list[CandidatePathProbe]]:
        """Scan every known CLI; return MCPs + per-candidate probe debug.

        The debug list NEVER contains env values or full config blobs.
        Each entry carries only: cli, path, exists, parse_ok,
        has_mcp_block, mcp_count, server_names. Used by the discovery
        endpoint so the frontend can show "checked 12 paths, 0 had
        mcpServers" instead of a bare "0 found."
        """
        candidates = _candidates()
        all_mcps: list[DetectedMCP] = []
        all_probes: list[CandidatePathProbe] = []
        for cli, paths in candidates.items():
            for path in paths:
                probe, mcps = await self._probe_path(cli, path)
                all_probes.append(probe)
                all_mcps.extend(mcps)
        logger.info(
            "mcp_sync.discovered_with_debug",
            total_mcps=len(all_mcps),
            paths_checked=len(all_probes),
            paths_existing=sum(1 for p in all_probes if p.exists),
            paths_with_mcp_block=sum(1 for p in all_probes if p.has_mcp_block),
        )
        return all_mcps, all_probes

    async def _probe_path(
        self, cli: str, path: Path,
    ) -> tuple[CandidatePathProbe, list[DetectedMCP]]:
        """Probe one candidate path; return (debug, list of MCPs).

        Reads the file when present + JSON-parseable. Returns an empty
        list of MCPs (with debug populated) on missing / unreadable
        / no-mcpServers-block.
        """
        if not path.exists():
            return CandidatePathProbe(
                cli=cli, path=str(path), exists=False, parse_ok=False,
                has_mcp_block=False, mcp_count=0, skip_reason="not_found",
            ), []
        try:
            raw = await asyncio.to_thread(path.read_text, "utf-8")
            data = json.loads(raw)
        except (OSError, json.JSONDecodeError) as exc:
            logger.debug(
                "mcp_sync.config_unreadable", cli=cli, path=str(path),
                error_type=type(exc).__name__,
            )
            return CandidatePathProbe(
                cli=cli, path=str(path), exists=True, parse_ok=False,
                has_mcp_block=False, mcp_count=0,
                skip_reason=f"parse_error:{type(exc).__name__}",
            ), []
        servers_block = self._mcp_block(data)
        if not servers_block:
            return CandidatePathProbe(
                cli=cli, path=str(path), exists=True, parse_ok=True,
                has_mcp_block=False, mcp_count=0,
                skip_reason="no_mcp_block",
            ), []
        mcps = self._extract(cli, str(path), data)
        return CandidatePathProbe(
            cli=cli, path=str(path), exists=True, parse_ok=True,
            has_mcp_block=True, mcp_count=len(mcps),
            server_names=[m.name for m in mcps],
        ), mcps

    @staticmethod
    def _mcp_block(data: Any) -> dict | None:
        """Return the mcpServers / mcp_servers block if present."""
        if not isinstance(data, dict):
            return None
        block: Any = data.get("mcpServers") or data.get("mcp_servers")
        if not block:
            mcp_section = data.get("mcp")
            if isinstance(mcp_section, dict):
                block = mcp_section.get("servers")
        return block if isinstance(block, dict) else None

    async def _discover_one(self, cli: str) -> list[DetectedMCP]:
        """Try each candidate path for a CLI and return the first hit."""
        for path in _candidates()[cli]:
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
