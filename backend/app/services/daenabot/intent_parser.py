"""IntentParser — extracts structured DaenaBot tool calls from natural language.

Converts user messages like "list files in D:\\Projects" into structured
tool calls like ``ToolCall(agent="file", operation="list_directory",
params={"path": "D:\\\\Projects"})``.

Phase 1: regex-based deterministic parsing (fast, auditable).
Phase 2: LLM-assisted parsing for ambiguous multi-step workflows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ToolCall:
    """A parsed tool call ready for DaenaBot dispatch."""

    agent: str           # "file", "terminal", "browser"
    operation: str       # "list_directory", "execute_command", "navigate"
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def tool_name(self) -> str:
        """Dot-notation tool name for ExecutionService dispatch."""
        return f"{self.agent}.{self.operation}"


# ── Path extraction helper ─────────────────────────────────────

# Matches Windows paths (D:\foo\bar), Unix paths (/foo/bar),
# relative paths (./foo), and quoted paths ("path with spaces")
_PATH_PATTERN = re.compile(
    r'(?:'
    r'"([^"]+)"'              # Quoted path
    r'|'
    r"'([^']+)'"              # Single-quoted path
    r'|'
    r'([A-Za-z]:\\[^\s,;]+)'  # Windows absolute  (D:\Ideas\Daena)
    r'|'
    r'(/[^\s,;]+)'            # Unix absolute      (/home/user/file)
    r'|'
    r'(\./[^\s,;]+)'          # Relative with ./   (./src/main.py)
    r')'
)

# ── File operation patterns ────────────────────────────────────

_FILE_PATTERNS: list[tuple[str, re.Pattern[str], dict[str, str]]] = [
    # list / ls / show files / dir
    ("list_directory", re.compile(
        r'(?:list|show|ls|dir|what\s+files|what\'?s\s+in|contents?\s+of)'
        r'(?:\s+(?:the\s+)?(?:files?\s+(?:in|of|from|at|under))?)?'
        r'\s+(.+)',
        re.IGNORECASE,
    ), {"path_group": "1"}),

    # read / cat / show contents / open file
    ("read_file", re.compile(
        r'(?:read|cat|show|display|open|view|print)\s+'
        r'(?:(?:the\s+)?(?:contents?\s+of|file)\s+)?'
        r'(.+)',
        re.IGNORECASE,
    ), {"path_group": "1"}),

    # create / touch / new file
    ("create_file", re.compile(
        r'(?:create|touch|make|new)\s+'
        r'(?:a\s+)?(?:new\s+)?(?:file\s+)?'
        r'(?:called|named|at|in)?\s*'
        r'(.+?)(?:\s+with\s+(?:contents?|text|content)\s+["\'](.+?)["\'])?$',
        re.IGNORECASE,
    ), {"path_group": "1", "content_group": "2"}),

    # write / save / put content
    ("write_file", re.compile(
        r'(?:write|save|put|store)\s+'
        r'(?:["\'](.+?)["\']\s+(?:to|into|in)\s+)?'
        r'(.+)',
        re.IGNORECASE,
    ), {"content_group": "1", "path_group": "2"}),

    # move / rename / mv
    ("move_file", re.compile(
        r'(?:move|rename|mv)\s+'
        r'(.+?)\s+(?:to|as|->)\s+(.+)',
        re.IGNORECASE,
    ), {"source_group": "1", "dest_group": "2"}),

    # delete / remove / rm (will become ARCHIVE via governance)
    ("delete_file", re.compile(
        r'(?:delete|remove|rm|archive)\s+'
        r'(?:the\s+)?(?:file\s+)?(.+)',
        re.IGNORECASE,
    ), {"path_group": "1"}),
]

# ── Terminal patterns ──────────────────────────────────────────

_TERMINAL_PATTERNS: list[tuple[re.Pattern[str], dict[str, str]]] = [
    # Explicit "run" / "execute" / "shell" prefix
    (re.compile(
        r'(?:run|execute|exec|shell|command|cmd)\s*[:\-]?\s*(.+)',
        re.IGNORECASE,
    ), {"command_group": "1"}),

    # Backtick-wrapped commands
    (re.compile(
        r'`(.+?)`',
        re.IGNORECASE,
    ), {"command_group": "1"}),
]

# ── Browser patterns ──────────────────────────────────────────

_BROWSER_PATTERNS: list[tuple[str, re.Pattern[str], dict[str, str]]] = [
    # Navigate / open / go to URL
    ("navigate", re.compile(
        r'(?:open|navigate\s+to|go\s+to|browse|visit|load)\s+'
        r'(https?://[^\s]+)',
        re.IGNORECASE,
    ), {"url_group": "1"}),

    # Screenshot
    ("screenshot", re.compile(
        r'(?:screenshot|capture|snap)\s+'
        r'(?:(?:the\s+)?(?:page|website|screen|site)\s*)?'
        r'(?:(?:of|at|from)\s+)?(https?://[^\s]+)?',
        re.IGNORECASE,
    ), {"url_group": "1"}),

    # Extract text from page
    ("extract_text", re.compile(
        r'(?:extract|scrape|get|grab|pull)\s+'
        r'(?:the\s+)?(?:text|content|data)\s+'
        r'(?:from\s+)?(https?://[^\s]+)?',
        re.IGNORECASE,
    ), {"url_group": "1"}),
]


class IntentParser:
    """Parses user messages into DaenaBot tool calls.

    Returns ``None`` if the message doesn't match any actionable pattern,
    meaning it should fall through to the normal LLM pipeline.
    """

    @classmethod
    def parse(cls, message: str) -> ToolCall | None:
        """Attempt to extract a DaenaBot tool call from a user message.

        Priority order (matches ``QueryUnderstandingService``):
            1. Browser (URL present → strong signal)
            2. Terminal (explicit run/execute prefix)
            3. File operations (list, read, create, write, move, delete)

        Returns:
            ``ToolCall`` if a match is found, ``None`` otherwise.
        """
        stripped = message.strip()
        if not stripped:
            return None

        # 1. Browser — URL presence is a strong signal
        result = cls._try_browser(stripped)
        if result:
            return result

        # 2. Terminal — explicit command prefix or backticks
        result = cls._try_terminal(stripped)
        if result:
            return result

        # 3. File operations
        result = cls._try_file(stripped)
        if result:
            return result

        return None

    # ── Agent-specific parsers ─────────────────────────────────

    @classmethod
    def _try_browser(cls, message: str) -> ToolCall | None:
        for operation, pattern, groups in _BROWSER_PATTERNS:
            m = pattern.search(message)
            if m:
                params: dict[str, Any] = {}
                url = (
                    m.group(int(groups.get("url_group", "1")))
                    if groups.get("url_group")
                    else None
                )
                if url:
                    params["url"] = url
                elif operation == "navigate":
                    continue  # navigate requires a URL
                return ToolCall(agent="browser", operation=operation, params=params)
        return None

    @classmethod
    def _try_terminal(cls, message: str) -> ToolCall | None:
        for pattern, groups in _TERMINAL_PATTERNS:
            m = pattern.search(message)
            if m:
                command = m.group(int(groups["command_group"])).strip()
                if command:
                    return ToolCall(
                        agent="terminal",
                        operation="execute_command",
                        params={"command": command},
                    )
        return None

    @classmethod
    def _try_file(cls, message: str) -> ToolCall | None:
        for operation, pattern, groups in _FILE_PATTERNS:
            m = pattern.search(message)
            if m:
                params = cls._extract_file_params(m, operation, groups)
                if params is not None:
                    return ToolCall(agent="file", operation=operation, params=params)
        return None

    @classmethod
    def _extract_file_params(
        cls,
        match: re.Match,
        operation: str,
        groups: dict[str, str],
    ) -> dict[str, Any] | None:
        """Extract and clean parameters from a file operation match."""
        params: dict[str, Any] = {}

        if operation in ("read_file", "list_directory", "delete_file"):
            raw = match.group(int(groups["path_group"])).strip()
            path = cls._clean_path(raw)
            if not path:
                return None
            params["path"] = path

        elif operation == "create_file":
            raw = match.group(int(groups["path_group"])).strip()
            path = cls._clean_path(raw)
            if not path:
                return None
            params["path"] = path
            content_group = groups.get("content_group")
            if content_group:
                content = match.group(int(content_group))
                params["content"] = content if content else ""
            else:
                params["content"] = ""

        elif operation == "write_file":
            path_raw = match.group(int(groups["path_group"])).strip()
            path = cls._clean_path(path_raw)
            if not path:
                return None
            params["path"] = path
            content_group = groups.get("content_group")
            if content_group:
                content = match.group(int(content_group))
                params["content"] = content if content else ""
            else:
                params["content"] = ""

        elif operation == "move_file":
            src = cls._clean_path(match.group(int(groups["source_group"])).strip())
            dst = cls._clean_path(match.group(int(groups["dest_group"])).strip())
            if not src or not dst:
                return None
            params["source"] = src
            params["destination"] = dst

        return params

    @staticmethod
    def _clean_path(raw: str) -> str:
        """Strip common natural-language debris from a path string."""
        # Remove trailing punctuation
        cleaned = raw.rstrip(".,;:!?")
        # Remove surrounding quotes
        if (cleaned.startswith('"') and cleaned.endswith('"')) or \
           (cleaned.startswith("'") and cleaned.endswith("'")):
            cleaned = cleaned[1:-1]
        # Remove common filler words at the start
        for prefix in ("the ", "this ", "that ", "file ", "directory ", "folder ", "dir "):
            if cleaned.lower().startswith(prefix):
                cleaned = cleaned[len(prefix):]
        return cleaned.strip()
