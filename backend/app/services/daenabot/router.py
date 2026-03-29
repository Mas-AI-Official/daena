"""DaenaBotRouter — maps natural-language messages to tool calls.

Phase 1: regex pattern matching for common file/terminal/browser intents.
Phase 2+: will use LLM function-calling for richer extraction.

Used by ChatOrchestrator (Stage 7.5) to detect when a user message
in EXE mode should trigger a DaenaBot agent before the LLM streams.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A parsed tool invocation extracted from a user message."""

    tool_name: str          # e.g. "file.list_directory"
    params: dict[str, Any]  # e.g. {"path": "/home/user/project"}
    description: str        # Human-readable: "List files in /home/user/project"


# ── Pattern definitions ───────────────────────────────────────

# Each pattern: (compiled regex, tool_name, param builder, description template)
# param builder: callable(match) -> dict
# description template: str with {group_name} placeholders

_FILE_PATTERNS: list[tuple[re.Pattern[str], str, Any, str]] = [
    (
        re.compile(
            r"(?:list|show|ls|dir)\s+(?:files?\s+(?:in|at|under|of)\s+)?(.+)",
            re.IGNORECASE,
        ),
        "file.list_directory",
        lambda m: {"path": m.group(1).strip().strip("\"'")},
        "List files in {path}",
    ),
    (
        re.compile(
            r"(?:read|cat|show|display|open)\s+(?:the\s+)?(?:(?:file|contents?\s+of)\s+)?(.+)",
            re.IGNORECASE,
        ),
        "file.read_file",
        lambda m: {"path": m.group(1).strip().strip("\"'")},
        "Read file {path}",
    ),
    (
        re.compile(
            r"(?:create|make|touch)\s+(?:a\s+)?(?:new\s+)?file\s+(?:called\s+|named\s+)?(.+?)(?:\s+with\s+(?:content|text)\s+[\"'](.+)[\"'])?$",
            re.IGNORECASE,
        ),
        "file.create_file",
        lambda m: {
            "path": m.group(1).strip().strip("\"'"),
            "content": m.group(2) or "",
        },
        "Create file {path}",
    ),
    (
        re.compile(
            r"(?:write|save)\s+[\"'](.+?)[\"']\s+(?:to|into)\s+(.+)",
            re.IGNORECASE,
        ),
        "file.write_file",
        lambda m: {
            "path": m.group(2).strip().strip("\"'"),
            "content": m.group(1),
        },
        "Write to {path}",
    ),
    (
        re.compile(
            r"(?:move|mv|rename)\s+(.+?)\s+(?:to|->)\s+(.+)",
            re.IGNORECASE,
        ),
        "file.move_file",
        lambda m: {
            "source": m.group(1).strip().strip("\"'"),
            "destination": m.group(2).strip().strip("\"'"),
        },
        "Move {source} to {destination}",
    ),
    (
        re.compile(
            r"(?:delete|remove|archive)\s+(?:the\s+)?(?:file\s+)?(.+)",
            re.IGNORECASE,
        ),
        "file.delete_file",
        lambda m: {"path": m.group(1).strip().strip("\"'")},
        "Archive file {path}",
    ),
]

_TERMINAL_PATTERNS: list[tuple[re.Pattern[str], str, Any, str]] = [
    (
        re.compile(
            r"(?:run|execute|exec)\s+(?:the\s+)?(?:command\s+)?[`\"'](.+?)[`\"']",
            re.IGNORECASE,
        ),
        "terminal.execute_command",
        lambda m: {"command": m.group(1)},
        "Execute: {command}",
    ),
    (
        re.compile(
            r"(?:run|execute|exec)\s+(?:the\s+)?(?:command\s+)?(.+)",
            re.IGNORECASE,
        ),
        "terminal.execute_command",
        lambda m: {"command": m.group(1).strip()},
        "Execute: {command}",
    ),
]

_BROWSER_PATTERNS: list[tuple[re.Pattern[str], str, Any, str]] = [
    (
        re.compile(
            r"(?:go\s+to|navigate\s+to|open|visit|browse)\s+(https?://\S+)",
            re.IGNORECASE,
        ),
        "browser.navigate",
        lambda m: {"url": m.group(1).strip()},
        "Navigate to {url}",
    ),
    (
        re.compile(
            r"(?:screenshot|capture|snap)\s+(?:of\s+)?(https?://\S+)",
            re.IGNORECASE,
        ),
        "browser.screenshot",
        lambda m: {"url": m.group(1).strip()},
        "Screenshot {url}",
    ),
    (
        re.compile(
            r"(?:extract|get|scrape)\s+(?:the\s+)?text\s+(?:from|of)\s+(https?://\S+)",
            re.IGNORECASE,
        ),
        "browser.extract_text",
        lambda m: {"url": m.group(1).strip()},
        "Extract text from {url}",
    ),
]

# Priority order: terminal > file > browser
# Terminal patterns require an explicit "run/execute/exec" prefix, so they
# won't swallow bare file commands like "ls /tmp".  But without going first,
# "run ls -la" matches the file `ls` pattern via regex *search* (not match).
_ALL_PATTERNS = _TERMINAL_PATTERNS + _FILE_PATTERNS + _BROWSER_PATTERNS


class DaenaBotRouter:
    """Maps user messages to DaenaBot tool calls via pattern matching.

    Usage::

        router = DaenaBotRouter()
        call = router.match("list files in D:\\\\Ideas\\\\Daena")
        if call:
            print(call.tool_name)   # "file.list_directory"
            print(call.params)      # {"path": "D:\\\\Ideas\\\\Daena"}
    """

    @staticmethod
    def match(message: str) -> ToolCall | None:
        """Try to match a user message to a DaenaBot tool call.

        Returns:
            ToolCall if a match is found, None otherwise.
        """
        stripped = message.strip()
        if not stripped:
            return None

        for pattern, tool_name, param_builder, desc_template in _ALL_PATTERNS:
            m = pattern.search(stripped)
            if m:
                try:
                    params = param_builder(m)
                    description = desc_template.format(**params)
                    logger.info(
                        "daenabot_router.matched",
                        tool=tool_name,
                        description=description,
                    )
                    return ToolCall(
                        tool_name=tool_name,
                        params=params,
                        description=description,
                    )
                except (IndexError, KeyError):
                    continue

        return None
