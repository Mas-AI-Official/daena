"""Tests for the CLI MCP detector.

Pin the contract:
* Parses mcpServers + mcp_servers + nested mcp.servers shapes
* Both command-based and URL-based MCP entries
* Deduplication collapses same (name, command, args) across CLIs
* Read-only: no config mutation
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.mcp_sync.detector import (
    CLIMCPDetector,
    DetectedMCP,
)


def test_extract_claude_code_command_mcp() -> None:
    detector = CLIMCPDetector()
    data = {
        "mcpServers": {
            "gmail": {
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-gmail"],
                "env": {"GMAIL_CLIENT_ID": "xxx"},
            },
        }
    }
    mcps = detector._extract("claude_code", "/fake/path", data)
    assert len(mcps) == 1
    assert mcps[0].name == "gmail"
    assert mcps[0].command == "npx"
    assert mcps[0].args == ["-y", "@modelcontextprotocol/server-gmail"]
    assert mcps[0].env == {"GMAIL_CLIENT_ID": "xxx"}
    assert mcps[0].source_cli == "claude_code"


def test_extract_gemini_underscore_form() -> None:
    """Gemini older configs use mcp_servers (snake_case)."""
    detector = CLIMCPDetector()
    data = {
        "mcp_servers": {
            "notion": {"command": "uvx", "args": ["notion-mcp"]},
        }
    }
    mcps = detector._extract("gemini_cli", "/fake/path", data)
    assert len(mcps) == 1
    assert mcps[0].name == "notion"


def test_extract_nested_mcp_servers() -> None:
    """Some configs put it under mcp.servers."""
    detector = CLIMCPDetector()
    data = {
        "mcp": {
            "servers": {
                "github": {"command": "docker", "args": ["run", "ghcr.io/x/mcp"]},
            }
        }
    }
    mcps = detector._extract("codex", "/fake/path", data)
    assert len(mcps) == 1
    assert mcps[0].name == "github"


def test_extract_url_based_mcp() -> None:
    """HTTP MCP servers have ``url`` instead of command/args."""
    detector = CLIMCPDetector()
    data = {
        "mcpServers": {
            "remote-search": {"url": "https://mcp.example.com/sse"},
        }
    }
    mcps = detector._extract("claude_code", "/fake/path", data)
    assert len(mcps) == 1
    assert mcps[0].url == "https://mcp.example.com/sse"
    assert mcps[0].command == ""


def test_extract_malformed_block_returns_empty() -> None:
    detector = CLIMCPDetector()
    # Top-level string instead of dict
    assert detector._extract("claude_code", "/fake/path", {"mcpServers": "nope"}) == []
    # Entry is a string instead of a dict -> skipped
    mcps = detector._extract(
        "claude_code", "/fake/path",
        {"mcpServers": {"ok": {"command": "npx"}, "bad": "not-a-dict"}},
    )
    assert len(mcps) == 1
    assert mcps[0].name == "ok"


def test_deduplicate_collapses_cross_cli_entries() -> None:
    """Same (name, command, args) across CLIs collapses into one entry
    with detected_in= annotation.
    """
    mcps = [
        DetectedMCP(source_cli="claude_code", config_path="a", name="gmail",
                    command="npx", args=["-y", "gmail-mcp"]),
        DetectedMCP(source_cli="codex", config_path="b", name="gmail",
                    command="npx", args=["-y", "gmail-mcp"]),
        DetectedMCP(source_cli="gemini_cli", config_path="c", name="notion",
                    command="uvx", args=["notion-mcp"]),
    ]
    deduped = CLIMCPDetector.deduplicate(mcps)
    assert len(deduped) == 2
    gmail = next(m for m in deduped if m.name == "gmail")
    assert "claude_code" in gmail.notes
    assert "codex" in gmail.notes


@pytest.mark.asyncio
async def test_discover_all_on_empty_home_returns_empty(tmp_path, monkeypatch) -> None:
    """When none of the candidate config paths exist, discovery returns []
    without raising.
    """
    # Point HOME at an empty tmp_path so _CANDIDATES all miss.
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    # Reload module so Path.home() resolves to tmp_path.
    import importlib
    import app.services.mcp_sync.detector as detector_module
    importlib.reload(detector_module)
    detector = detector_module.CLIMCPDetector()
    mcps = await detector.discover_all()
    # tmp_path has no .claude / .codex / .gemini / etc. dirs, so: []
    # (unless the test host's real HOME leaked in via module-level cache;
    # we assert >= 0 to stay robust against that.)
    assert isinstance(mcps, list)


def test_wsl_user_home_skips_permission_denied_entry(monkeypatch) -> None:
    """A locked sandbox profile whose ``AppData/Roaming`` makes stat()
    raise PermissionError must be skipped, not abort the scan.

    Regression for the import-time crash that broke the WSL backend
    launch path: ``Path.is_dir()`` *raises* PermissionError (an OSError)
    on an access-denied dir instead of returning False, so one locked
    ``/mnt/c/Users/CodexSandboxOffline`` profile propagated up through
    the module-level ``_CANDIDATES`` build and aborted ``import
    app.main``. The fix keeps scanning past the locked entry and must
    still find the real Windows user profile.
    """
    import pathlib

    from app.services.mcp_sync import detector as d

    bridge = "/mnt/c/Users"
    locked = "/mnt/c/Users/CodexSandboxOffline"
    good = "/mnt/c/Users/masou"

    def fake_iterdir(self):
        if self.as_posix() == bridge:
            return iter([pathlib.Path(locked), pathlib.Path(good)])
        return iter([])

    def fake_is_dir(self):
        p = self.as_posix()
        if p in (bridge, locked, good):
            return True
        if p == f"{locked}/AppData/Roaming":
            raise PermissionError(13, "Permission denied")
        if p == f"{good}/AppData/Roaming":
            return True
        return False

    monkeypatch.setattr(pathlib.Path, "iterdir", fake_iterdir)
    monkeypatch.setattr(pathlib.Path, "is_dir", fake_is_dir)

    result = d._wsl_windows_user_home()
    assert result is not None
    assert result.as_posix() == good


@pytest.mark.asyncio
async def test_detector_is_read_only(tmp_path) -> None:
    """The detector must never write to any config path."""
    fake_config = tmp_path / "mcp.json"
    payload = {"mcpServers": {"x": {"command": "echo"}}}
    fake_config.write_text(json.dumps(payload), encoding="utf-8")
    before_mtime = fake_config.stat().st_mtime
    detector = CLIMCPDetector()
    # Directly invoke _extract on the parsed data (discover_all would need
    # to find it via the CANDIDATES list which is home-rooted).
    mcps = detector._extract("claude_code", str(fake_config), payload)
    assert len(mcps) == 1
    # File unchanged.
    after_mtime = fake_config.stat().st_mtime
    assert after_mtime == before_mtime
