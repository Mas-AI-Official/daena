"""
Capabilities API for Daena awareness and LLM system prompt.
- GET /api/v1/capabilities: live capabilities (hands_gateway, governance, tool_catalog).
- get_enabled_tools() / get_workspace_scopes(): used by llm_service for system prompt.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List

from fastapi import APIRouter

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


@dataclass
class EnabledTool:
    name: str
    enabled: bool
    requires_approval: bool


@dataclass
class WorkspaceScope:
    path: str


def get_enabled_tools() -> List[EnabledTool]:
    """Return tools with enabled and requires_approval for llm_service system prompt."""
    try:
        from backend.tools.registry import list_tools
        from backend.services.tool_broker import get_risk_level, requires_approval as risk_requires_approval
        raw = list_tools(include_enabled=True)
        out: List[EnabledTool] = []
        for t in raw:
            name = t.get("name") or ""
            enabled = t.get("enabled", True)
            try:
                risk = get_risk_level({"action_type": name, "tool_name": name})
                req_approval = risk_requires_approval(risk)
            except Exception:
                req_approval = name in ("shell_exec", "filesystem_write", "apply_patch", "terminal.run", "filesystem.download")
            out.append(EnabledTool(name=name, enabled=enabled, requires_approval=req_approval))
        return out
    except Exception:
        from backend.core.capabilities import TOOL_CATALOG
        return [
            EnabledTool(name=t["id"], enabled=True, requires_approval=bool(t.get("requires_approval")))
            for t in TOOL_CATALOG
        ]


def get_workspace_scopes() -> List[WorkspaceScope]:
    """Return workspace paths for llm_service system prompt."""
    path = os.getenv("WORKSPACE_PATH") or os.getcwd()
    try:
        from backend.tools.registry import _workspace_root
        path = _workspace_root()
    except Exception:
        pass
    return [WorkspaceScope(path=path)]


@router.get("")
async def get_capabilities() -> Dict[str, Any]:
    """
    Live capabilities: hands_gateway, governance, tool_catalog, version.
    Same shape as backend.core.capabilities.build_capabilities() for Control Plane and awareness UI.
    """
    try:
        from backend.core.capabilities import build_capabilities
        return await build_capabilities()
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Capabilities build failed: %s", e)
        return {
            "success": False,
            "error": str(e),
            "hands_gateway": {"status": "offline", "url": os.getenv("DAENABOT_HANDS_URL", "not_set"), "capabilities": []},
            "available": {"hands_gateway": False, "local_llm": False, "tool_catalog": True},
            "health": {},
        }
