"""
Daena Tools Package

Tools that give Daena AI VP actual capabilities to:
- Scan and analyze codebase
- Inspect database
- Test API endpoints
- Execute CMP tools
- Connect to external AI (MCP)
- Control browser (Manus-style)
"""

from .code_scanner import scan_file, search_code, analyze_structure, list_directory
from .db_inspector import list_tables, describe_table, query_read_only, count_records
from .api_tester import test_endpoint, health_check, list_routes

# Import async modules separately to avoid issues
try:
    from .mcp_client import (
        discover_mcp_servers, connect_to_mcp, disconnect_mcp,
        send_to_mcp, list_connections, ask_antigravity, daena_mcp
    )
except ImportError:
    pass

try:
    from .browser_automation import (
        navigate, click, fill, screenshot, get_page_content,
        login, close_browser, daena_browser
    )
except ImportError:
    pass

__all__ = [
    # Code Scanner
    'scan_file',
    'search_code', 
    'analyze_structure',
    'list_directory',
    # DB Inspector
    'list_tables',
    'describe_table',
    'query_read_only',
    'count_records',
    # API Tester
    'test_endpoint',
    'health_check',
    'list_routes',
    # MCP Client
    'discover_mcp_servers',
    'connect_to_mcp',
    'disconnect_mcp',
    'send_to_mcp',
    'list_connections',
    'ask_antigravity',
    'daena_mcp',
    # Browser Automation
    'navigate',
    'click',
    'fill',
    'screenshot',
    'get_page_content',
    'login',
    'close_browser',
    'daena_browser',
]

