"""
Canonical tool execution endpoint for Daena + agents.

POST /api/v1/tools/execute
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel

from backend.services.cmp_service import run_cmp_tool_action
from backend.tools.registry import list_tools


router = APIRouter(prefix="/api/v1/tools", tags=["tools"])


def _trace_id(request: Optional[Request]) -> str:
    if request is not None and hasattr(request.state, "trace_id") and request.state.trace_id:
        return str(request.state.trace_id)
    return uuid.uuid4().hex


class ToolExecuteRequest(BaseModel):
    tool_name: str
    args: Dict[str, Any] = {}
    department: Optional[str] = None
    agent_id: Optional[str] = None
    reason: Optional[str] = None
    dry_run: bool = False


@router.get("/status")
async def tools_status():
    """
    Returns tool registry plus basic availability hints (dependency installed checks are done at runtime per tool).
    """
    return {"success": True, "tools": list_tools()}


from backend.routes.auth import get_current_user

@router.post("/execute")
async def tools_execute(
    req: ToolExecuteRequest, 
    request: Request,
    current_user: dict = Depends(get_current_user)
):
    """
    Execute a tool with governance checks.
    Authenticated users only.
    """
    trace_id = _trace_id(request)
    
    # Basic Governance / Risk Check
    # In a full systems, we would check tool metadata for risk_level
    # For now, we block high-risk tools for non-founders/admins if implied
    # or rely on run_cmp_tool_action to handle internal checks.
    # The crucial part is we now have current_user.
    
    # Map user info to context for tool execution
    context = req.args.get("context", {})
    context["user_id"] = current_user.get("sub")
    context["user_role"] = current_user.get("role")
    req.args["context"] = context

    out = await run_cmp_tool_action(
        tool_name=req.tool_name,
        args=req.args,
        department=req.department,
        agent_id=req.agent_id,
        reason=req.reason,
        trace_id=trace_id,
        dry_run=req.dry_run,
    )
    return {"success": out["status"] == "ok", **out}


class ConsultUIRequest(BaseModel):
    provider: str  # "chatgpt" | "gemini"
    question: str
    timeout_sec: int = 60
    manual_approval: bool = True


@router.post("/consult_ui")
async def consult_ui_endpoint(req: ConsultUIRequest, request: Request):
    """
    Consult external LLM UI via browser automation (manual approval mode).
    
    This is a fallback mode when APIs are unavailable or too costly.
    Requires ENABLE_UI_CONSULT=1 and manual approval by default.
    """
    import os
    
    # Check feature flag
    if os.getenv("ENABLE_UI_CONSULT", "0") != "1":
        return {
            "success": False,
            "status": "error",
            "error": "UI Consult Mode disabled. Set ENABLE_UI_CONSULT=1 to enable.",
        }
    
    trace_id = _trace_id(request)
    
    # Execute via canonical tool runner
    out = await run_cmp_tool_action(
        tool_name="consult_ui",
        args={
            "provider": req.provider,
            "question": req.question,
            "timeout_sec": req.timeout_sec,
            "manual_approval": req.manual_approval,
        },
        department=None,
        agent_id=None,
        reason="daena.ui_consult",
        trace_id=trace_id,
    )
    
    return {"success": out["status"] == "ok", **out}




# ============ WEB SEARCH ENDPOINTS ============

class SearchRequest(BaseModel):
    query: str
    num_results: int = 5
    provider: Optional[str] = None


@router.post("/search")
async def web_search(req: SearchRequest):
    import os
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        from backend.services.daena_tools.web_search import web_search_service
        
        result = await web_search_service.search(
            query=req.query,
            num_results=req.num_results,
            preferred_provider=req.provider
        )
        
        if not result.get("success"):
            return {"success": False, "error": result.get("error", "Search failed"), "query": req.query, "results": []}
        
        return {
            "success": True,
            "query": req.query,
            "results": [{"title": r.get("title", ""), "url": r.get("url", r.get("link", "")), "snippet": r.get("snippet", r.get("description", "")), "provider": result.get("provider", "unknown")} for r in result.get("results", [])],
            "provider_used": result.get("provider", "unknown"),
            "total_results": len(result.get("results", []))
        }
    except Exception as e:
        logger.error(f"Search failed: {e}")
        return {"success": False, "error": str(e), "query": req.query, "results": []}


@router.get("/search")
async def web_search_get(q: str, num: int = 5, provider: Optional[str] = None):
    req = SearchRequest(query=q, num_results=num, provider=provider)
    return await web_search(req)


@router.get("/providers")
async def list_search_providers():
    import os
    providers = [
        {"name": "brave", "available": bool(os.getenv("BRAVE_API_KEY")), "priority": 1},
        {"name": "serper", "available": bool(os.getenv("SERPER_API_KEY")), "priority": 2},
        {"name": "tavily", "available": bool(os.getenv("TAVILY_API_KEY")), "priority": 3},
        {"name": "duckduckgo", "available": True, "priority": 4}
    ]
    active = next((p["name"] for p in providers if p["available"]), "duckduckgo")
    return {"providers": providers, "active_provider": active}


# ============ TOOLS LIBRARY ENDPOINTS (CMP-style) ============

# Tool catalog (100+ tools like n8n)
TOOLS_CATALOG = [
    {
        "id": "n8n",
        "name": "n8n",
        "category": "automation",
        "logo": "https://n8n.io/n8n-logo.png",
        "description": "Workflow automation for technical teams",
        "auth_type": "oauth2",
        "popularity": 95
    },
    {
        "id": "zapier",
        "name": "Zapier",
        "category": "automation",
        "logo": "https://zapier.com/logo.png",
        "description": "Automate workflows between 5000+ apps",
        "auth_type": "oauth2",
        "popularity": 98
    },
    {
        "id": "github",
        "name": "GitHub",
        "category": "development",
        "logo": "https://github.com/logo.png",
        "description": "Code hosting and collaboration",
        "auth_type": "oauth2",
        "popularity": 99
    },
    {
        "id": "notion",
        "name": "Notion",
        "category": "productivity",
        "logo": "https://notion.so/logo.png",
        "description": "All-in-one workspace",
        "auth_type": "oauth2",
        "popularity": 92
    },
    {
        "id": "slack",
        "name": "Slack",
        "category": "communication",
        "logo": "https://slack.com/logo.png",
        "description": "Team communication platform",
        "auth_type": "oauth2",
        "popularity": 96
    },
    {
        "id": "airtable",
        "name": "Airtable",
        "category": "database",
        "logo": "https://airtable.com/logo.png",
        "description": "Low-code database platform",
        "auth_type": "oauth2",
        "popularity": 88
    },
    {
        "id": "stripe",
        "name": "Stripe",
        "category": "payments",
        "logo": "https://stripe.com/logo.png",
        "description": "Payment processing platform",
        "auth_type": "api_key",
        "popularity": 97
    },
    {
        "id": "openai",
        "name": "OpenAI",
        "category": "ai",
        "logo": "https://openai.com/logo.png",
        "description": "AI models and APIs",
        "auth_type": "api_key",
        "popularity": 99
    }
]

class ConnectToolRequest(BaseModel):
    tool_id: str
    credentials: Dict[str, Any]


@router.get("/library")
async def get_tools_library(
    category: Optional[str] = None,
    search: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """Get tools catalog with filtering"""
    import os
    import json
    
    tools = TOOLS_CATALOG.copy()
    user_id = current_user.get('id') or current_user.get('sub')
    
    # Filter by category
    if category and category != "all":
        tools = [t for t in tools if t["category"] == category]
    
    # Filter by search
    if search:
        search_lower = search.lower()
        tools = [
            t for t in tools 
            if search_lower in t["name"].lower() 
            or search_lower in t["description"].lower()
        ]
    
    # Get user's connected tools from storage
    connected_ids = set()
    try:
        connections_file = os.path.join(os.getcwd(), "data", "tool_connections.json")
        if os.path.exists(connections_file):
            with open(connections_file, 'r') as f:
                all_connections = json.load(f)
                user_connections = all_connections.get(str(user_id), {})
                connected_ids = set(user_connections.keys())
    except Exception as e:
        print(f"[Tools] Error loading connections: {e}")
    
    # Mark connected tools
    for tool in tools:
        tool["connected"] = tool["id"] in connected_ids
    
    categories = list(set(t["category"] for t in TOOLS_CATALOG))
    
    return {
        "tools": tools,
        "categories": categories,
        "count": len(tools),
        "connected_count": len(connected_ids)
    }


@router.post("/connect")
async def connect_tool(
    req: ConnectToolRequest,
    current_user: dict = Depends(get_current_user)
):
    """Connect a tool"""
    import os
    import json
    from datetime import datetime
    
    tool = next((t for t in TOOLS_CATALOG if t["id"] == req.tool_id), None)
    if not tool:
        raise HTTPException(404, "Tool not found")
    
    user_id = str(current_user.get('id') or current_user.get('sub'))
    
    # Store connection (in production, encrypt credentials)
    try:
        connections_file = os.path.join(os.getcwd(), "data", "tool_connections.json")
        os.makedirs(os.path.dirname(connections_file), exist_ok=True)
        
        all_connections = {}
        if os.path.exists(connections_file):
            with open(connections_file, 'r') as f:
                all_connections = json.load(f)
        
        if user_id not in all_connections:
            all_connections[user_id] = {}
        
        all_connections[user_id][req.tool_id] = {
            "credentials_encrypted": "encrypted",  # TODO: actual encryption
            "connected_at": datetime.now().isoformat(),
            "status": "active"
        }
        
        with open(connections_file, 'w') as f:
            json.dump(all_connections, f, indent=2)
        
        return {"status": "connected", "tool_id": req.tool_id}
        
    except Exception as e:
        raise HTTPException(500, f"Failed to save connection: {str(e)}")
