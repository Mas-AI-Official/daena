"""
Session Categories API - Manage chat session organization
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/api/v1/daena/categories", tags=["categories"])

class SessionCategory:
    EXECUTIVE = "executive"
    DEPARTMENTS = "departments"
    AGENTS = "agents"
    GENERAL = "general"

# Category metadata
CATEGORIES = {
    "executive": {
        "id": "executive",
        "name": "Executive",
        "description": "1-on-1 with Masoud (Founder)",
        "icon": "fa-crown",
        "color": "#D4AF37"  # Gold
    },
    "departments": {
        "id": "departments",
        "name": "Departments",
        "description": "Department-level discussions",
        "icon": "fa-building",
        "color": "#8B5CF6"  # Purple
    },
    "agents": {
        "id": "agents",
        "name": "Agents",
        "description": "Agent coordination & tasks",
        "icon": "fa-robot",
        "color": "#3B82F6"  # Blue
    },
    "general": {
        "id": "general",
        "name": "General",
        "description": "Miscellaneous conversations",
        "icon": "fa-comments",
        "color": "#6B7280"  # Gray
    }
}

@router.get("/list")
async def get_categories():
    """Get all available session categories"""
    return {
        "categories": list(CATEGORIES.values())
    }

@router.post("/{session_id}/set")
async def set_session_category(session_id: str, category: str):
    """Set category for a session"""
    from backend.routes.daena import active_sessions
    
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if category not in CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    
    active_sessions[session_id].category = category
    
    return {
        "success": True,
        "session_id": session_id,
        "category": category
    }

@router.post("/{session_id}/update_title")
async def update_session_title(session_id: str, title: str):
    """Update session title"""
    from backend.routes.daena import active_sessions
    
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    active_sessions[session_id].title = title
    
    return {
        "success": True,
        "session_id": session_id,
        "title": title
    }
