"""
Capabilities API
Returns enabled tools, scopes, and system capabilities for Daena.
Used by the LLM to understand what actions are available.
"""
from fastapi import APIRouter, Depends
from typing import Dict, List, Any
from pydantic import BaseModel
from pathlib import Path

from backend.config.settings import settings, project_root

router = APIRouter(prefix="/capabilities", tags=["Capabilities"])


class ToolCapability(BaseModel):
    name: str
    description: str
    enabled: bool
    requires_approval: bool
    scope: str  # "workspace", "system", "network"


class WorkspaceScope(BaseModel):
    path: str
    readable: bool
    writable: bool


class CapabilitiesResponse(BaseModel):
    version: str
    tools: List[ToolCapability]
    workspaces: List[WorkspaceScope]
    features: Dict[str, bool]
    limits: Dict[str, Any]


def get_enabled_tools() -> List[ToolCapability]:
    """Get list of enabled tools for Daena."""
    # Core tools - always available
    tools = [
        ToolCapability(
            name="filesystem_read",
            description="Read files and directories within allowed workspaces",
            enabled=True,
            requires_approval=False,
            scope="workspace"
        ),
        ToolCapability(
            name="workspace_search",
            description="Search/grep within workspace files",
            enabled=True,
            requires_approval=False,
            scope="workspace"
        ),
        ToolCapability(
            name="write_to_file",
            description="Write or create files in workspace",
            enabled=True,
            requires_approval=True,
            scope="workspace"
        ),
        ToolCapability(
            name="apply_patch",
            description="Apply code patches to existing files",
            enabled=True,
            requires_approval=True,
            scope="workspace"
        ),
        ToolCapability(
            name="git_diff",
            description="Show git diff for pending changes",
            enabled=True,
            requires_approval=False,
            scope="workspace"
        ),
        ToolCapability(
            name="git_commit",
            description="Commit changes to git repository",
            enabled=True,
            requires_approval=True,
            scope="workspace"
        ),
    ]
    
    # Execution layer tools (if enabled)
    if getattr(settings, 'enable_execution_layer', True):
        tools.extend([
            ToolCapability(
                name="shell_exec",
                description="Execute allowlisted shell commands",
                enabled=True,
                requires_approval=True,
                scope="system"
            ),
            ToolCapability(
                name="browser_open",
                description="Open URLs in browser (Playwright)",
                enabled=getattr(settings, 'enable_browser_tools', False),
                requires_approval=True,
                scope="network"
            ),
        ])
    
    # DeFi tools (if enabled)
    defi_enabled = getattr(settings, 'enable_defi_tools', False)
    if defi_enabled:
        tools.extend([
            ToolCapability(
                name="defi_slither_scan",
                description="Run Slither static analysis on Solidity contracts",
                enabled=True,
                requires_approval=False,
                scope="workspace"
            ),
            ToolCapability(
                name="defi_mythril_scan",
                description="Run Mythril symbolic execution",
                enabled=True,
                requires_approval=False,
                scope="workspace"
            ),
            ToolCapability(
                name="defi_apply_fix",
                description="Apply security fixes to contracts",
                enabled=True,
                requires_approval=True,
                scope="workspace"
            ),
        ])
    
    return tools


def get_workspace_scopes() -> List[WorkspaceScope]:
    """Get allowed workspace scopes."""
    workspaces = [
        WorkspaceScope(
            path=str(project_root),
            readable=True,
            writable=True
        ),
    ]
    
    # Add configured workspaces
    if hasattr(settings, 'workspace_allowlist'):
        for ws in settings.workspace_allowlist or []:
            workspaces.append(WorkspaceScope(
                path=ws,
                readable=True,
                writable=True
            ))
    
    return workspaces


@router.get("", response_model=CapabilitiesResponse)
async def get_capabilities():
    """
    Get current Daena capabilities.
    
    This endpoint returns:
    - Enabled tools and their scopes
    - Allowed workspaces
    - Feature flags
    - System limits
    
    Used by the LLM to understand available actions.
    """
    return CapabilitiesResponse(
        version="1.0.0",
        tools=get_enabled_tools(),
        workspaces=get_workspace_scopes(),
        features={
            "filesystem_access": True,
            "code_editing": True,
            "git_integration": True,
            "execution_layer": getattr(settings, 'enable_execution_layer', True),
            "browser_automation": getattr(settings, 'enable_browser_tools', False),
            "defi_security": getattr(settings, 'enable_defi_tools', False),
            "voice_interface": getattr(settings, 'enable_voice', False),
            "autonomous_mode": getattr(settings, 'autonomous_mode', False),
        },
        limits={
            "max_file_size_bytes": 10 * 1024 * 1024,  # 10MB
            "max_output_chars": 50000,
            "tool_timeout_seconds": 300,
            "max_concurrent_tools": 3,
        }
    )


@router.get("/summary")
async def get_capabilities_summary():
    """
    Get a compact summary of capabilities for system prompts.
    
    Returns a string that can be injected into LLM prompts.
    """
    tools = get_enabled_tools()
    workspaces = get_workspace_scopes()
    
    enabled_tools = [t.name for t in tools if t.enabled]
    approval_tools = [t.name for t in tools if t.enabled and t.requires_approval]
    
    summary = f"""
AVAILABLE TOOLS:
{', '.join(enabled_tools)}

TOOLS REQUIRING APPROVAL:
{', '.join(approval_tools) or 'None'}

ACCESSIBLE WORKSPACES:
{', '.join([w.path for w in workspaces])}

IMPORTANT NOTES:
- You CAN read files using filesystem_read
- You CAN search files using workspace_search  
- You CAN modify files using write_to_file or apply_patch (requires approval)
- NEVER say "I cannot access files" - you have full workspace access
- Always verify file contents before claiming they don't exist
"""
    return {"summary": summary.strip()}


@router.get("/tools/{tool_name}")
async def get_tool_details(tool_name: str):
    """Get detailed information about a specific tool."""
    tools = get_enabled_tools()
    for tool in tools:
        if tool.name == tool_name:
            return {
                "tool": tool.dict(),
                "usage_example": get_tool_usage_example(tool_name)
            }
    return {"error": f"Tool '{tool_name}' not found"}


def get_tool_usage_example(tool_name: str) -> str:
    """Get usage example for a tool."""
    examples = {
        "filesystem_read": "filesystem_read(path='/path/to/file.py')",
        "workspace_search": "workspace_search(query='def main', path='/workspace')",
        "write_to_file": "write_to_file(path='/path/to/file.py', content='...')",
        "apply_patch": "apply_patch(file='/path/to/file.py', diff='@@ -1,3 +1,4 @@...')",
        "git_diff": "git_diff(path='/workspace')",
        "shell_exec": "shell_exec(command='npm test', cwd='/workspace')",
        "defi_slither_scan": "defi_slither_scan(contract='/contracts/Token.sol')",
    }
    return examples.get(tool_name, f"{tool_name}(...)")
