"""
Department Tools Mapping - Defines which tools are available to each department.
"""
from typing import Dict, List

DEPARTMENT_TOOLS: Dict[str, List[str]] = {
    "engineering": [
        "git_status", 
        "git_diff", 
        "filesystem_read", 
        "filesystem_write", 
        "apply_patch", 
        "shell_exec", 
        "windows_node_safe_shell_exec", 
        "run_tests", 
        "workspace_index", 
        "workspace_search",
        "repo_scan"
    ],
    "product": [
        "workspace_index", 
        "workspace_search", 
        "web_scrape_bs4", 
        "browser_automation_selenium",
        "screenshot_capture"
    ],
    "sales": [
        "web_scrape_bs4", 
        "browser_automation_selenium", 
        "desktop_automation_pyautogui"
    ],
    "marketing": [
        "web_scrape_bs4", 
        "browser_automation_selenium", 
        "desktop_automation_pyautogui", 
        "screenshot_capture"
    ],
    "finance": [
        "web_scrape_bs4", 
        "filesystem_read", 
        "filesystem_write",
        "system_info"
    ],
    "hr": [
        "filesystem_read", 
        "filesystem_write"
    ],
    "legal": [
        "filesystem_read", 
        "filesystem_write", 
        "repo_scan",
        "windows_eventlog_read"
    ],
    "customer": [
        "web_scrape_bs4", 
        "browser_automation_selenium",
        "consult_ui"
    ],
    "daena_office": [
        "system_info", 
        "process_list", 
        "service_list", 
        "net_connections", 
        "windows_eventlog_read", 
        "defender_status_read", 
        "workspace_index", 
        "workspace_search", 
        "repo_scan"
    ]
}

def get_tools_for_department(dept_id: str) -> List[str]:
    """Get list of tool names for a specific department."""
    return DEPARTMENT_TOOLS.get(dept_id, DEPARTMENT_TOOLS.get("daena_office", []))
