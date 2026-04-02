"""ToolSchemaBuilder -- dynamically builds LLM function definitions.

Collects tools from ALL sources and builds a unified schema that gets
injected into the LLM's system prompt. This is what enables the LLM
to autonomously decide WHEN to call tools, instead of relying on
regex pattern matching.

Sources:
    1. System access (file system, terminal, network, desktop)
    2. DaenaBot agents (browser, MCP)
    3. Connected integrations (Gmail, Calendar, Notion)
    4. MCP servers (auto-discovered via MCPRegistry)
    5. Department workflows
    6. Desktop control (Windows-MCP: mouse, keyboard, screen)

The schema follows the OpenAI function-calling format, which is
supported by Ollama, Claude, and most LLM providers.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.core.logging import get_logger

logger = get_logger(__name__)


def build_tool_schema(
    *,
    include_daenabot: bool = True,
    include_integrations: bool = True,
    include_system: bool = True,
    include_workflows: bool = True,
    include_mcp: bool = True,
    include_desktop: bool = True,
    connected_providers: list[str] | None = None,
    mcp_registry: Any | None = None,
    agi_mode: bool = False,
) -> list[dict[str, Any]]:
    """Build the full tool schema for LLM function calling.

    Args:
        include_daenabot: Include browser/MCP agent tools.
        include_integrations: Include Gmail/Calendar/Notion tools.
        include_system: Include system access tools (file, terminal, network).
        include_workflows: Include department workflow triggers.
        include_mcp: Include auto-discovered MCP server tools.
        include_desktop: Include desktop control tools (mouse, keyboard, screen).
        connected_providers: List of connected provider slugs (only include those).
        mcp_registry: MCPRegistry instance for auto-discovered tools.
        agi_mode: If True, include all tools without safety filtering.

    Returns:
        List of function definitions in OpenAI tool format.
    """
    tools: list[dict[str, Any]] = []

    if include_system:
        tools.extend(_system_tools())

    if include_daenabot:
        tools.extend(_daenabot_tools())

    if include_desktop:
        tools.extend(_desktop_tools())

    if include_integrations:
        tools.extend(_integration_tools(connected_providers))

    if include_workflows:
        tools.extend(_workflow_tools())

    if include_mcp and mcp_registry is not None:
        tools.extend(_mcp_tools(mcp_registry))

    return tools


def build_tool_prompt(tools: list[dict[str, Any]]) -> str:
    """Convert tool definitions into a system prompt section.

    Uses a clear format that most LLMs can parse for function calling.
    """
    if not tools:
        return ""

    lines = [
        "AVAILABLE TOOLS:",
        "You can call these tools by responding with a JSON block:",
        '```tool_call',
        '{"tool": "tool_name", "params": {"param1": "value1"}}',
        '```',
        "",
        "After each tool call, you will receive the result and can continue reasoning.",
        "You can chain multiple tool calls to complete complex tasks.",
        "Call tools when you need real data -- do not guess or make up answers.",
        "When a task requires multiple steps, call tools one at a time and use results to inform next steps.",
        "",
    ]

    for tool in tools:
        name = tool["name"]
        desc = tool["description"]
        params = tool.get("parameters", {})
        param_list = params.get("properties", {})

        lines.append(f"## {name}")
        lines.append(f"  {desc}")
        if param_list:
            required = params.get("required", [])
            for pname, pinfo in param_list.items():
                req = " (required)" if pname in required else ""
                lines.append(f"  - {pname}: {pinfo.get('description', pinfo.get('type', ''))}{req}")
        lines.append("")

    return "\n".join(lines)


def parse_tool_calls(llm_response: str) -> list[dict[str, Any]]:
    """Parse tool calls from LLM response text.

    Looks for ```tool_call blocks with JSON inside.
    Also handles bare JSON objects with "tool" key.

    Returns:
        List of dicts with "tool" and "params" keys.
    """
    import json
    import re

    calls: list[dict[str, Any]] = []

    # Pattern 1: ```tool_call ... ```
    pattern = r'```tool_call\s*\n?(.*?)\n?```'
    matches = re.findall(pattern, llm_response, re.DOTALL)
    for match in matches:
        try:
            data = json.loads(match.strip())
            if isinstance(data, dict) and "tool" in data:
                calls.append({
                    "tool": data["tool"],
                    "params": data.get("params", data.get("arguments", {})),
                })
        except json.JSONDecodeError:
            continue

    # Pattern 2: {"tool": "name", "params": {...}} anywhere in text
    if not calls:
        json_pattern = r'\{[^{}]*"tool"\s*:\s*"[^"]+"\s*[,}][^{}]*\}'
        for match in re.finditer(json_pattern, llm_response):
            try:
                data = json.loads(match.group())
                if "tool" in data:
                    calls.append({
                        "tool": data["tool"],
                        "params": data.get("params", data.get("arguments", {})),
                    })
            except json.JSONDecodeError:
                continue

    # Pattern 3: Nested JSON with tool_call wrapper
    if not calls:
        try:
            # Try parsing the entire response as JSON
            data = json.loads(llm_response.strip())
            if isinstance(data, dict) and "tool" in data:
                calls.append({
                    "tool": data["tool"],
                    "params": data.get("params", {}),
                })
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "tool" in item:
                        calls.append({
                            "tool": item["tool"],
                            "params": item.get("params", {}),
                        })
        except (json.JSONDecodeError, ValueError):
            pass

    return calls


# ── Tool Definitions ──────────────────────────────────────────


def _system_tools() -> list[dict[str, Any]]:
    """Core system access tools -- file system, terminal, network."""
    return [
        {
            "name": "read_file",
            "description": "Read a file from the filesystem. Use this to examine code, configs, logs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path"},
                },
                "required": ["path"],
            },
        },
        {
            "name": "write_file",
            "description": "Write content to a file. Creates parent directories if needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to write to"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
        },
        {
            "name": "list_directory",
            "description": "List files and folders in a directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path"},
                },
                "required": ["path"],
            },
        },
        {
            "name": "search_files",
            "description": "Search for files matching a glob pattern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern (e.g. '**/*.py')"},
                    "root": {"type": "string", "description": "Root directory to search from"},
                },
                "required": ["pattern"],
            },
        },
        {
            "name": "run_command",
            "description": "Execute a shell command. Use for: running tests, installing packages, git operations, builds, any CLI tool.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "working_directory": {"type": "string", "description": "Directory to run in (optional)"},
                },
                "required": ["command"],
            },
        },
        {
            "name": "run_python",
            "description": "Execute Python code directly. Use for data processing, calculations, scripting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string", "description": "Python code to execute"},
                },
                "required": ["code"],
            },
        },
        {
            "name": "delete_file",
            "description": "Delete (archive) a file. Archives to .archive/ for safety.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path to delete"},
                },
                "required": ["path"],
            },
        },
        {
            "name": "move_file",
            "description": "Move or rename a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Source file path"},
                    "destination": {"type": "string", "description": "Destination path"},
                },
                "required": ["source", "destination"],
            },
        },
        {
            "name": "copy_file",
            "description": "Copy a file to a new location.",
            "parameters": {
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Source file path"},
                    "destination": {"type": "string", "description": "Destination path"},
                },
                "required": ["source", "destination"],
            },
        },
        {
            "name": "http_get",
            "description": "Make an HTTP GET request. Use for fetching web pages, APIs, data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to request"},
                },
                "required": ["url"],
            },
        },
        {
            "name": "http_post",
            "description": "Make an HTTP POST request. Use for calling APIs, webhooks, sending data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to post to"},
                    "json_body": {"type": "object", "description": "JSON payload"},
                },
                "required": ["url"],
            },
        },
        {
            "name": "web_search",
            "description": "Search the web for information. Use when you need current data, documentation, or answers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "install_package",
            "description": "Install a package via pip or npm.",
            "parameters": {
                "type": "object",
                "properties": {
                    "package": {"type": "string", "description": "Package name"},
                    "manager": {"type": "string", "description": "Package manager: 'pip' or 'npm' (default: pip)"},
                },
                "required": ["package"],
            },
        },
    ]


def _daenabot_tools() -> list[dict[str, Any]]:
    """DaenaBot agent tools (browser automation, MCP bridge)."""
    return [
        {
            "name": "browser_navigate",
            "description": "Open a URL in the browser and get the page content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to navigate to"},
                },
                "required": ["url"],
            },
        },
        {
            "name": "browser_screenshot",
            "description": "Take a screenshot of a webpage and get it as base64.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to screenshot"},
                },
                "required": ["url"],
            },
        },
        {
            "name": "browser_extract_text",
            "description": "Extract all text content from a webpage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to extract text from"},
                },
                "required": ["url"],
            },
        },
        {
            "name": "browser_fill_form",
            "description": "Fill a form field on a webpage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL of the page"},
                    "selector": {"type": "string", "description": "CSS selector of the input field"},
                    "value": {"type": "string", "description": "Value to fill"},
                },
                "required": ["url", "selector", "value"],
            },
        },
        {
            "name": "browser_click",
            "description": "Click an element on a webpage.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL of the page"},
                    "selector": {"type": "string", "description": "CSS selector of the element to click"},
                },
                "required": ["url", "selector"],
            },
        },
        {
            "name": "mcp_call",
            "description": "Call a tool on an MCP server. Use this to access external MCP capabilities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "tool_name": {"type": "string", "description": "MCP tool name"},
                    "arguments": {"type": "object", "description": "Tool arguments"},
                    "server_url": {"type": "string", "description": "MCP server URL (optional, uses default)"},
                },
                "required": ["tool_name"],
            },
        },
    ]


def _desktop_tools() -> list[dict[str, Any]]:
    """Desktop control tools -- mouse, keyboard, screen capture.

    These bridge to Windows-MCP / Desktop Commander for full computer
    control with governance. This is what makes Daena an OpenClaw-class
    agent: she can see the screen, click, type, scroll.
    """
    return [
        {
            "name": "desktop_screenshot",
            "description": "Take a screenshot of the entire desktop or a specific window. Returns base64 image.",
            "parameters": {
                "type": "object",
                "properties": {
                    "window_title": {"type": "string", "description": "Window title to capture (optional, captures full screen if omitted)"},
                },
            },
        },
        {
            "name": "desktop_click",
            "description": "Click at coordinates on the screen. Use after taking a screenshot to determine positions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate"},
                    "y": {"type": "integer", "description": "Y coordinate"},
                    "button": {"type": "string", "description": "Mouse button: 'left', 'right', 'middle' (default: left)"},
                    "double_click": {"type": "boolean", "description": "Double-click if true"},
                },
                "required": ["x", "y"],
            },
        },
        {
            "name": "desktop_type",
            "description": "Type text using the keyboard. Works in any focused application.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type"},
                },
                "required": ["text"],
            },
        },
        {
            "name": "desktop_hotkey",
            "description": "Press a keyboard shortcut (e.g., 'ctrl+c', 'alt+tab', 'ctrl+shift+s').",
            "parameters": {
                "type": "object",
                "properties": {
                    "keys": {"type": "string", "description": "Key combination (e.g., 'ctrl+c', 'alt+f4')"},
                },
                "required": ["keys"],
            },
        },
        {
            "name": "desktop_scroll",
            "description": "Scroll the mouse wheel at the current position or specified coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "description": "'up' or 'down'"},
                    "amount": {"type": "integer", "description": "Scroll amount (default: 3)"},
                    "x": {"type": "integer", "description": "X coordinate (optional)"},
                    "y": {"type": "integer", "description": "Y coordinate (optional)"},
                },
                "required": ["direction"],
            },
        },
        {
            "name": "desktop_move_mouse",
            "description": "Move the mouse cursor to specific coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "integer", "description": "X coordinate"},
                    "y": {"type": "integer", "description": "Y coordinate"},
                },
                "required": ["x", "y"],
            },
        },
        {
            "name": "computer_use",
            "description": "Autonomously control the computer to complete a visual task. Takes screenshots, understands UI elements via vision AI, and performs clicks/typing/scrolling to accomplish the goal. Use this for tasks that require interacting with desktop applications (not web browsers -- use browser tools for those).",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "What to accomplish on the desktop (e.g., 'Open VS Code and create a new file called app.py')"},
                    "max_steps": {"type": "integer", "description": "Maximum number of screenshot-action cycles (default: 10)"},
                },
                "required": ["task"],
            },
        },
    ]


def _integration_tools(connected_providers: list[str] | None = None) -> list[dict[str, Any]]:
    """Integration tools from connected services."""
    tools = []

    gmail_tools = [
        {
            "name": "gmail_search",
            "description": "Search Gmail inbox. Use Gmail query syntax (e.g. 'is:unread', 'from:user@example.com', 'subject:meeting').",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Gmail search query"},
                    "max_results": {"type": "integer", "description": "Max results (default 10)"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "gmail_read",
            "description": "Read a specific email by its message ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "Gmail message ID"},
                },
                "required": ["message_id"],
            },
        },
        {
            "name": "gmail_send",
            "description": "Send an email. CAUTION: This actually sends the email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email address"},
                    "subject": {"type": "string", "description": "Email subject"},
                    "body": {"type": "string", "description": "Email body text"},
                },
                "required": ["to", "subject", "body"],
            },
        },
        {
            "name": "gmail_draft",
            "description": "Create a draft email without sending it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email"},
                    "subject": {"type": "string", "description": "Subject line"},
                    "body": {"type": "string", "description": "Email body"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    ]

    calendar_tools = [
        {
            "name": "calendar_list_events",
            "description": "List upcoming calendar events for the next 7 days.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {"type": "integer", "description": "Max events (default 20)"},
                    "query": {"type": "string", "description": "Search term (optional)"},
                },
            },
        },
        {
            "name": "calendar_create_event",
            "description": "Create a new calendar event.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Event title"},
                    "start": {"type": "string", "description": "Start time (ISO format)"},
                    "end": {"type": "string", "description": "End time (ISO format)"},
                    "description": {"type": "string", "description": "Event description"},
                    "attendees": {"type": "array", "description": "List of attendee emails"},
                },
                "required": ["summary", "start", "end"],
            },
        },
        {
            "name": "calendar_find_free_time",
            "description": "Find available time slots in the calendar.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    ]

    notion_tools = [
        {
            "name": "notion_search",
            "description": "Search the Notion workspace for pages and databases.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "notion_read_page",
            "description": "Read a Notion page with its content.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Notion page ID"},
                },
                "required": ["page_id"],
            },
        },
        {
            "name": "notion_create_page",
            "description": "Create a new page in Notion.",
            "parameters": {
                "type": "object",
                "properties": {
                    "parent_id": {"type": "string", "description": "Parent page or database ID"},
                    "title": {"type": "string", "description": "Page title"},
                    "content": {"type": "string", "description": "Page content"},
                },
                "required": ["parent_id", "title"],
            },
        },
    ]

    # Only include tools for connected providers
    if connected_providers is None or "gmail" in connected_providers:
        tools.extend(gmail_tools)
    if connected_providers is None or "google-calendar" in connected_providers:
        tools.extend(calendar_tools)
    if connected_providers is None or "notion" in connected_providers:
        tools.extend(notion_tools)

    return tools


def _workflow_tools() -> list[dict[str, Any]]:
    """Department workflow trigger tools."""
    return [
        {
            "name": "run_workflow",
            "description": "Run a department workflow. Available: ops.daily_briefing, ops.task_summary, mkt.draft_content, mkt.competitor_watch, sales.lead_research, sales.outreach_draft, eng.test_status, fin.cost_report, research.competitive_scan, sec.access_audit",
            "parameters": {
                "type": "object",
                "properties": {
                    "workflow_id": {"type": "string", "description": "Workflow ID to run"},
                },
                "required": ["workflow_id"],
            },
        },
    ]


def _mcp_tools(mcp_registry: Any) -> list[dict[str, Any]]:
    """Auto-discovered MCP server tools.

    Pulls tools from the MCPRegistry and converts them to the
    OpenAI function-calling format. This means any MCP server
    connected to Daena automatically becomes available to the LLM.
    """
    tools: list[dict[str, Any]] = []

    try:
        registered_tools = mcp_registry.list_tools()
        for mcp_tool in registered_tools:
            name = mcp_tool.get("name", "")
            if not name:
                continue

            # Prefix with mcp_ to avoid name collisions
            schema_name = f"mcp_{name}" if not name.startswith("mcp_") else name

            tool_def: dict[str, Any] = {
                "name": schema_name,
                "description": mcp_tool.get("description", f"MCP tool: {name}"),
            }

            # Convert MCP input schema to OpenAI parameter format
            input_schema = mcp_tool.get("input_schema", {})
            if input_schema:
                tool_def["parameters"] = input_schema
            else:
                tool_def["parameters"] = {"type": "object", "properties": {}}

            tools.append(tool_def)

        if tools:
            logger.info("tool_schema.mcp_tools_added", count=len(tools))

    except Exception as exc:
        logger.warning("tool_schema.mcp_discovery_failed", error=str(exc))

    return tools


# ── Tool Name Mapping ──────────────────────────────────────────
# Maps schema tool names to execution dispatch paths

TOOL_DISPATCH_MAP: dict[str, tuple[str, str]] = {
    # System tools -> agent_prefix.operation
    "read_file": ("file", "read_file"),
    "write_file": ("file", "write_file"),
    "list_directory": ("file", "list_directory"),
    "search_files": ("file", "search_files"),
    "delete_file": ("file", "delete_file"),
    "move_file": ("file", "move_file"),
    "copy_file": ("file", "copy_file"),
    "run_command": ("terminal", "execute_command"),
    "run_python": ("terminal", "run_python"),
    "install_package": ("terminal", "install_package"),
    "web_search": ("network", "web_search"),
    "http_get": ("network", "http_get"),
    "http_post": ("network", "http_post"),
    # Browser tools
    "browser_navigate": ("browser", "navigate"),
    "browser_screenshot": ("browser", "screenshot"),
    "browser_extract_text": ("browser", "extract_text"),
    "browser_fill_form": ("browser", "fill_form"),
    "browser_click": ("browser", "click_element"),
    # Desktop control tools
    "desktop_screenshot": ("desktop", "screenshot"),
    "desktop_click": ("desktop", "click"),
    "desktop_type": ("desktop", "type_text"),
    "desktop_hotkey": ("desktop", "hotkey"),
    "desktop_scroll": ("desktop", "scroll"),
    "desktop_move_mouse": ("desktop", "move_mouse"),
    "computer_use": ("vision", "execute_task"),
    # MCP bridge
    "mcp_call": ("mcp", "call_tool"),
    # Gmail
    "gmail_search": ("gmail", "search_emails"),
    "gmail_read": ("gmail", "read_email"),
    "gmail_send": ("gmail", "send_email"),
    "gmail_draft": ("gmail", "create_draft"),
    # Calendar
    "calendar_list_events": ("calendar", "list_events"),
    "calendar_create_event": ("calendar", "create_event"),
    "calendar_find_free_time": ("calendar", "find_free_time"),
    # Notion
    "notion_search": ("notion", "search_pages"),
    "notion_read_page": ("notion", "read_page"),
    "notion_create_page": ("notion", "create_page"),
    # Workflows
    "run_workflow": ("workflow", "run"),
}


def resolve_tool_call(
    tool_name: str,
    params: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Resolve a schema tool name to an execution dispatch path.

    Returns:
        Tuple of (qualified_tool_name, resolved_params)
        where qualified_tool_name is "agent.operation" format.
    """
    if tool_name in TOOL_DISPATCH_MAP:
        prefix, operation = TOOL_DISPATCH_MAP[tool_name]
        return f"{prefix}.{operation}", params

    # Handle auto-discovered MCP tools (prefixed with mcp_)
    if tool_name.startswith("mcp_"):
        real_name = tool_name[4:]  # Strip mcp_ prefix
        return "mcp.call_tool", {"tool_name": real_name, "arguments": params}

    # Fallback: assume it's already qualified
    return tool_name, params
