"""Tests for ActionPlanner and Workspace (pure unit tests, no LLM calls)."""

from __future__ import annotations

import pytest

from app.services.daenabot.planner import Action, ActionPlanner
from app.services.daenabot.workspace import ActionResult, Workspace

# ── ActionPlanner._parse_plan tests ────────────────────────────


class TestActionPlannerParsePlan:
    """Tests for ActionPlanner._parse_plan() JSON parsing."""

    def setup_method(self) -> None:
        """Create a fresh planner for each test."""
        self.planner = ActionPlanner()

    def test_parse_valid_json(self) -> None:
        """Valid JSON array produces correct Action objects."""
        raw = '[{"agent": "file", "operation": "read_file", "params": {"path": "/tmp/test.txt"}, "description": "Read the file"}]'
        actions = self.planner._parse_plan(raw)

        assert len(actions) == 1
        assert actions[0].agent == "file"
        assert actions[0].operation == "read_file"
        assert actions[0].params == {"path": "/tmp/test.txt"}
        assert actions[0].description == "Read the file"
        assert actions[0].depends_on is None

    def test_parse_multi_step_sets_depends_on(self) -> None:
        """Multi-step plans set depends_on for sequential execution."""
        raw = (
            '['
            '{"agent": "file", "operation": "read_file", "params": {"path": "/a.txt"}, "description": "Step 1"},'
            '{"agent": "terminal", "operation": "execute_command", "params": {"command": "wc -l /a.txt"}, "description": "Step 2"}'
            ']'
        )
        actions = self.planner._parse_plan(raw)

        assert len(actions) == 2
        assert actions[0].depends_on is None
        assert actions[1].depends_on == 0

    def test_parse_markdown_fenced_json(self) -> None:
        """JSON wrapped in markdown code fences is correctly extracted."""
        raw = (
            "```json\n"
            '[{"agent": "terminal", "operation": "execute_command", '
            '"params": {"command": "ls"}, "description": "List files"}]\n'
            "```"
        )
        actions = self.planner._parse_plan(raw)

        assert len(actions) == 1
        assert actions[0].agent == "terminal"
        assert actions[0].operation == "execute_command"
        assert actions[0].params == {"command": "ls"}

    def test_parse_markdown_fenced_no_language_tag(self) -> None:
        """Code fences without a language tag also work."""
        raw = (
            "```\n"
            '[{"agent": "browser", "operation": "navigate", '
            '"params": {"url": "https://example.com"}, "description": "Open site"}]\n'
            "```"
        )
        actions = self.planner._parse_plan(raw)

        assert len(actions) == 1
        assert actions[0].agent == "browser"

    def test_parse_invalid_json_returns_empty(self) -> None:
        """Invalid JSON returns an empty list (no crash)."""
        actions = self.planner._parse_plan("this is not json at all")
        assert actions == []

    def test_parse_non_array_json_returns_empty(self) -> None:
        """JSON object (not array) returns empty list."""
        actions = self.planner._parse_plan('{"agent": "file"}')
        assert actions == []

    def test_parse_empty_array(self) -> None:
        """Empty JSON array returns empty list."""
        actions = self.planner._parse_plan("[]")
        assert actions == []

    def test_parse_skips_non_dict_elements(self) -> None:
        """Non-dict items in the array are silently skipped."""
        raw = '[{"agent": "file", "operation": "read_file", "params": {}, "description": "ok"}, "not_a_dict", 42]'
        actions = self.planner._parse_plan(raw)

        assert len(actions) == 1
        assert actions[0].agent == "file"

    def test_parse_defaults_for_missing_fields(self) -> None:
        """Missing fields get sensible defaults."""
        raw = '[{"agent": "terminal"}]'
        actions = self.planner._parse_plan(raw)

        assert len(actions) == 1
        assert actions[0].operation == ""
        assert actions[0].params == {}
        assert actions[0].description == "Step 1"


# ── ActionPlanner._fallback_plan tests ─────────────────────────


class TestActionPlannerFallback:
    """Tests for ActionPlanner._fallback_plan() deterministic path."""

    def setup_method(self) -> None:
        """Create a fresh planner for each test."""
        self.planner = ActionPlanner()

    def test_fallback_with_matching_intent(self) -> None:
        """IntentParser match produces a single-step Action."""
        actions = self.planner._fallback_plan("list files in D:\\Projects")

        assert len(actions) == 1
        assert actions[0].agent == "file"
        assert actions[0].operation == "list_directory"
        assert "D:\\Projects" in actions[0].params.get("path", "")

    def test_fallback_with_terminal_intent(self) -> None:
        """Terminal command fallback works."""
        actions = self.planner._fallback_plan("run `git status`")

        assert len(actions) == 1
        assert actions[0].agent == "terminal"
        assert actions[0].operation == "execute_command"

    def test_fallback_no_match_returns_empty(self) -> None:
        """Non-actionable text returns empty list."""
        actions = self.planner._fallback_plan("what is the meaning of life")
        assert actions == []

    def test_fallback_empty_string_returns_empty(self) -> None:
        """Empty input returns empty list."""
        actions = self.planner._fallback_plan("")
        assert actions == []


# ── Workspace tests ────────────────────────────────────────────


class TestWorkspace:
    """Tests for Workspace state tracking."""

    def test_add_result_and_get_last_output(self) -> None:
        """Adding results and retrieving last output works."""
        ws = Workspace(session_id="test-session")

        ws.add_result(ActionResult(
            step_index=0,
            agent="file",
            operation="read_file",
            success=True,
            output="file contents here",
        ))
        ws.add_result(ActionResult(
            step_index=1,
            agent="terminal",
            operation="execute_command",
            success=True,
            output="command output",
        ))

        assert ws.get_last_output() == "command output"

    def test_get_last_output_skips_failures(self) -> None:
        """get_last_output skips failed results."""
        ws = Workspace(session_id="test-session")

        ws.add_result(ActionResult(
            step_index=0,
            agent="file",
            operation="read_file",
            success=True,
            output="good data",
        ))
        ws.add_result(ActionResult(
            step_index=1,
            agent="terminal",
            operation="execute_command",
            success=False,
            error="command failed",
        ))

        assert ws.get_last_output() == "good data"

    def test_get_last_output_empty_workspace(self) -> None:
        """Empty workspace returns None for last output."""
        ws = Workspace(session_id="test-session")
        assert ws.get_last_output() is None

    def test_get_last_output_skips_none_output(self) -> None:
        """Successful results with None output are skipped."""
        ws = Workspace(session_id="test-session")
        ws.add_result(ActionResult(
            step_index=0,
            agent="file",
            operation="delete_file",
            success=True,
            output=None,
        ))
        assert ws.get_last_output() is None

    def test_context_summary_formatting(self) -> None:
        """get_context_summary produces readable multi-line output."""
        ws = Workspace(session_id="test-session")

        ws.add_result(ActionResult(
            step_index=0,
            agent="file",
            operation="read_file",
            success=True,
            output="hello world",
        ))
        ws.add_result(ActionResult(
            step_index=1,
            agent="terminal",
            operation="execute_command",
            success=False,
            error="permission denied",
        ))

        summary = ws.get_context_summary()
        assert "Step 0: file.read_file -> OK" in summary
        assert "hello world" in summary
        assert "Step 1: terminal.execute_command -> FAILED: permission denied" in summary

    def test_context_summary_empty(self) -> None:
        """Empty workspace returns empty string for summary."""
        ws = Workspace(session_id="test-session")
        assert ws.get_context_summary() == ""

    def test_context_summary_truncates_long_output(self) -> None:
        """Output longer than 500 chars is truncated in summary."""
        ws = Workspace(session_id="test-session")
        long_output = "x" * 1000

        ws.add_result(ActionResult(
            step_index=0,
            agent="file",
            operation="read_file",
            success=True,
            output=long_output,
        ))

        summary = ws.get_context_summary()
        # The output in the summary should be at most 500 chars
        output_line = [line for line in summary.split("\n") if "Output:" in line][0]
        # Strip "  Output: " prefix
        output_content = output_line.split("Output: ", 1)[1]
        assert len(output_content) == 500

    def test_all_succeeded_true(self) -> None:
        """all_succeeded is True when all results are successful."""
        ws = Workspace(session_id="test-session")
        ws.add_result(ActionResult(step_index=0, agent="file", operation="read_file", success=True))
        ws.add_result(ActionResult(step_index=1, agent="file", operation="read_file", success=True))

        assert ws.all_succeeded is True
        assert ws.has_failures is False

    def test_all_succeeded_false_on_failure(self) -> None:
        """all_succeeded is False when any result failed."""
        ws = Workspace(session_id="test-session")
        ws.add_result(ActionResult(step_index=0, agent="file", operation="read_file", success=True))
        ws.add_result(ActionResult(step_index=1, agent="file", operation="read_file", success=False, error="oops"))

        assert ws.all_succeeded is False
        assert ws.has_failures is True

    def test_all_succeeded_empty_workspace(self) -> None:
        """Empty workspace reports all_succeeded=True (vacuous truth)."""
        ws = Workspace(session_id="test-session")
        assert ws.all_succeeded is True
        assert ws.has_failures is False

    def test_has_failures_all_failed(self) -> None:
        """has_failures is True when every result failed."""
        ws = Workspace(session_id="test-session")
        ws.add_result(ActionResult(step_index=0, agent="file", operation="x", success=False, error="a"))
        ws.add_result(ActionResult(step_index=1, agent="file", operation="y", success=False, error="b"))

        assert ws.has_failures is True
        assert ws.all_succeeded is False

    def test_session_id_stored(self) -> None:
        """Workspace stores the session_id correctly."""
        ws = Workspace(session_id="abc-123")
        assert ws.session_id == "abc-123"

    def test_working_directory_default(self) -> None:
        """Default working directory is current directory."""
        ws = Workspace(session_id="test")
        assert ws.working_directory == "."


# ── Action dataclass tests ─────────────────────────────────────


class TestAction:
    """Tests for the Action frozen dataclass."""

    def test_action_frozen(self) -> None:
        """Action instances are immutable."""
        action = Action(agent="file", operation="read_file")
        with pytest.raises(AttributeError):
            action.agent = "terminal"  # type: ignore[misc]

    def test_action_defaults(self) -> None:
        """Default field values are set correctly."""
        action = Action(agent="file", operation="read_file")
        assert action.params == {}
        assert action.description == ""
        assert action.depends_on is None
