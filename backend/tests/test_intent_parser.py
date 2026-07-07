"""Unit coverage for ``app.services.daenabot.intent_parser``.

``IntentParser`` is the deterministic front door of DaenaBot's EXE path: it
turns a free-text user message ("list files in D:\\Projects", "switch to
claude 4.7", "run npm test") into a structured ``ToolCall`` that
``QueryUnderstandingService`` hands to dispatch. It executes nothing itself --
the security gate and governance run downstream -- but a silent regression
here is dangerous precisely because its output FEEDS dispatch: mis-route
"delete X" to the wrong operation, drop a path, or mis-extract a command and
the wrong tool runs (or the right tool runs on the wrong target). None of that
raises; it just quietly does the wrong thing. So the priority order and every
branch of the parse are worth pinning.

The module is pure: it imports only ``re``/``dataclass``/``typing`` and a
logger. ``IntentParser.parse`` is regex classification plus string cleaning --
no DB, no network, no async, no LLM, no filesystem. Every expected value below
was pinned against the live parser, not re-derived from the regex, so a change
to a pattern fails these tests instead of shipping a quietly re-routed
dispatcher. A few cases are explicitly labelled "documented current behavior":
they capture today's quirks so that a future tightening of a pattern is a
deliberate, test-visible change rather than an accident.
"""
from __future__ import annotations

import dataclasses

import pytest

from app.services.daenabot.intent_parser import IntentParser, ToolCall


def _parsed(message: str) -> ToolCall:
    """Parse a message that is expected to match, failing loudly if it does not."""
    tc = IntentParser.parse(message)
    assert tc is not None, f"expected a ToolCall for {message!r}, got None"
    return tc


# ---------------------------------------------------------------------------
# ToolCall -- the immutable dispatch record
# ---------------------------------------------------------------------------

def test_tool_name_is_agent_dot_operation():
    # tool_name is the dispatch key ExecutionService keys on -- pin the format.
    assert ToolCall(agent="file", operation="read_file").tool_name == "file.read_file"


def test_tool_call_params_default_to_empty_dict():
    assert ToolCall(agent="settings", operation="get_runtime_state").params == {}


def test_tool_call_is_frozen():
    # frozen=True: a parsed call cannot be mutated out from under dispatch.
    tc = ToolCall(agent="file", operation="read_file", params={"path": "x"})
    with pytest.raises(dataclasses.FrozenInstanceError):
        tc.agent = "terminal"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# parse -- empty/whitespace/non-actionable guards
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "message",
    [
        "",
        "   ",
        "hello there how are you",
        "what is the meaning of life",
    ],
)
def test_parse_returns_none_for_non_actionable(message):
    # No actionable pattern -> None, so the message falls through to the
    # normal LLM pipeline instead of being forced into a tool call.
    assert IntentParser.parse(message) is None


# ---------------------------------------------------------------------------
# Settings / self-config -- matched FIRST so "switch X"/"use X" never gets
# misread as a shell command or a file path
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "message,alias",
    [
        ("switch to claude 4.7", "claude 4.7"),
        ("switch your primary mind to grok", "grok"),
        ("set primary mind to codex", "codex"),
        ("use codex as primary", "codex"),
        ("use grok as my main brain", "grok"),
        ("make claude my primary", "claude"),
        ("make claude primary", "claude"),
    ],
)
def test_settings_set_primary_mind(message, alias):
    tc = _parsed(message)
    assert (tc.agent, tc.operation) == ("settings", "set_primary_mind")
    assert tc.params == {"mind_alias": alias}


@pytest.mark.parametrize("tail", [" max", " please"])
def test_settings_strips_trailing_modal_tokens(tail):
    # "claude 4.7 max" / "claude 4.7 please" resolve to the bare alias.
    tc = _parsed("switch to claude 4.7" + tail)
    assert tc.params == {"mind_alias": "claude 4.7"}


@pytest.mark.parametrize(
    "message",
    [
        "which mind are you using",
        "what model is my primary",
        "current runtime",
    ],
)
def test_settings_get_runtime_state(message):
    tc = _parsed(message)
    assert (tc.agent, tc.operation) == ("settings", "get_runtime_state")
    assert tc.params == {}


def test_settings_list_available_minds():
    tc = _parsed("list available minds")
    assert (tc.agent, tc.operation) == ("settings", "list_available_minds")
    assert tc.params == {}


# ---------------------------------------------------------------------------
# Browser -- URL presence is the strong signal (checked before terminal/file)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "message,url",
    [
        ("open https://example.com", "https://example.com"),
        ("navigate to https://a.b/c", "https://a.b/c"),
        ("go to https://x.io", "https://x.io"),
    ],
)
def test_browser_navigate(message, url):
    tc = _parsed(message)
    assert (tc.agent, tc.operation) == ("browser", "navigate")
    assert tc.params == {"url": url}


def test_browser_screenshot_with_url():
    tc = _parsed("screenshot https://x.com")
    assert (tc.agent, tc.operation) == ("browser", "screenshot")
    assert tc.params == {"url": "https://x.com"}


def test_browser_screenshot_without_url_has_no_params():
    # screenshot does not require a URL (capture the current page).
    tc = _parsed("screenshot the page")
    assert (tc.agent, tc.operation) == ("browser", "screenshot")
    assert tc.params == {}


def test_browser_extract_text():
    tc = _parsed("extract text from https://x.com")
    assert (tc.agent, tc.operation) == ("browser", "extract_text")
    assert tc.params == {"url": "https://x.com"}


def test_browser_scrape_without_content_keyword_is_none():
    # Documented current behavior: the extract_text pattern requires a
    # "text"/"content"/"data" keyword, so a bare "scrape <url>" does NOT match
    # and falls through to None (it is not a file/terminal verb either).
    assert IntentParser.parse("scrape https://x.com") is None


# ---------------------------------------------------------------------------
# Terminal -- explicit run/execute/shell/cmd prefix or backtick wrap
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "message,command",
    [
        ("run ls -la", "ls -la"),
        ("execute npm test", "npm test"),
        ("cmd: dir", "dir"),
        ("shell - whoami", "whoami"),
        ("`git status`", "git status"),
    ],
)
def test_terminal_execute_command(message, command):
    tc = _parsed(message)
    assert (tc.agent, tc.operation) == ("terminal", "execute_command")
    assert tc.params == {"command": command}


# ---------------------------------------------------------------------------
# File operations -- list / read / create / write / move / delete
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "message,path",
    [
        (r"list files in D:\Projects", r"D:\Projects"),
        ("ls /tmp", "/tmp"),
        (r"show D:\foo", r"D:\foo"),  # "show" routes to list, not read
    ],
)
def test_file_list_directory(message, path):
    tc = _parsed(message)
    assert (tc.agent, tc.operation) == ("file", "list_directory")
    assert tc.params == {"path": path}


@pytest.mark.parametrize(
    "message,path",
    [
        (r"read D:\foo\bar.txt", r"D:\foo\bar.txt"),
        ("cat /etc/hosts", "/etc/hosts"),
        ("read the file foo.txt", "foo.txt"),       # filler "the file " stripped
        ("open the file /tmp/a.txt", "/tmp/a.txt"),  # "open ... file" routes to read
    ],
)
def test_file_read_file(message, path):
    tc = _parsed(message)
    assert (tc.agent, tc.operation) == ("file", "read_file")
    assert tc.params == {"path": path}


def test_file_create_without_content_defaults_to_empty():
    tc = _parsed("create file notes.txt")
    assert (tc.agent, tc.operation) == ("file", "create_file")
    assert tc.params == {"path": "notes.txt", "content": ""}


def test_file_create_with_quoted_content():
    tc = _parsed('create file notes.txt with contents "hello world"')
    assert (tc.agent, tc.operation) == ("file", "create_file")
    assert tc.params == {"path": "notes.txt", "content": "hello world"}


def test_file_write_quoted_content_to_path():
    tc = _parsed('write "hello" to notes.txt')
    assert (tc.agent, tc.operation) == ("file", "write_file")
    assert tc.params == {"path": "notes.txt", "content": "hello"}


@pytest.mark.parametrize("verb", ["move", "rename"])
def test_file_move_extracts_source_and_destination(verb):
    tc = _parsed(f"{verb} a.txt to b.txt")
    assert (tc.agent, tc.operation) == ("file", "move_file")
    assert tc.params == {"source": "a.txt", "destination": "b.txt"}


@pytest.mark.parametrize(
    "message,path",
    [
        ("delete the file secret.txt", "secret.txt"),
        ("remove temp.log", "temp.log"),
        ("archive old.log", "old.log"),  # "archive" is a delete-family verb
    ],
)
def test_file_delete_file(message, path):
    tc = _parsed(message)
    assert (tc.agent, tc.operation) == ("file", "delete_file")
    assert tc.params == {"path": path}


# ---------------------------------------------------------------------------
# _clean_path -- strips natural-language debris off an extracted path
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw,cleaned",
    [
        ("report.txt!!", "report.txt"),   # trailing punctuation
        ("x;", "x"),
        ('"foo bar"', "foo bar"),          # surrounding double quotes
        ("'q'", "q"),                       # surrounding single quotes
        ("the foo", "foo"),                 # leading filler word
        ("file foo", "foo"),
        ("folder myfolder", "myfolder"),
        ("this dir/x", "dir/x"),
        ("  spaced  ", "spaced"),          # surrounding whitespace
        (r"D:\foo.", r"D:\foo"),            # trailing dot on a Windows path
    ],
)
def test_clean_path(raw, cleaned):
    assert IntentParser._clean_path(raw) == cleaned


# ---------------------------------------------------------------------------
# Documented current-behavior quirks -- pinned so a future fix is deliberate
# ---------------------------------------------------------------------------
# Each of these is a place where today's regex produces a technically-wrong but
# stable result. Pinning them means the test fails (and is consciously updated)
# the day someone tightens the pattern, instead of the behavior drifting
# silently. See HANDOFF for the P2 follow-ups these flag.

def test_quirk_show_me_the_available_brains_falls_through_to_file_list():
    # "show me the available brains" is intended as list_available_minds, but
    # the settings list pattern only allows ONE qualifier token, so "the
    # available" defeats it and the message falls through to file.list_directory
    # with the leftover text as the path.
    tc = _parsed("show me the available brains")
    assert (tc.agent, tc.operation) == ("file", "list_directory")
    assert tc.params == {"path": "me the available brains"}


def test_quirk_unquoted_save_content_is_not_separated():
    # write/save content must be quoted to be split out; unquoted text is taken
    # whole as the path with empty content.
    tc = _parsed("save data into report.csv")
    assert (tc.agent, tc.operation) == ("file", "write_file")
    assert tc.params == {"path": "data into report.csv", "content": ""}


def test_quirk_what_files_are_in_keeps_leading_words_in_path():
    # The "what files" list trigger consumes only "what files ", leaving "are
    # in /var/log" as the captured path.
    tc = _parsed("what files are in /var/log")
    assert (tc.agent, tc.operation) == ("file", "list_directory")
    assert tc.params == {"path": "are in /var/log"}
