"""Tests for DaenaBot API endpoints and router."""

from __future__ import annotations

import pytest

from app.services.daenabot.router import DaenaBotRouter, ToolCall

# ── Router pattern matching ──


class TestDaenaBotRouter:
    def test_match_list_files(self) -> None:
        result = DaenaBotRouter.match("list files in D:\\Ideas\\Daena")
        assert result is not None
        assert result.tool_name == "file.list_directory"
        assert "D:\\Ideas\\Daena" in result.params.get("path", "")

    def test_match_read_file(self) -> None:
        result = DaenaBotRouter.match("read the file D:\\test.txt")
        assert result is not None
        assert result.tool_name == "file.read_file"

    def test_match_run_command(self) -> None:
        result = DaenaBotRouter.match("run `git status`")
        assert result is not None
        assert result.tool_name == "terminal.execute_command"
        assert result.params["command"] == "git status"

    def test_match_navigate_url(self) -> None:
        # "navigate to" is an unambiguous browser signal
        result = DaenaBotRouter.match("navigate to https://example.com")
        assert result is not None
        assert result.tool_name == "browser.navigate"
        assert result.params["url"] == "https://example.com"

    def test_no_match_for_general_text(self) -> None:
        result = DaenaBotRouter.match("what is the meaning of life")
        assert result is None

    def test_empty_message(self) -> None:
        assert DaenaBotRouter.match("") is None
        assert DaenaBotRouter.match("   ") is None

    def test_match_create_file(self) -> None:
        result = DaenaBotRouter.match("create file test.txt")
        assert result is not None
        assert result.tool_name == "file.create_file"

    def test_match_move_file(self) -> None:
        result = DaenaBotRouter.match("move old.txt to new.txt")
        assert result is not None
        assert result.tool_name == "file.move_file"

    def test_match_screenshot(self) -> None:
        result = DaenaBotRouter.match("screenshot of https://google.com")
        assert result is not None
        assert result.tool_name == "browser.screenshot"

    def test_match_extract_text(self) -> None:
        result = DaenaBotRouter.match("extract text from https://docs.python.org")
        assert result is not None
        assert result.tool_name == "browser.extract_text"


# ── ToolCall dataclass ──


class TestToolCall:
    def test_tool_call_frozen(self) -> None:
        tc = ToolCall(
            tool_name="file.read_file",
            params={"path": "/tmp/test"},
            description="Read /tmp/test",
        )
        assert tc.tool_name == "file.read_file"
        with pytest.raises(AttributeError):
            tc.tool_name = "modified"  # type: ignore[misc]

    def test_tool_call_description(self) -> None:
        result = DaenaBotRouter.match("list files in /home/user")
        assert result is not None
        assert "list" in result.description.lower() or "List" in result.description
