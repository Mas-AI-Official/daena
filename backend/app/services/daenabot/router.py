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

# ── Vision Browser patterns (AI-powered, no selectors needed) ──

_VISION_BROWSER_PATTERNS: list[tuple[re.Pattern[str], str, Any, str]] = [
    # "research <url>" or "analyze website <url>"
    (
        re.compile(
            r"(?:research|analyze|study|investigate|review)\s+(?:the\s+)?(?:website|page|site)?\s*(https?://\S+)",
            re.IGNORECASE,
        ),
        "vision_browser.research_url",
        lambda m: {"url": m.group(1).strip(), "question": ""},
        "Research {url}",
    ),
    # "what's on <url>" or "what does <url> show"
    (
        re.compile(
            r"(?:what(?:'s| is| does))\s+(?:on|at|the)\s+(https?://\S+)",
            re.IGNORECASE,
        ),
        "vision_browser.research_url",
        lambda m: {"url": m.group(1).strip(), "question": "What is on this page?"},
        "Analyze {url}",
    ),
    # "fill out the form at <url> with ..." (smart form filling)
    (
        re.compile(
            r"(?:fill\s+(?:out|in)\s+(?:the\s+)?form)\s+(?:at|on)\s+(https?://\S+)",
            re.IGNORECASE,
        ),
        "vision_browser.fill_form_smart",
        lambda m: {"url": m.group(1).strip(), "form_data": {}, "submit": False},
        "Fill form at {url}",
    ),
    # "browse <url> and <goal>" (autonomous browsing with a goal)
    (
        re.compile(
            r"(?:browse|explore|use)\s+(https?://\S+)\s+(?:and|to)\s+(.+)",
            re.IGNORECASE,
        ),
        "vision_browser.browse_and_act",
        lambda m: {"url": m.group(1).strip(), "goal": m.group(2).strip()},
        "Browse {url} and {goal}",
    ),
    # Generic "do <task> on <url>"
    (
        re.compile(
            r"(?:on|at)\s+(https?://\S+)\s*[,:]\s*(.+)",
            re.IGNORECASE,
        ),
        "vision_browser.browse_and_act",
        lambda m: {"url": m.group(1).strip(), "goal": m.group(2).strip()},
        "Act on {url}: {goal}",
    ),
]

# ── Web Crawler patterns (data extraction and research) ──

_WEB_CRAWLER_PATTERNS: list[tuple[re.Pattern[str], str, Any, str]] = [
    # "crawl <url>" or "scrape site <url>"
    (
        re.compile(
            r"(?:crawl|deep\s*crawl|spider|scrape\s+(?:the\s+)?site)\s+(https?://\S+)",
            re.IGNORECASE,
        ),
        "web_crawler.deep_crawl",
        lambda m: {"url": m.group(1).strip(), "max_pages": 5},
        "Deep crawl {url}",
    ),
    # "extract data from <url>"
    (
        re.compile(
            r"(?:extract|pull|get)\s+(?:the\s+)?(?:data|info(?:rmation)?|content|details?)\s+(?:from|off|on)\s+(https?://\S+)",
            re.IGNORECASE,
        ),
        "web_crawler.extract_page",
        lambda m: {"url": m.group(1).strip()},
        "Extract data from {url}",
    ),
    # "read page <url>"
    (
        re.compile(
            r"(?:read|fetch|download)\s+(?:the\s+)?(?:page|content)\s+(?:at|from|of)\s+(https?://\S+)",
            re.IGNORECASE,
        ),
        "web_crawler.extract_page",
        lambda m: {"url": m.group(1).strip()},
        "Read page {url}",
    ),
    # "research <topic> from <url1>, <url2>"
    (
        re.compile(
            r"research\s+(.+?)\s+(?:from|using)\s+(https?://\S+(?:\s*,\s*https?://\S+)*)",
            re.IGNORECASE,
        ),
        "web_crawler.research_topic",
        lambda m: {
            "topic": m.group(1).strip(),
            "urls": [u.strip() for u in m.group(2).split(",")],
        },
        "Research {topic}",
    ),
]

# ── Integration patterns (Gmail, Calendar, Notion) ───────────

_GMAIL_PATTERNS: list[tuple[re.Pattern[str], str, Any, str]] = [
    (
        re.compile(
            r"(?:search|find|look\s+for)\s+(?:my\s+)?(?:emails?|messages?|mail)\s+(?:about|from|with|regarding)\s+(.+)",
            re.IGNORECASE,
        ),
        "gmail.search_emails",
        lambda m: {"query": m.group(1).strip()},
        "Search emails: {query}",
    ),
    (
        re.compile(
            r"(?:check|read|show)\s+(?:my\s+)?(?:unread\s+)?(?:emails?|inbox|mail)",
            re.IGNORECASE,
        ),
        "gmail.search_emails",
        lambda m: {"query": "is:unread", "max_results": 10},
        "Check unread emails",
    ),
    (
        re.compile(
            r"(?:send|compose|write)\s+(?:an?\s+)?email\s+to\s+(\S+@\S+)\s+(?:about|subject|re)\s+(.+)",
            re.IGNORECASE,
        ),
        "gmail.send_email",
        lambda m: {"to": m.group(1).strip(), "subject": m.group(2).strip(), "body": ""},
        "Send email to {to}: {subject}",
    ),
    (
        re.compile(
            r"(?:draft|prepare)\s+(?:an?\s+)?email\s+to\s+(\S+@\S+)\s+(?:about|subject|re)\s+(.+)",
            re.IGNORECASE,
        ),
        "gmail.create_draft",
        lambda m: {"to": m.group(1).strip(), "subject": m.group(2).strip(), "body": ""},
        "Draft email to {to}: {subject}",
    ),
]

_CALENDAR_PATTERNS: list[tuple[re.Pattern[str], str, Any, str]] = [
    (
        re.compile(
            r"(?:check|show|list|what'?s?\s+on)\s+(?:my\s+)?(?:calendar|schedule|events?|agenda)",
            re.IGNORECASE,
        ),
        "calendar.list_events",
        lambda m: {},
        "List upcoming events",
    ),
    (
        re.compile(
            r"(?:schedule|create|add|book)\s+(?:a\s+)?(?:meeting|event|call)\s+(?:with\s+)?(.+?)(?:\s+(?:on|at|for)\s+(.+))?$",
            re.IGNORECASE,
        ),
        "calendar.create_event",
        lambda m: {"summary": m.group(1).strip(), "start": m.group(2) or "", "end": ""},
        "Schedule: {summary}",
    ),
    (
        re.compile(
            r"(?:when\s+am\s+I|find)\s+(?:free|available)",
            re.IGNORECASE,
        ),
        "calendar.find_free_time",
        lambda m: {},
        "Find free time slots",
    ),
]

_NOTION_PATTERNS: list[tuple[re.Pattern[str], str, Any, str]] = [
    (
        re.compile(
            r"(?:search|find|look\s+up)\s+(?:in\s+)?notion\s+(?:for\s+)?(.+)",
            re.IGNORECASE,
        ),
        "notion.search_pages",
        lambda m: {"query": m.group(1).strip()},
        "Search Notion: {query}",
    ),
    (
        re.compile(
            r"(?:create|add|new)\s+(?:a\s+)?(?:notion\s+)?(?:page|doc|document)\s+(?:called|titled|named)\s+(.+)",
            re.IGNORECASE,
        ),
        "notion.create_page",
        lambda m: {"title": m.group(1).strip(), "parent_id": "", "content": ""},
        "Create Notion page: {title}",
    ),
]

# Priority order: terminal > integration > vision_browser > web_crawler > file > browser
# Integration patterns checked before file patterns to avoid "check my email"
# matching file "check" operations. Vision/crawler patterns checked before
# basic browser to prefer AI-powered navigation for research tasks.
_ALL_PATTERNS = (
    _TERMINAL_PATTERNS
    + _GMAIL_PATTERNS
    + _CALENDAR_PATTERNS
    + _NOTION_PATTERNS
    + _VISION_BROWSER_PATTERNS
    + _WEB_CRAWLER_PATTERNS
    + _FILE_PATTERNS
    + _BROWSER_PATTERNS
)


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
