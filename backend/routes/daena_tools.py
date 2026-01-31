"""
Daena Tools API Routes

Endpoints for Daena to execute tools and analyze the system.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging

router = APIRouter(prefix="/api/v1/daena/tools", tags=["daena-tools"])
logger = logging.getLogger(__name__)


class ToolRequest(BaseModel):
    command: str
    tool: Optional[str] = None  # auto-detect if not specified


class FileRequest(BaseModel):
    path: str
    max_lines: Optional[int] = 500


class SearchRequest(BaseModel):
    query: str
    pattern: Optional[str] = "*.py"
    max_results: Optional[int] = 50


class DBQueryRequest(BaseModel):
    sql: str
    limit: Optional[int] = 100


class APITestRequest(BaseModel):
    path: str
    method: Optional[str] = "GET"
    body: Optional[Dict] = None


# === Code Scanner Routes ===

@router.post("/scan-file")
async def scan_file(req: FileRequest) -> Dict[str, Any]:
    """Scan/read a file from the codebase."""
    from backend.services.daena_tools.code_scanner import scan_file as _scan
    return _scan(req.path, req.max_lines or 500)


@router.post("/search-code")
async def search_code(req: SearchRequest) -> Dict[str, Any]:
    """Search the codebase for a pattern."""
    from backend.services.daena_tools.code_scanner import search_code as _search
    return _search(req.query, req.pattern or "*.py", req.max_results or 50)


@router.get("/list-directory")
async def list_directory(path: str = ".") -> Dict[str, Any]:
    """List contents of a directory."""
    from backend.services.daena_tools.code_scanner import list_directory as _list
    return _list(path)


@router.get("/analyze-structure")
async def analyze_structure(path: str = ".") -> Dict[str, Any]:
    """Analyze the structure of a directory."""
    from backend.services.daena_tools.code_scanner import analyze_structure as _analyze
    return _analyze(path)


# === Database Inspector Routes ===

@router.get("/db/tables")
async def db_tables() -> Dict[str, Any]:
    """List all database tables."""
    from backend.services.daena_tools.db_inspector import list_tables
    return list_tables()


@router.get("/db/describe/{table_name}")
async def db_describe(table_name: str) -> Dict[str, Any]:
    """Describe a database table schema."""
    from backend.services.daena_tools.db_inspector import describe_table
    return describe_table(table_name)


@router.get("/db/count/{table_name}")
async def db_count(table_name: str) -> Dict[str, Any]:
    """Count records in a table."""
    from backend.services.daena_tools.db_inspector import count_records
    return count_records(table_name)


@router.post("/db/query")
async def db_query(req: DBQueryRequest) -> Dict[str, Any]:
    """Execute a read-only SQL query."""
    from backend.services.daena_tools.db_inspector import query_read_only
    return query_read_only(req.sql, req.limit or 100)


# === API Tester Routes ===

@router.post("/test-endpoint")
async def test_endpoint(req: APITestRequest) -> Dict[str, Any]:
    """Test an API endpoint."""
    from backend.services.daena_tools.api_tester import test_endpoint as _test
    return await _test(req.path, req.method or "GET", req.body)


@router.get("/health-check")
async def api_health_check() -> Dict[str, Any]:
    """Run health check on all major endpoints."""
    from backend.services.daena_tools.api_tester import health_check
    return await health_check()


@router.get("/routes")
async def list_routes() -> Dict[str, Any]:
    """List all registered API routes."""
    from backend.services.daena_tools.api_tester import list_routes as _list
    return _list()


# === Unified Executor ===

@router.post("/execute")
async def execute_daena_command(req: ToolRequest) -> Dict[str, Any]:
    """
    Execute a natural language command using the appropriate tool.
    
    Auto-detects which tool to use based on the command.
    
    Examples:
        - "scan backend/routes/daena.py"
        - "search getChatHistory"
        - "show tables"
        - "describe departments"
        - "health check"
        - "test /api/v1/brain/status"
        - "discover servers" (MCP)
        - "go to https://google.com" (Browser)
        - "click at 100 200" / "type on desktop hello" (Desktop automation)
    """
    command_raw = req.command.strip()
    command = command_raw.lower()

    # Try chat-style tool detection first (desktop, action_execute, etc.)
    try:
        from backend.routes.daena import detect_and_execute_tool
        tool_result = await detect_and_execute_tool(command_raw)
        if tool_result is not None:
            if "error" in tool_result:
                return {"success": False, "error": tool_result["error"]}
            return {"success": True, "result": tool_result.get("result", tool_result)}
    except Exception as e:
        logger.debug(f"detect_and_execute_tool skipped: {e}")

    # Determine which tool to use
    if req.tool:
        tool = req.tool
    else:
        # Auto-detect (skip "click" for desktop: click at X Y is handled above)
        if any(kw in command for kw in ["scan ", "search ", "find ", "list ", "ls ", "analyze"]):
            tool = "code"
        elif any(kw in command for kw in ["table", "describe ", "count ", "select ", "schema"]):
            tool = "db"
        elif any(kw in command for kw in ["test ", "health", "route", "get ", "post "]):
            tool = "api"
        elif any(kw in command for kw in ["mcp", "server", "connect", "antigravity", "ollama"]):
            tool = "mcp"
        elif any(kw in command for kw in ["go to", "navigate", "fill", "screenshot", "browser", "login"]) or (
            "click" in command and " at " not in command
        ):
            tool = "browser"
        else:
            # Default to code scanner
            tool = "code"

    try:
        if tool == "code":
            from backend.services.daena_tools.code_scanner import daena_scan
            return await daena_scan(req.command)
        elif tool == "db":
            from backend.services.daena_tools.db_inspector import daena_db
            return await daena_db(req.command)
        elif tool == "api":
            from backend.services.daena_tools.api_tester import daena_api
            return await daena_api(req.command)
        elif tool == "mcp":
            from backend.services.daena_tools.mcp_client import daena_mcp
            return await daena_mcp(req.command)
        elif tool == "browser":
            from backend.services.daena_tools.browser_automation import daena_browser
            return await daena_browser(req.command)
        else:
            return {"success": False, "error": f"Unknown tool: {tool}"}
    except Exception as e:
        logger.error(f"execute_daena_command error: {e}")
        return {"success": False, "error": str(e)}


# === Capabilities ===

@router.get("/capabilities")
async def get_capabilities() -> Dict[str, Any]:
    """Get Daena's tool capabilities."""
    return {
        "success": True,
        "tools": {
            "code_scanner": {
                "description": "Scan, search, and analyze the codebase",
                "commands": ["scan <file>", "search <query>", "list <dir>", "analyze <dir>"]
            },
            "db_inspector": {
                "description": "Inspect the database (read-only)",
                "commands": ["show tables", "describe <table>", "count <table>", "SELECT queries"]
            },
            "api_tester": {
                "description": "Test API endpoints",
                "commands": ["health check", "list routes", "test <path>", "post <path> {json}"]
            },
            "mcp_client": {
                "description": "Connect to external AI servers (Antigravity, Ollama)",
                "commands": ["discover servers", "connect <server>", "list connections", "ask <server> <question>"]
            },
            "browser": {
                "description": "Manus-style browser automation",
                "commands": ["go to <url>", "click <element>", "fill <field> with <value>", "screenshot", "login <url> <user> <pass>"]
            },
            "cmp_tools": {
                "description": "Execute registered CMP tools",
                "endpoint": "/api/v1/cmp/tools/execute"
            }
        }
    }


# === MCP Client Routes ===

class MCPConnectRequest(BaseModel):
    server_id: str
    custom_url: Optional[str] = None


class MCPSendRequest(BaseModel):
    server_id: str
    action: str
    payload: Dict[str, Any] = {}


@router.get("/mcp/discover")
async def mcp_discover() -> Dict[str, Any]:
    """Discover available MCP servers."""
    from backend.services.daena_tools.mcp_client import discover_mcp_servers
    return await discover_mcp_servers()


@router.post("/mcp/connect")
async def mcp_connect(req: MCPConnectRequest) -> Dict[str, Any]:
    """Connect to an MCP server."""
    from backend.services.daena_tools.mcp_client import connect_to_mcp
    return await connect_to_mcp(req.server_id, req.custom_url)


@router.delete("/mcp/disconnect/{server_id}")
async def mcp_disconnect(server_id: str) -> Dict[str, Any]:
    """Disconnect from an MCP server."""
    from backend.services.daena_tools.mcp_client import disconnect_mcp
    return await disconnect_mcp(server_id)


@router.get("/mcp/connections")
async def mcp_list_connections() -> Dict[str, Any]:
    """List active MCP connections."""
    from backend.services.daena_tools.mcp_client import list_connections
    return list_connections()


@router.post("/mcp/send")
async def mcp_send(req: MCPSendRequest) -> Dict[str, Any]:
    """Send a request to an MCP server."""
    from backend.services.daena_tools.mcp_client import send_to_mcp
    return await send_to_mcp(req.server_id, req.action, req.payload)


# === Browser Automation Routes ===

class BrowserNavigateRequest(BaseModel):
    url: str


class BrowserClickRequest(BaseModel):
    selector: str


class BrowserFillRequest(BaseModel):
    selector: str
    value: str


class BrowserLoginRequest(BaseModel):
    url: str
    username: str
    password: str
    username_field: Optional[str] = "username"
    password_field: Optional[str] = "password"
    submit_button: Optional[str] = "submit"


@router.post("/browser/navigate")
async def browser_navigate(req: BrowserNavigateRequest) -> Dict[str, Any]:
    """Navigate to a URL."""
    from backend.services.daena_tools.browser_automation import navigate
    return await navigate(req.url)


@router.post("/browser/click")
async def browser_click(req: BrowserClickRequest) -> Dict[str, Any]:
    """Click an element."""
    from backend.services.daena_tools.browser_automation import click
    return await click(req.selector)


@router.post("/browser/fill")
async def browser_fill(req: BrowserFillRequest) -> Dict[str, Any]:
    """Fill a form field."""
    from backend.services.daena_tools.browser_automation import fill
    return await fill(req.selector, req.value)


@router.get("/browser/screenshot")
async def browser_screenshot(name: str = "screenshot") -> Dict[str, Any]:
    """Take a screenshot."""
    from backend.services.daena_tools.browser_automation import screenshot
    return await screenshot(name)


@router.get("/browser/content")
async def browser_content() -> Dict[str, Any]:
    """Get current page content."""
    from backend.services.daena_tools.browser_automation import get_page_content
    return await get_page_content()


@router.post("/browser/login")
async def browser_login(req: BrowserLoginRequest) -> Dict[str, Any]:
    """Automated login to a page."""
    from backend.services.daena_tools.browser_automation import login
    return await login(
        req.url, req.username, req.password,
        req.username_field, req.password_field, req.submit_button
    )


@router.post("/browser/close")
async def browser_close() -> Dict[str, Any]:
    """Close the browser session."""
    from backend.services.daena_tools.browser_automation import close_browser
    return await close_browser()

